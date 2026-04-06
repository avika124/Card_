"""
rag/knowledge_base.py — Vector knowledge base for compliance regulations.

Architecture:
  - ChromaDB as the vector store (local, no server needed)
  - Anthropic claude to embed via API (or sentence-transformers as fallback)
  - Chunked regulation text indexed by regulation ID, source, section
  - Retrieval injects relevant regulation context into compliance checks

Usage:
  from rag.knowledge_base import KnowledgeBase
  kb = KnowledgeBase()
  kb.ingest_file("regulations/udaap.txt", regulation="udaap", source="CFPB")
  chunks = kb.retrieve("penalty APR disclosure requirements", regulation="tila", top_k=5)
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

# ── Constants ─────────────────────────────────────────────────────────────────
CHUNK_SIZE   = 800    # characters per chunk
CHUNK_OVERLAP = 150   # overlap between chunks
TOP_K_DEFAULT = 5
DB_PATH = str(Path(__file__).parent / "chroma_db")

REGULATION_IDS = [
    "udaap", "tila", "ecoa", "fcra", "bsa",
    "pci", "scra", "collections", "sr117"
]


# ── Embedding function ─────────────────────────────────────────────────────────

def _get_embedding_fn():
    """
    Use Anthropic embeddings if available, otherwise fall back to
    chromadb's built-in default (all-MiniLM-L6-v2 via sentence-transformers).
    """
    try:
        # Prefer lightweight built-in so no extra deps needed
        return embedding_functions.DefaultEmbeddingFunction()
    except Exception:
        return embedding_functions.DefaultEmbeddingFunction()


# ── Text chunking ──────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preserving paragraph boundaries."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = text.split("\n\n")

    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            # Overlap: keep last `overlap` chars
            current = current[-overlap:] + "\n\n" + para
        else:
            current = (current + "\n\n" + para).strip()

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c) > 50]


def _doc_id(text: str, source: str, idx: int) -> str:
    h = hashlib.md5(f"{source}:{idx}:{text[:50]}".encode()).hexdigest()[:8]
    return f"{source}_{idx}_{h}"


# ── KnowledgeBase class ────────────────────────────────────────────────────────

class KnowledgeBase:
    """
    Local vector knowledge base for compliance regulations and policies.

    Collections:
      - "regulations" : official regulatory text (CFPB, Fed, OCC, etc.)
      - "policies"    : internal or company policy documents
      - "agreements"  : cardholder agreements for reference
    """

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        self._emb_fn = _get_embedding_fn()

        # Create collections if they don't exist
        self.regulations = self.client.get_or_create_collection(
            name="regulations",
            embedding_function=self._emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.policies = self.client.get_or_create_collection(
            name="policies",
            embedding_function=self._emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.agreements = self.client.get_or_create_collection(
            name="agreements",
            embedding_function=self._emb_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def _collection_for(self, doc_type: str):
        return {
            "regulation": self.regulations,
            "policy":     self.policies,
            "agreement":  self.agreements,
        }.get(doc_type, self.policies)

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_text(
        self,
        text: str,
        source: str,
        regulation: str = "general",
        doc_type: str = "regulation",   # regulation | policy | agreement
        section: str = "",
        url: str = "",
    ) -> int:
        """Chunk and embed plain text into the knowledge base. Returns chunk count."""
        chunks = chunk_text(text)
        if not chunks:
            return 0

        collection = self._collection_for(doc_type)
        ids, docs, metas = [], [], []

        for i, chunk in enumerate(chunks):
            doc_id = _doc_id(chunk, source, i)
            ids.append(doc_id)
            docs.append(chunk)
            metas.append({
                "source":     source,
                "regulation": regulation,
                "doc_type":   doc_type,
                "section":    section,
                "url":        url,
                "chunk_idx":  i,
            })

        # Upsert in batches of 100
        batch = 100
        for start in range(0, len(ids), batch):
            collection.upsert(
                ids=ids[start:start+batch],
                documents=docs[start:start+batch],
                metadatas=metas[start:start+batch],
            )

        return len(chunks)

    def ingest_file(
        self,
        file_path: str,
        regulation: str = "general",
        doc_type: str = "regulation",
        source: Optional[str] = None,
        url: str = "",
    ) -> int:
        """Ingest a file (TXT, PDF, DOCX) into the knowledge base."""
        path = Path(file_path)
        src = source or path.stem
        ext = path.suffix.lower()

        if ext == ".txt" or ext == ".md":
            text = path.read_text(encoding="utf-8", errors="ignore")

        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages)

        elif ext in (".docx", ".doc"):
            import subprocess
            result = subprocess.run(
                ["pandoc", str(path), "-t", "plain"],
                capture_output=True, text=True
            )
            text = result.stdout

        elif ext == ".json":
            data = json.loads(path.read_text())
            text = json.dumps(data, indent=2)

        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not text.strip():
            raise ValueError(f"No text extracted from {file_path}")

        return self.ingest_text(text, source=src, regulation=regulation,
                                doc_type=doc_type, url=url)

    def ingest_directory(
        self,
        dir_path: str,
        regulation: str = "general",
        doc_type: str = "regulation",
    ) -> dict:
        """Ingest all supported files in a directory."""
        results = {}
        for f in Path(dir_path).iterdir():
            if f.suffix.lower() in (".txt", ".md", ".pdf", ".docx"):
                try:
                    n = self.ingest_file(str(f), regulation=regulation, doc_type=doc_type)
                    results[f.name] = {"status": "ok", "chunks": n}
                except Exception as e:
                    results[f.name] = {"status": "error", "error": str(e)}
        return results

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        regulation: Optional[str] = None,
        doc_type: Optional[str] = None,
        top_k: int = TOP_K_DEFAULT,
    ) -> list[dict]:
        """
        Retrieve most relevant chunks for a query.
        Returns list of {text, source, regulation, section, url, score}.
        """
        # Determine which collections to search
        if doc_type:
            collections = [self._collection_for(doc_type)]
        else:
            collections = [self.regulations, self.policies, self.agreements]

        where = {}
        if regulation and regulation != "general":
            where["regulation"] = {"$in": [regulation, "general"]}

        all_results = []
        for col in collections:
            if col.count() == 0:
                continue
            try:
                kwargs = {"query_texts": [query], "n_results": min(top_k, col.count())}
                if where:
                    kwargs["where"] = where
                res = col.query(**kwargs)
                for i, doc in enumerate(res["documents"][0]):
                    meta = res["metadatas"][0][i]
                    dist = res["distances"][0][i]
                    all_results.append({
                        "text":       doc,
                        "source":     meta.get("source", ""),
                        "regulation": meta.get("regulation", ""),
                        "section":    meta.get("section", ""),
                        "url":        meta.get("url", ""),
                        "score":      round(1 - dist, 3),  # cosine similarity
                    })
            except Exception:
                continue

        # Sort by score, deduplicate, return top_k
        all_results.sort(key=lambda x: x["score"], reverse=True)
        seen = set()
        unique = []
        for r in all_results:
            key = r["text"][:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    def retrieve_for_regulations(
        self,
        query: str,
        reg_ids: list[str],
        top_k_per_reg: int = 3,
    ) -> dict[str, list[dict]]:
        """Retrieve relevant chunks for each regulation separately."""
        result = {}
        for reg_id in reg_ids:
            chunks = self.retrieve(query, regulation=reg_id, top_k=top_k_per_reg)
            if chunks:
                result[reg_id] = chunks
        return result

    def build_context_block(
        self,
        query: str,
        reg_ids: list[str],
        top_k: int = 4,
    ) -> str:
        """
        Build a formatted context block to inject into the Claude prompt.
        Returns a string ready to append to the system prompt.
        """
        chunks = self.retrieve(query, top_k=top_k * len(reg_ids))
        if not chunks:
            return ""

        lines = ["\n\n--- RETRIEVED REGULATORY CONTEXT ---",
                 "Use the following authoritative regulatory text when analyzing the document:\n"]

        for c in chunks[:top_k * 2]:
            lines.append(f"[{c['regulation'].upper()} | {c['source']}]")
            lines.append(c["text"])
            lines.append("")

        lines.append("--- END REGULATORY CONTEXT ---\n")
        return "\n".join(lines)

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            "regulations": self.regulations.count(),
            "policies":    self.policies.count(),
            "agreements":  self.agreements.count(),
            "total_chunks": (
                self.regulations.count() +
                self.policies.count() +
                self.agreements.count()
            ),
            "db_path": DB_PATH,
        }

    def list_sources(self) -> list[str]:
        sources = set()
        for col in [self.regulations, self.policies, self.agreements]:
            if col.count() == 0:
                continue
            results = col.get(include=["metadatas"])
            for m in results.get("metadatas", []):
                sources.add(m.get("source", "unknown"))
        return sorted(sources)

    def delete_source(self, source: str) -> int:
        """Remove all chunks from a given source."""
        deleted = 0
        for col in [self.regulations, self.policies, self.agreements]:
            try:
                results = col.get(where={"source": source}, include=["metadatas"])
                ids = results.get("ids", [])
                if ids:
                    col.delete(ids=ids)
                    deleted += len(ids)
            except Exception:
                pass
        return deleted

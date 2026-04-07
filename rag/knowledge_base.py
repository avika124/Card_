"""
rag/knowledge_base.py — Vector knowledge base for compliance regulations.

Architecture:
  - JSON file store (no external vector DB needed)
  - TF-IDF via scikit-learn for similarity retrieval
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
import pickle
from pathlib import Path
from typing import Optional

# ── Constants ─────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 150
TOP_K_DEFAULT = 5
DB_PATH = str(Path(__file__).parent / "json_db")


# ── Text chunking ──────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preserving paragraph boundaries."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > chunk_size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n\n" + para
        else:
            current = (current + "\n\n" + para).strip()
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if len(c) > 50]


def _doc_id(text: str, source: str, idx: int) -> str:
    h = hashlib.md5(f"{source}:{idx}:{text[:50]}".encode()).hexdigest()[:8]
    return f"{source}_{idx}_{h}"


# ── Simple JSON + TF-IDF store ─────────────────────────────────────────────────

class _Store:
    """Lightweight JSON-backed document store with TF-IDF retrieval."""

    def __init__(self, store_path: str):
        self.path = Path(store_path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.data_file = self.path / "docs.json"
        self._docs: dict = self._load()

    def _load(self) -> dict:
        if self.data_file.exists():
            try:
                return json.loads(self.data_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self.data_file.write_text(
            json.dumps(self._docs, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def upsert(self, doc_id: str, text: str, metadata: dict):
        self._docs[doc_id] = {"text": text, "metadata": metadata}
        self._save()

    def count(self) -> int:
        return len(self._docs)

    def get_all(self) -> list[dict]:
        return [{"id": k, "text": v["text"], **v["metadata"]}
                for k, v in self._docs.items()]

    def delete_by_source(self, source: str) -> int:
        to_del = [k for k, v in self._docs.items()
                  if v.get("metadata", {}).get("source") == source]
        for k in to_del:
            del self._docs[k]
        if to_del:
            self._save()
        return len(to_del)

    def query(self, query_text: str, top_k: int = 5,
              regulation: Optional[str] = None) -> list[dict]:
        """TF-IDF similarity search."""
        docs = self.get_all()
        if not docs:
            return []

        # Filter by regulation if specified
        if regulation and regulation != "general":
            filtered = [d for d in docs
                        if d.get("regulation") in (regulation, "general")]
            if filtered:
                docs = filtered

        if not docs:
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            corpus = [d["text"] for d in docs]
            vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
            tfidf_matrix = vectorizer.fit_transform(corpus + [query_text])
            query_vec = tfidf_matrix[-1]
            doc_vecs = tfidf_matrix[:-1]
            scores = cosine_similarity(query_vec, doc_vecs)[0]

            top_indices = np.argsort(scores)[::-1][:top_k]
            results = []
            for i in top_indices:
                if scores[i] > 0:
                    results.append({
                        "text":       docs[i]["text"],
                        "source":     docs[i].get("source", ""),
                        "regulation": docs[i].get("regulation", ""),
                        "section":    docs[i].get("section", ""),
                        "url":        docs[i].get("url", ""),
                        "score":      round(float(scores[i]), 3),
                    })
            return results

        except ImportError:
            # Fallback: keyword overlap scoring
            query_words = set(query_text.lower().split())
            results = []
            for d in docs:
                doc_words = set(d["text"].lower().split())
                overlap = len(query_words & doc_words)
                score = overlap / (len(query_words) + 1)
                if score > 0:
                    results.append({
                        "text":       d["text"],
                        "source":     d.get("source", ""),
                        "regulation": d.get("regulation", ""),
                        "section":    d.get("section", ""),
                        "url":        d.get("url", ""),
                        "score":      round(score, 3),
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]


# ── KnowledgeBase class ────────────────────────────────────────────────────────

class KnowledgeBase:
    """
    Local knowledge base for compliance regulations and policies.

    Collections:
      - "regulations" : official regulatory text (CFPB, Fed, OCC, etc.)
      - "policies"    : internal or company policy documents
      - "agreements"  : cardholder agreements for reference
    """

    def __init__(self, db_path: str = DB_PATH):
        self.regulations = _Store(os.path.join(db_path, "regulations"))
        self.policies    = _Store(os.path.join(db_path, "policies"))
        self.agreements  = _Store(os.path.join(db_path, "agreements"))

    def _collection_for(self, doc_type: str) -> _Store:
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
        doc_type: str = "regulation",
        section: str = "",
        url: str = "",
    ) -> int:
        chunks = chunk_text(text)
        if not chunks:
            return 0
        store = self._collection_for(doc_type)
        for i, chunk in enumerate(chunks):
            doc_id = _doc_id(chunk, source, i)
            store.upsert(doc_id, chunk, {
                "source": source, "regulation": regulation,
                "doc_type": doc_type, "section": section,
                "url": url, "chunk_idx": i,
            })
        return len(chunks)

    def ingest_file(
        self,
        file_path: str,
        regulation: str = "general",
        doc_type: str = "regulation",
        source: Optional[str] = None,
        url: str = "",
    ) -> int:
        path = Path(file_path)
        src  = source or path.stem
        ext  = path.suffix.lower()

        if ext in (".txt", ".md"):
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

    def ingest_directory(self, dir_path: str, regulation: str = "general",
                         doc_type: str = "regulation") -> dict:
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
        if doc_type:
            stores = [self._collection_for(doc_type)]
        else:
            stores = [self.regulations, self.policies, self.agreements]

        all_results = []
        for store in stores:
            if store.count() == 0:
                continue
            all_results.extend(store.query(query, top_k=top_k, regulation=regulation))

        all_results.sort(key=lambda x: x["score"], reverse=True)
        seen, unique = set(), []
        for r in all_results:
            key = r["text"][:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    def retrieve_for_regulations(self, query: str, reg_ids: list[str],
                                  top_k_per_reg: int = 3) -> dict[str, list[dict]]:
        result = {}
        for reg_id in reg_ids:
            chunks = self.retrieve(query, regulation=reg_id, top_k=top_k_per_reg)
            if chunks:
                result[reg_id] = chunks
        return result

    def build_context_block(self, query: str, reg_ids: list[str],
                             top_k: int = 4) -> str:
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
        r = self.regulations.count()
        p = self.policies.count()
        a = self.agreements.count()
        return {
            "regulations":  r,
            "policies":     p,
            "agreements":   a,
            "total_chunks": r + p + a,
            "db_path":      DB_PATH,
        }

    def list_sources(self) -> list[str]:
        sources = set()
        for store in [self.regulations, self.policies, self.agreements]:
            for doc in store.get_all():
                sources.add(doc.get("source", "unknown"))
        return sorted(sources)

    def delete_source(self, source: str) -> int:
        deleted = 0
        for store in [self.regulations, self.policies, self.agreements]:
            deleted += store.delete_by_source(source)
        return deleted

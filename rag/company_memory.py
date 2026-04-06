"""
rag/company_memory.py — Company Prior Communications & Policy Store

Separate from the regulatory knowledge base, this module manages:
  - Prior marketing materials (emails, ads, landing pages, brochures)
  - Internal policies (credit, collections, underwriting, servicing)
  - Customer-facing communications (cardholder agreements, disclosures)
  - Prior adverse action notices, settlement letters, scripts

When a new document is checked, the engine retrieves the most similar
prior company communications and checks for conflicts:
  - Does this contradict what we told customers before?
  - Does this violate our own stated policies?
  - Are we making promises inconsistent with prior disclosures?
  - Have we changed terms without proper notice?

Collections:
  "marketing"     : ads, emails, landing pages, promotional copy
  "policies"      : internal credit, collections, underwriting policies
  "disclosures"   : cardholder agreements, adverse action, disclosures
  "scripts"       : call center, collections, onboarding scripts
  "settlements"   : settlement letters, hardship agreements, consent orders
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime

import chromadb
from chromadb.utils import embedding_functions

# ── Constants ──────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 600
CHUNK_OVERLAP = 120
DB_PATH = str(Path(__file__).parent / "company_db")

DOC_TYPES = {
    "marketing":   "Marketing Materials",
    "policy":      "Internal Policies",
    "disclosure":  "Customer Disclosures",
    "script":      "Call / Collections Scripts",
    "settlement":  "Settlements / Consent Orders",
    "agreement":   "Cardholder Agreements",
    "other":       "Other Communications",
}

CONFLICT_CATEGORIES = {
    "rate_fee":        "Interest rates or fee amounts",
    "rewards":         "Rewards program terms or earning rates",
    "benefits":        "Product benefits or protections",
    "eligibility":     "Eligibility criteria or requirements",
    "process":         "Processes or procedures described to customers",
    "legal_rights":    "Legal rights or dispute procedures",
    "policy_change":   "Policy changes or amendments",
    "promise":         "Explicit or implicit promises made to customers",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) > size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n\n" + para
        else:
            current = (current + "\n\n" + para).strip()
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if len(c) > 40]


def _doc_id(text: str, source: str, idx: int) -> str:
    h = hashlib.md5(f"{source}:{idx}:{text[:40]}".encode()).hexdigest()[:8]
    return f"cm_{source[:20]}_{idx}_{h}"


# ── CompanyMemory class ────────────────────────────────────────────────────────

class CompanyMemory:
    """
    Stores and retrieves a company's prior communications and policies
    for conflict detection during compliance checks.
    """

    def __init__(self, db_path: str = DB_PATH, company_name: str = "Company"):
        self.company_name = company_name
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)
        self._emb = embedding_functions.DefaultEmbeddingFunction()

        # One collection per doc type
        self._cols = {}
        for dtype in DOC_TYPES:
            self._cols[dtype] = self.client.get_or_create_collection(
                name=f"cm_{dtype}",
                embedding_function=self._emb,
                metadata={"hnsw:space": "cosine"},
            )

    def _col(self, doc_type: str):
        return self._cols.get(doc_type, self._cols["other"])

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def add_document(
        self,
        text: str,
        source: str,
        doc_type: str = "marketing",
        product: str = "general",
        date: str = "",
        version: str = "",
        tags: str = "",
        url: str = "",
    ) -> int:
        """
        Add a company document to memory.

        Args:
            text:     Full document text
            source:   Document name / identifier
            doc_type: One of: marketing, policy, disclosure, script,
                      settlement, agreement, other
            product:  Product name (e.g. "Sapphire Reserve", "Freedom Unlimited")
            date:     Document date (YYYY-MM-DD or free text)
            version:  Document version string
            tags:     Comma-separated tags for filtering
            url:      Source URL if applicable

        Returns:
            Number of chunks indexed
        """
        chunks = _chunk(text)
        if not chunks:
            return 0

        col = self._col(doc_type)
        ids, docs, metas = [], [], []
        timestamp = datetime.now().isoformat()

        for i, chunk in enumerate(chunks):
            ids.append(_doc_id(chunk, source, i))
            docs.append(chunk)
            metas.append({
                "source":    source,
                "doc_type":  doc_type,
                "product":   product,
                "date":      date or timestamp[:10],
                "version":   version,
                "tags":      tags,
                "url":       url,
                "indexed_at": timestamp,
                "chunk_idx": i,
            })

        batch = 100
        for start in range(0, len(ids), batch):
            col.upsert(
                ids=ids[start:start+batch],
                documents=docs[start:start+batch],
                metadatas=metas[start:start+batch],
            )
        return len(chunks)

    def add_file(
        self,
        file_path: str,
        doc_type: str = "marketing",
        source: Optional[str] = None,
        product: str = "general",
        date: str = "",
        version: str = "",
        tags: str = "",
    ) -> int:
        """Ingest a file (TXT, PDF, DOCX, MD) into company memory."""
        import subprocess
        path = Path(file_path)
        src = source or path.stem
        ext = path.suffix.lower()

        if ext in (".txt", ".md"):
            text = path.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext in (".docx", ".doc"):
            result = subprocess.run(["pandoc", str(path), "-t", "plain"],
                                    capture_output=True, text=True)
            text = result.stdout
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not text.strip():
            raise ValueError(f"No text extracted from {file_path}")

        return self.add_document(text, source=src, doc_type=doc_type,
                                 product=product, date=date, version=version)

    def add_directory(
        self,
        dir_path: str,
        doc_type: str = "marketing",
        product: str = "general",
    ) -> dict:
        """Ingest all supported files in a directory."""
        results = {}
        for f in Path(dir_path).iterdir():
            if f.suffix.lower() in (".txt", ".md", ".pdf", ".docx"):
                try:
                    n = self.add_file(str(f), doc_type=doc_type, product=product)
                    results[f.name] = {"status": "ok", "chunks": n}
                except Exception as e:
                    results[f.name] = {"status": "error", "error": str(e)}
        return results

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def retrieve_similar(
        self,
        query: str,
        doc_types: Optional[list[str]] = None,
        product: Optional[str] = None,
        top_k: int = 8,
    ) -> list[dict]:
        """
        Retrieve the most similar prior company communications for conflict checking.
        """
        search_cols = [self._cols[dt] for dt in (doc_types or list(DOC_TYPES.keys()))
                       if dt in self._cols]

        where = {}
        if product and product != "general":
            where["product"] = {"$in": [product, "general"]}

        all_results = []
        for col in search_cols:
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
                        "text":     doc,
                        "source":   meta.get("source", ""),
                        "doc_type": meta.get("doc_type", ""),
                        "product":  meta.get("product", ""),
                        "date":     meta.get("date", ""),
                        "version":  meta.get("version", ""),
                        "score":    round(1 - dist, 3),
                    })
            except Exception:
                continue

        all_results.sort(key=lambda x: x["score"], reverse=True)
        seen, unique = set(), []
        for r in all_results:
            key = r["text"][:80]
            if key not in seen:
                seen.add(key); unique.append(r)
        return unique[:top_k]

    def build_conflict_context(self, query: str, product: Optional[str] = None,
                               top_k: int = 8) -> str:
        """
        Build the conflict-check context block for injection into Claude prompt.
        """
        chunks = self.retrieve_similar(query, product=product, top_k=top_k)
        if not chunks:
            return ""

        lines = [
            "\n\n--- PRIOR COMPANY COMMUNICATIONS (check for conflicts) ---",
            f"The following are {self.company_name}'s prior marketing materials, ",
            "policies, and customer communications. Flag any conflicts, contradictions,",
            "or inconsistencies between the NEW document and these prior communications.\n",
        ]
        for c in chunks:
            dt_label = DOC_TYPES.get(c["doc_type"], c["doc_type"])
            lines.append(f"[{dt_label} | {c['source']} | {c['date']} | score:{c['score']}]")
            lines.append(c["text"])
            lines.append("")
        lines.append("--- END PRIOR COMMUNICATIONS ---\n")
        return "\n".join(lines)

    # ── Stats / management ────────────────────────────────────────────────────

    def stats(self) -> dict:
        counts = {dt: self._cols[dt].count() for dt in DOC_TYPES}
        counts["total"] = sum(counts.values())
        counts["db_path"] = DB_PATH
        counts["company"] = self.company_name
        return counts

    def list_documents(self, doc_type: Optional[str] = None) -> list[dict]:
        """List all unique documents (by source) in memory."""
        search = [doc_type] if doc_type else list(DOC_TYPES.keys())
        seen, docs = set(), []
        for dt in search:
            col = self._cols.get(dt)
            if not col or col.count() == 0:
                continue
            results = col.get(include=["metadatas"])
            for m in results.get("metadatas", []):
                src = m.get("source", "")
                if src not in seen:
                    seen.add(src)
                    docs.append({
                        "source":   src,
                        "doc_type": m.get("doc_type", dt),
                        "product":  m.get("product", ""),
                        "date":     m.get("date", ""),
                        "version":  m.get("version", ""),
                    })
        return sorted(docs, key=lambda x: x["date"], reverse=True)

    def delete_document(self, source: str) -> int:
        """Remove all chunks from a given source document."""
        deleted = 0
        for col in self._cols.values():
            try:
                results = col.get(where={"source": source}, include=["metadatas"])
                ids = results.get("ids", [])
                if ids:
                    col.delete(ids=ids); deleted += len(ids)
            except Exception:
                pass
        return deleted

    def clear_all(self) -> int:
        """Remove ALL company memory. Use with care."""
        total = 0
        for dt, col in self._cols.items():
            n = col.count()
            if n > 0:
                ids = col.get()["ids"]
                col.delete(ids=ids)
                total += n
        return total

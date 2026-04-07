"""
rag/company_memory.py — Company Prior Communications & Policy Store
(No chromadb — uses JSON + TF-IDF for Python 3.14 compatibility)
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime

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


# ── JSON Store ─────────────────────────────────────────────────────────────────

class _Store:
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

    def clear(self) -> int:
        n = len(self._docs)
        self._docs = {}
        self._save()
        return n

    def query(self, query_text: str, top_k: int = 8,
              product: Optional[str] = None) -> list[dict]:
        docs = self.get_all()
        if not docs:
            return []

        if product and product != "general":
            filtered = [d for d in docs if d.get("product") in (product, "general")]
            if filtered:
                docs = filtered

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            corpus = [d["text"] for d in docs]
            vectorizer = TfidfVectorizer(stop_words="english", max_features=5000)
            tfidf_matrix = vectorizer.fit_transform(corpus + [query_text])
            scores = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])[0]
            top_indices = np.argsort(scores)[::-1][:top_k]

            results = []
            for i in top_indices:
                if scores[i] > 0:
                    results.append({
                        "text":     docs[i]["text"],
                        "source":   docs[i].get("source", ""),
                        "doc_type": docs[i].get("doc_type", ""),
                        "product":  docs[i].get("product", ""),
                        "date":     docs[i].get("date", ""),
                        "version":  docs[i].get("version", ""),
                        "score":    round(float(scores[i]), 3),
                    })
            return results

        except ImportError:
            query_words = set(query_text.lower().split())
            results = []
            for d in docs:
                overlap = len(query_words & set(d["text"].lower().split()))
                score = overlap / (len(query_words) + 1)
                if score > 0:
                    results.append({
                        "text":     d["text"],
                        "source":   d.get("source", ""),
                        "doc_type": d.get("doc_type", ""),
                        "product":  d.get("product", ""),
                        "date":     d.get("date", ""),
                        "version":  d.get("version", ""),
                        "score":    round(score, 3),
                    })
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

    def list_unique_sources(self) -> list[dict]:
        seen, docs = set(), []
        for d in self.get_all():
            src = d.get("source", "")
            if src not in seen:
                seen.add(src)
                docs.append({
                    "source":   src,
                    "doc_type": d.get("doc_type", ""),
                    "product":  d.get("product", ""),
                    "date":     d.get("date", ""),
                    "version":  d.get("version", ""),
                })
        return docs


# ── CompanyMemory class ────────────────────────────────────────────────────────

class CompanyMemory:
    def __init__(self, db_path: str = DB_PATH, company_name: str = "Company"):
        self.company_name = company_name
        self._stores = {
            dt: _Store(os.path.join(db_path, f"cm_{dt}"))
            for dt in DOC_TYPES
        }

    def _store(self, doc_type: str) -> _Store:
        return self._stores.get(doc_type, self._stores["other"])

    def add_document(self, text: str, source: str, doc_type: str = "marketing",
                     product: str = "general", date: str = "", version: str = "",
                     tags: str = "", url: str = "") -> int:
        chunks = _chunk(text)
        if not chunks:
            return 0
        store = self._store(doc_type)
        timestamp = datetime.now().isoformat()
        for i, chunk in enumerate(chunks):
            store.upsert(_doc_id(chunk, source, i), chunk, {
                "source": source, "doc_type": doc_type, "product": product,
                "date": date or timestamp[:10], "version": version,
                "tags": tags, "url": url, "indexed_at": timestamp, "chunk_idx": i,
            })
        return len(chunks)

    def add_file(self, file_path: str, doc_type: str = "marketing",
                 source: Optional[str] = None, product: str = "general",
                 date: str = "", version: str = "", tags: str = "") -> int:
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
            import subprocess
            result = subprocess.run(["pandoc", str(path), "-t", "plain"],
                                    capture_output=True, text=True)
            text = result.stdout
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not text.strip():
            raise ValueError(f"No text extracted from {file_path}")

        return self.add_document(text, source=src, doc_type=doc_type,
                                 product=product, date=date, version=version)

    def retrieve_similar(self, query: str, doc_types: Optional[list[str]] = None,
                         product: Optional[str] = None, top_k: int = 8) -> list[dict]:
        search = doc_types or list(DOC_TYPES.keys())
        all_results = []
        for dt in search:
            store = self._stores.get(dt)
            if store and store.count() > 0:
                all_results.extend(store.query(query, top_k=top_k, product=product))

        all_results.sort(key=lambda x: x["score"], reverse=True)
        seen, unique = set(), []
        for r in all_results:
            key = r["text"][:80]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    def build_conflict_context(self, query: str, product: Optional[str] = None,
                               top_k: int = 8) -> str:
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

    def stats(self) -> dict:
        counts = {dt: self._stores[dt].count() for dt in DOC_TYPES}
        counts["total"] = sum(counts.values())
        counts["db_path"] = DB_PATH
        counts["company"] = self.company_name
        return counts

    def list_documents(self, doc_type: Optional[str] = None) -> list[dict]:
        search = [doc_type] if doc_type else list(DOC_TYPES.keys())
        seen, docs = set(), []
        for dt in search:
            store = self._stores.get(dt)
            if not store:
                continue
            for d in store.list_unique_sources():
                src = d.get("source", "")
                if src not in seen:
                    seen.add(src)
                    docs.append(d)
        return sorted(docs, key=lambda x: x.get("date", ""), reverse=True)

    def delete_document(self, source: str) -> int:
        deleted = 0
        for store in self._stores.values():
            deleted += store.delete_by_source(source)
        return deleted

    def clear_all(self) -> int:
        total = 0
        for store in self._stores.values():
            total += store.clear()
        return total

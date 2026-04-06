"""
rag/rag_compliance.py — RAG-enhanced compliance checking.

Wraps the base compliance checker with retrieved regulatory context,
making findings more accurate, specific, and citation-backed.

Usage:
  from rag.rag_compliance import RAGComplianceChecker
  checker = RAGComplianceChecker()
  result = checker.check_text(text, reg_ids=["udaap","tila"])
"""

import os
import json
import base64
from typing import Optional
from pathlib import Path

import anthropic

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.knowledge_base import KnowledgeBase

# ── Regulation metadata ───────────────────────────────────────────────────────

REGULATIONS = {
    "udaap":       {"label": "UDAAP",                "description": "Unfair, Deceptive, or Abusive Acts or Practices"},
    "tila":        {"label": "TILA / Reg Z / CARD Act","description": "Truth in Lending Act"},
    "ecoa":        {"label": "ECOA / Reg B",           "description": "Equal Credit Opportunity Act"},
    "fcra":        {"label": "FCRA / Reg V",           "description": "Fair Credit Reporting Act"},
    "bsa":         {"label": "BSA / AML / OFAC / CIP", "description": "Bank Secrecy Act / Anti-Money Laundering"},
    "pci":         {"label": "PCI DSS",                "description": "Payment Card Industry Data Security Standard"},
    "scra":        {"label": "SCRA",                   "description": "Servicemembers Civil Relief Act"},
    "collections": {"label": "Collections Conduct",    "description": "FDCPA / Collection Practices"},
    "sr117":       {"label": "SR 11-7",                "description": "Model Risk Management"},
}

BASE_SYSTEM_PROMPT = """You are an expert credit card compliance attorney and regulatory analyst with deep expertise in consumer financial protection laws. Analyze the provided content against the specified regulations and return ONLY a valid JSON object — no markdown, no explanation, no preamble.

Return this exact structure:
{{
  "overall_risk": "high|medium|low|pass",
  "summary": "2-3 sentence executive summary of findings",
  "rag_enhanced": true,
  "findings": [
    {{
      "regulation": "regulation name",
      "severity": "high|medium|low|pass",
      "issue": "short title of the issue or pass confirmation",
      "detail": "detailed explanation citing specific regulatory requirements",
      "regulatory_citation": "specific CFR section, statute, or guidance cited e.g. '12 CFR 1026.16(b)' or 'FDCPA §807'",
      "excerpt": "relevant quoted text from the ANALYZED DOCUMENT that triggered this finding",
      "recommendation": "specific actionable recommendation"
    }}
  ]
}}

Produce one finding per regulation checked. Be specific. When regulatory context is provided below, cite the exact provisions.{context}"""


def _build_reg_list(reg_ids: list[str]) -> str:
    lines = []
    for rid in reg_ids:
        if rid in REGULATIONS:
            r = REGULATIONS[rid]
            lines.append(f"- {r['label']}: {r['description']}")
    return "\n".join(lines)


def _parse_result(raw: str) -> dict:
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


# ── RAGComplianceChecker ──────────────────────────────────────────────────────

class RAGComplianceChecker:
    """
    Compliance checker that retrieves relevant regulatory context
    from the knowledge base before calling Claude.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 4000,
        use_rag: bool = True,
        rag_top_k: int = 6,
    ):
        self.client    = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self.model     = model or os.environ.get("MODEL", "claude-sonnet-4-20250514")
        self.max_tokens = max_tokens
        self.use_rag   = use_rag
        self.rag_top_k = rag_top_k

        if use_rag:
            try:
                self.kb = KnowledgeBase()
                self._rag_available = self.kb.stats()["total_chunks"] > 0
            except Exception:
                self._rag_available = False
        else:
            self._rag_available = False

    def _get_context(self, content_sample: str, reg_ids: list[str]) -> str:
        """Retrieve regulatory context from knowledge base."""
        if not self._rag_available:
            return ""
        try:
            return self.kb.build_context_block(
                query=content_sample[:500],
                reg_ids=reg_ids,
                top_k=self.rag_top_k,
            )
        except Exception:
            return ""

    def _call_claude(self, system: str, messages: list) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
        )
        raw = "".join(b.text for b in response.content if hasattr(b, "text"))
        result = _parse_result(raw)
        result["rag_enhanced"] = self._rag_available
        result["rag_chunks_retrieved"] = self.rag_top_k if self._rag_available else 0
        return result

    def check_text(self, text: str, reg_ids: list[str]) -> dict:
        context  = self._get_context(text, reg_ids)
        system   = BASE_SYSTEM_PROMPT.format(context=context)
        reg_list = _build_reg_list(reg_ids)

        return self._call_claude(system, [{
            "role": "user",
            "content": (
                f"Analyze the following content for compliance against these regulations:\n"
                f"{reg_list}\n\nContent to analyze:\n---\n{text}\n---"
            ),
        }])

    def check_image(self, image_bytes: bytes, media_type: str, reg_ids: list[str]) -> dict:
        context  = self._get_context("credit card document image", reg_ids)
        system   = BASE_SYSTEM_PROMPT.format(context=context)
        reg_list = _build_reg_list(reg_ids)
        b64      = base64.standard_b64encode(image_bytes).decode()

        return self._call_claude(system, [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text",  "text": f"Analyze this document image for compliance against:\n{reg_list}\nExtract all text and check thoroughly."},
            ],
        }])

    def check_file(self, file_path: str, reg_ids: list[str]) -> dict:
        import subprocess
        ext = Path(file_path).suffix.lower()
        image_exts = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                      ".png": "image/png", ".webp": "image/webp"}

        if ext in image_exts:
            with open(file_path, "rb") as f:
                return self.check_image(f.read(), image_exts[ext], reg_ids)

        if ext == ".txt":
            text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
        elif ext in (".docx", ".doc"):
            result = subprocess.run(["pandoc", file_path, "-t", "plain"],
                                    capture_output=True, text=True)
            text = result.stdout
        elif ext in (".json",):
            text = Path(file_path).read_text()
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        if not text.strip():
            raise ValueError("Could not extract text from file.")

        return self.check_text(text, reg_ids)

    # ── Knowledge base management ─────────────────────────────────────────────

    def ingest_text(self, text: str, source: str, regulation: str = "general",
                    doc_type: str = "policy") -> int:
        if not self.use_rag:
            raise RuntimeError("RAG is disabled.")
        n = self.kb.ingest_text(text, source=source, regulation=regulation, doc_type=doc_type)
        self._rag_available = True
        return n

    def ingest_file(self, file_path: str, regulation: str = "general",
                    doc_type: str = "policy", source: Optional[str] = None) -> int:
        if not self.use_rag:
            raise RuntimeError("RAG is disabled.")
        n = self.kb.ingest_file(file_path, regulation=regulation,
                                doc_type=doc_type, source=source)
        self._rag_available = True
        return n

    def kb_stats(self) -> dict:
        if not self.use_rag:
            return {"rag": "disabled"}
        return self.kb.stats()

    def kb_sources(self) -> list[str]:
        if not self.use_rag:
            return []
        return self.kb.list_sources()

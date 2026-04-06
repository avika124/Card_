"""
rag/conflict_detector.py — Prior Communications Conflict Detector

Uses Claude to find contradictions between a new document and a company's
prior marketing materials, policies, and customer-facing communications.

Conflict types detected:
  - Rate / fee changes not disclosed
  - Rewards terms that contradict prior advertising
  - Benefits described differently across materials
  - Policy changes without customer notice
  - Eligibility criteria inconsistencies
  - Legal rights described differently
  - Explicit promises contradicted by new terms
  - Process / procedure described differently to customers
"""

import os
import json
from typing import Optional
from pathlib import Path

import anthropic

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.company_memory import CompanyMemory, DOC_TYPES

CONFLICT_SYSTEM_PROMPT = """You are a senior compliance attorney specializing in consumer financial products. Your task is to compare a NEW document against a company's PRIOR communications and identify conflicts, contradictions, and inconsistencies.

A conflict exists when:
- The new document states a rate, fee, or term differently than prior materials
- The new document promises or implies something that prior policies prohibit or restrict
- The new document changes customer rights or procedures without clear notice
- Marketing claims in the new document contradict what disclosures or agreements state
- The new document uses language that would create a different customer expectation than prior communications

Analyze carefully and return ONLY valid JSON — no markdown, no preamble:

{
  "has_conflicts": true|false,
  "conflict_risk": "high|medium|low|none",
  "summary": "2-3 sentence summary of conflict findings",
  "conflicts": [
    {
      "severity": "high|medium|low",
      "category": "rate_fee|rewards|benefits|eligibility|process|legal_rights|policy_change|promise",
      "title": "short title of the conflict",
      "new_document_says": "exact language or paraphrase from the new document",
      "prior_communication_says": "exact language or paraphrase from the prior communication",
      "prior_source": "name/date of the prior document",
      "explanation": "why this is a conflict and why it matters",
      "recommendation": "specific action to resolve this conflict"
    }
  ],
  "consistent_items": [
    "Brief description of areas where new doc is consistent with prior communications"
  ]
}

If no conflicts are found, return has_conflicts: false, conflict_risk: none, and an empty conflicts array."""


class ConflictDetector:
    """
    Detects conflicts between new documents and prior company communications.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        company_memory: Optional[CompanyMemory] = None,
        company_name: str = "Company",
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self.model = model or os.environ.get("MODEL", "claude-sonnet-4-20250514")
        self.memory = company_memory or CompanyMemory(company_name=company_name)
        self.company_name = company_name

    def _parse(self, raw: str) -> dict:
        clean = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)

    def check_conflicts(
        self,
        new_document_text: str,
        product: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
        top_k: int = 10,
    ) -> dict:
        """
        Check a new document against prior company communications for conflicts.

        Args:
            new_document_text: Text of the document being checked
            product: Product name to filter prior communications (optional)
            doc_types: Limit to specific doc types (optional)
            top_k: Number of prior communication chunks to retrieve

        Returns:
            Conflict analysis dict with has_conflicts, conflicts list, etc.
        """
        # Check if memory has anything
        stats = self.memory.stats()
        if stats["total"] == 0:
            return {
                "has_conflicts": False,
                "conflict_risk": "none",
                "summary": "No prior company communications in memory. Upload marketing materials and policies to enable conflict detection.",
                "conflicts": [],
                "consistent_items": [],
                "memory_empty": True,
            }

        # Retrieve relevant prior communications
        prior_context = self.memory.build_conflict_context(
            query=new_document_text[:600],
            product=product,
            top_k=top_k,
        )

        if not prior_context.strip():
            return {
                "has_conflicts": False,
                "conflict_risk": "none",
                "summary": "No relevant prior communications found for this product/content area.",
                "conflicts": [],
                "consistent_items": [],
                "memory_empty": False,
            }

        # Build prompt
        user_msg = (
            f"COMPANY: {self.company_name}\n\n"
            f"NEW DOCUMENT TO CHECK:\n"
            f"{'─'*60}\n"
            f"{new_document_text[:4000]}\n"
            f"{'─'*60}\n"
            f"{prior_context}"
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=3000,
            system=CONFLICT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = "".join(b.text for b in response.content if hasattr(b, "text"))
        result = self._parse(raw)
        result["prior_docs_checked"] = stats["total"]
        result["company"] = self.company_name
        return result

    def check_file_conflicts(
        self,
        file_path: str,
        product: Optional[str] = None,
        doc_types: Optional[list[str]] = None,
    ) -> dict:
        """Check a file against prior communications."""
        import subprocess
        path = Path(file_path)
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

        return self.check_conflicts(text, product=product, doc_types=doc_types)


def format_conflict_report(result: dict, company_name: str = "Company") -> str:
    """Format conflict results as readable text for CLI output."""
    lines = [
        f"\n{'='*60}",
        f"  CONFLICT CHECK — {company_name}",
        f"  Risk: {result.get('conflict_risk','unknown').upper()}",
        f"  Prior docs checked: {result.get('prior_docs_checked', 0)}",
        f"{'='*60}",
        f"\n{result.get('summary','')}",
    ]

    conflicts = result.get("conflicts", [])
    if conflicts:
        lines.append(f"\n── {len(conflicts)} Conflict(s) Found ─────────────────────────")
        sev_icons = {"high": "🔴", "medium": "🟡", "low": "🟠"}
        for i, c in enumerate(conflicts, 1):
            lines.extend([
                f"\n{sev_icons.get(c.get('severity','low'), '⚪')} [{c.get('severity','').upper()}] {c.get('title','')}",
                f"  Category:    {c.get('category','')}",
                f"  New doc:     {c.get('new_document_says','')}",
                f"  Prior says:  {c.get('prior_communication_says','')}",
                f"  Source:      {c.get('prior_source','')}",
                f"  Why it matters: {c.get('explanation','')}",
                f"  Fix:         {c.get('recommendation','')}",
            ])
    else:
        lines.append("\n✅ No conflicts found with prior communications.")

    consistent = result.get("consistent_items", [])
    if consistent:
        lines.append("\n── Consistent Areas ──────────────────────────────────")
        for item in consistent:
            lines.append(f"  ✓ {item}")

    return "\n".join(lines)

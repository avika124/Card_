"""
compliance.py — Core compliance checking logic using Anthropic Claude API
Shared across FastAPI, Streamlit, and CLI implementations.
"""

import os
import base64
import json
from typing import Optional
import anthropic

REGULATIONS = {
    "udaap": {"label": "UDAAP", "description": "Unfair, Deceptive, or Abusive Acts or Practices"},
    "tila":  {"label": "TILA / Reg Z / CARD Act", "description": "Truth in Lending Act"},
    "ecoa":  {"label": "ECOA / Reg B", "description": "Equal Credit Opportunity Act"},
    "fcra":  {"label": "FCRA / Reg V", "description": "Fair Credit Reporting Act"},
    "bsa":   {"label": "BSA / AML / OFAC / CIP", "description": "Bank Secrecy Act / Anti-Money Laundering"},
    "pci":   {"label": "PCI DSS", "description": "Payment Card Industry Data Security Standard"},
    "scra":  {"label": "SCRA", "description": "Servicemembers Civil Relief Act"},
    "collections": {"label": "Collections Conduct", "description": "FDCPA / Collection Practices"},
    "sr117": {"label": "SR 11-7", "description": "Model Risk Management"},
}

SYSTEM_PROMPT = """You are an expert credit card compliance attorney and regulatory analyst with deep expertise in consumer financial protection laws. Analyze the provided content against the specified regulations and return ONLY a valid JSON object — no markdown, no explanation, no preamble.

Return this exact structure:
{
  "overall_risk": "high|medium|low|pass",
  "summary": "2-3 sentence executive summary of findings",
  "findings": [
    {
      "regulation": "regulation name",
      "severity": "high|medium|low|pass",
      "issue": "short title of the issue or pass confirmation",
      "detail": "detailed explanation of the finding, specific concern, or why it passes",
      "excerpt": "relevant quoted text from the document that triggered this finding, or empty string if pass",
      "recommendation": "specific actionable recommendation, or empty string if pass"
    }
  ]
}

Produce one finding per regulation checked. Be specific, cite exact language when possible, and be rigorous — err on the side of flagging potential issues."""


def build_reg_list(reg_ids: list[str]) -> str:
    lines = []
    for rid in reg_ids:
        if rid in REGULATIONS:
            r = REGULATIONS[rid]
            lines.append(f"- {r['label']}: {r['description']}")
    return "\n".join(lines)


def check_text(text: str, reg_ids: list[str], api_key: Optional[str] = None) -> dict:
    """Run compliance check on plain text content."""
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    reg_list = build_reg_list(reg_ids)

    response = client.messages.create(
        model=os.environ.get("MODEL", "claude-sonnet-4-20250514"),
        max_tokens=int(os.environ.get("MAX_TOKENS", 4000)),
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Analyze the following content for compliance against these regulations:\n{reg_list}\n\nContent to analyze:\n---\n{text}\n---"
        }]
    )

    raw = "".join(block.text for block in response.content if hasattr(block, "text"))
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


def check_image(image_bytes: bytes, media_type: str, reg_ids: list[str], api_key: Optional[str] = None) -> dict:
    """Run compliance check on an image (Claude reads text from it)."""
    client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    reg_list = build_reg_list(reg_ids)
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = client.messages.create(
        model=os.environ.get("MODEL", "claude-sonnet-4-20250514"),
        max_tokens=int(os.environ.get("MAX_TOKENS", 4000)),
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64}
                },
                {
                    "type": "text",
                    "text": f"Analyze this document image for compliance against these regulations:\n{reg_list}\n\nExtract all text from the image and check it thoroughly."
                }
            ]
        }]
    )

    raw = "".join(block.text for block in response.content if hasattr(block, "text"))
    clean = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


def check_file(file_path: str, reg_ids: list[str], api_key: Optional[str] = None) -> dict:
    """
    Run compliance check on an uploaded file.
    Supports: .txt, .pdf (text extraction), .docx (via pandoc).
    """
    import subprocess

    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                     ".webp": "image/webp", ".gif": "image/gif"}
        return check_image(image_bytes, media_map.get(ext, "image/png"), reg_ids, api_key)

    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

    elif ext == ".pdf":
        result = subprocess.run(
            ["pdftotext", file_path, "-"],
            capture_output=True, text=True
        )
        text = result.stdout if result.returncode == 0 else ""
        if not text.strip():
            raise ValueError("Could not extract text from PDF. It may be a scanned image — try uploading as an image instead.")

    elif ext in (".docx", ".doc"):
        result = subprocess.run(
            ["pandoc", file_path, "-t", "plain"],
            capture_output=True, text=True
        )
        text = result.stdout if result.returncode == 0 else ""
        if not text.strip():
            raise ValueError("Could not extract text from document.")

    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return check_text(text, reg_ids, api_key)

"""
rag/scraper.py — Regulation ingestion pipeline.

Pulls authoritative regulatory text from public government sources:
  - CFPB (Reg Z, Reg B, Reg V, UDAAP guidance, cardholder agreements)
  - FFIEC (BSA/AML Examination Manual)
  - Federal Reserve (SR 11-7 Model Risk)
  - OCC (Comptroller's Handbook)
  - PCI SSC (PCI DSS summaries)
  - CFPB Agreement Database (Chase + major issuers)

Usage:
  python -m rag.scraper --all
  python -m rag.scraper --source cfpb_regs --regs tila ecoa
  python -m rag.scraper --source chase_agreements
  python -m rag.scraper --url https://... --regulation udaap --source "CFPB Blog"
"""

import os
import re
import time
import argparse
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from rag.knowledge_base import KnowledgeBase

# ── Source registry ────────────────────────────────────────────────────────────

SOURCES = {

    # ── CFPB Regulation text ─────────────────────────────────────────────────
    "cfpb_udaap": {
        "regulation": "udaap",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/",
                "source": "CFPB UDAAP Guidance",
            },
            {
                "url": "https://www.consumerfinance.gov/ask-cfpb/what-is-udaap-en-1423/",
                "source": "CFPB UDAAP FAQ",
            },
        ],
    },

    "cfpb_tila": {
        "regulation": "tila",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/rules-policy/regulations/1026/",
                "source": "Regulation Z (12 CFR 1026)",
            },
        ],
    },

    "cfpb_ecoa": {
        "regulation": "ecoa",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/rules-policy/regulations/1002/",
                "source": "Regulation B (12 CFR 1002)",
            },
        ],
    },

    "cfpb_fcra": {
        "regulation": "fcra",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/rules-policy/regulations/1022/",
                "source": "Regulation V (12 CFR 1022)",
            },
        ],
    },

    "cfpb_collections": {
        "regulation": "collections",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/rules-policy/regulations/1006/",
                "source": "Regulation F (FDCPA, 12 CFR 1006)",
            },
        ],
    },

    "cfpb_scra": {
        "regulation": "scra",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/consumer-tools/military-financial-relief/",
                "source": "CFPB SCRA Military Relief",
            },
        ],
    },

    # ── CFPB Cardholder Agreement Database ───────────────────────────────────
    "chase_agreements": {
        "regulation": "general",
        "doc_type": "agreement",
        "pages": [
            {
                "url": "https://www.consumerfinance.gov/credit-cards/agreements/issuer/jpmorgan-chase-bank-national-association/",
                "source": "Chase CFPB Agreement Index",
                "is_index": True,  # Will extract PDF links
            },
        ],
    },

    # ── Federal Reserve SR 11-7 ───────────────────────────────────────────────
    "fed_sr117": {
        "regulation": "sr117",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm",
                "source": "SR 11-7 Model Risk Management",
            },
        ],
    },

    # ── FFIEC BSA/AML ─────────────────────────────────────────────────────────
    "ffiec_bsa": {
        "regulation": "bsa",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://bsaaml.ffiec.gov/manual/Introduction/01",
                "source": "FFIEC BSA/AML Examination Manual",
            },
            {
                "url": "https://bsaaml.ffiec.gov/manual/RegulatoryRequirements/01",
                "source": "FFIEC BSA Regulatory Requirements",
            },
        ],
    },

    # ── OCC Comptroller's Handbook ────────────────────────────────────────────
    "occ_credit_card": {
        "regulation": "general",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.occ.gov/publications-and-resources/publications/comptrollers-handbook/files/credit-card-lending/index-credit-card-lending.html",
                "source": "OCC Comptroller's Handbook - Credit Card",
            },
        ],
    },

    # ── PCI DSS ───────────────────────────────────────────────────────────────
    "pci_dss": {
        "regulation": "pci",
        "doc_type": "regulation",
        "pages": [
            {
                "url": "https://www.pcisecuritystandards.org/standards/pci-dss/",
                "source": "PCI DSS v4.0 Overview",
            },
        ],
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ComplianceCheckerBot/1.0; "
        "+https://github.com/avika124/Card_)"
    )
}


# ── HTML text extraction ───────────────────────────────────────────────────────

def extract_text_from_html(html: str, url: str = "") -> str:
    """Extract clean readable text from HTML, removing nav/footer/scripts."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "nav", "header",
                               "footer", "aside", "form", "button"]):
        tag.decompose()

    # Try main content areas first
    main = (
        soup.find("main") or
        soup.find("article") or
        soup.find(id="main-content") or
        soup.find(class_="content") or
        soup.find(class_="main-content") or
        soup.body
    )

    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def fetch_url(url: str, retries: int = 3, delay: float = 1.5) -> Optional[str]:
    """Fetch a URL with retries. Returns HTML string or None."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"  Attempt {attempt+1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def fetch_pdf_text(url: str) -> Optional[str]:
    """Download a PDF and extract its text."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()

        import tempfile
        from pypdf import PdfReader
        import io

        content = resp.content
        reader = PdfReader(io.BytesIO(content))
        text = "\n\n".join(p.extract_text() or "" for p in reader.pages)
        return text if text.strip() else None
    except Exception as e:
        print(f"  PDF fetch failed for {url}: {e}")
        return None


# ── Ingestion functions ────────────────────────────────────────────────────────

def ingest_page(kb: KnowledgeBase, url: str, source: str,
                regulation: str, doc_type: str) -> dict:
    """Fetch a single page and ingest it."""
    print(f"  Fetching: {url}")
    html = fetch_url(url)
    if not html:
        return {"url": url, "status": "fetch_failed"}

    text = extract_text_from_html(html, url)
    if len(text) < 100:
        return {"url": url, "status": "too_short", "chars": len(text)}

    n = kb.ingest_text(text, source=source, regulation=regulation,
                       doc_type=doc_type, url=url)
    print(f"  ✓ {source}: {n} chunks from {len(text):,} chars")
    return {"url": url, "status": "ok", "chunks": n, "chars": len(text)}


def ingest_source(kb: KnowledgeBase, source_key: str) -> list[dict]:
    """Ingest all pages for a named source."""
    cfg = SOURCES.get(source_key)
    if not cfg:
        print(f"Unknown source: {source_key}")
        return []

    regulation = cfg["regulation"]
    doc_type   = cfg["doc_type"]
    results    = []

    for page in cfg["pages"]:
        url    = page["url"]
        source = page["source"]

        result = ingest_page(kb, url, source, regulation, doc_type)
        results.append(result)
        time.sleep(1.0)  # polite crawl delay

    return results


def ingest_custom_url(kb: KnowledgeBase, url: str, regulation: str,
                      source: str, doc_type: str = "regulation") -> dict:
    """Ingest any URL directly."""
    if url.lower().endswith(".pdf"):
        print(f"  Fetching PDF: {url}")
        text = fetch_pdf_text(url)
        if not text:
            return {"url": url, "status": "pdf_failed"}
        n = kb.ingest_text(text, source=source, regulation=regulation,
                           doc_type=doc_type, url=url)
        print(f"  ✓ PDF {source}: {n} chunks")
        return {"url": url, "status": "ok", "chunks": n}
    else:
        return ingest_page(kb, url, source, regulation, doc_type)


def ingest_all(kb: KnowledgeBase) -> dict:
    """Run all configured sources."""
    all_results = {}
    for key in SOURCES:
        print(f"\n[{key}]")
        all_results[key] = ingest_source(kb, key)
    return all_results


def ingest_local_directory(kb: KnowledgeBase, path: str,
                            regulation: str, doc_type: str) -> dict:
    """Ingest all files in a local directory."""
    print(f"Ingesting directory: {path} → regulation={regulation}, type={doc_type}")
    return kb.ingest_directory(path, regulation=regulation, doc_type=doc_type)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ingest regulations and policies into the compliance knowledge base"
    )
    parser.add_argument("--all", action="store_true",
                        help="Ingest all configured sources")
    parser.add_argument("--source", type=str,
                        help=f"Specific source key. Options: {', '.join(SOURCES.keys())}")
    parser.add_argument("--url", type=str,
                        help="Ingest a custom URL directly")
    parser.add_argument("--file", type=str,
                        help="Ingest a local file")
    parser.add_argument("--dir", type=str,
                        help="Ingest all files in a local directory")
    parser.add_argument("--regulation", type=str, default="general",
                        help="Regulation ID (udaap, tila, ecoa, fcra, bsa, pci, scra, collections, sr117)")
    parser.add_argument("--doc-type", type=str, default="regulation",
                        choices=["regulation", "policy", "agreement"],
                        help="Document type")
    parser.add_argument("--source-name", type=str, default="Custom Source",
                        help="Display name for --url or --file ingestion")
    parser.add_argument("--stats", action="store_true",
                        help="Show knowledge base stats and exit")
    parser.add_argument("--list", action="store_true",
                        help="List all ingested sources")
    parser.add_argument("--delete-source", type=str,
                        help="Delete all chunks from a source")

    args = parser.parse_args()
    kb = KnowledgeBase()

    if args.stats:
        s = kb.stats()
        print("\n── Knowledge Base Stats ──────────────────")
        for k, v in s.items():
            print(f"  {k}: {v}")
        return

    if args.list:
        sources = kb.list_sources()
        print(f"\n── {len(sources)} ingested sources ──────────────────")
        for s in sources:
            print(f"  • {s}")
        return

    if args.delete_source:
        n = kb.delete_source(args.delete_source)
        print(f"Deleted {n} chunks from source: {args.delete_source}")
        return

    print(f"\n{'='*55}")
    print(f"  Compliance Knowledge Base Ingestion")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}")

    results = {}

    if args.all:
        results = ingest_all(kb)

    elif args.source:
        results[args.source] = ingest_source(kb, args.source)

    elif args.url:
        results["custom"] = [ingest_custom_url(
            kb, args.url, args.regulation, args.source_name, args.doc_type
        )]

    elif args.file:
        n = kb.ingest_file(args.file, regulation=args.regulation,
                           doc_type=args.doc_type, source=args.source_name)
        results["file"] = [{"file": args.file, "chunks": n, "status": "ok"}]
        print(f"✓ Ingested {args.file}: {n} chunks")

    elif args.dir:
        results["directory"] = ingest_local_directory(
            kb, args.dir, args.regulation, args.doc_type
        )

    else:
        parser.print_help()
        return

    # Summary
    total_chunks = sum(
        r.get("chunks", 0)
        for batch in results.values()
        for r in (batch if isinstance(batch, list) else batch.values())
        if isinstance(r, dict)
    )
    stats = kb.stats()
    print(f"\n{'='*55}")
    print(f"  Ingestion complete")
    print(f"  New chunks this run : {total_chunks}")
    print(f"  Total in DB         : {stats['total_chunks']}")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()

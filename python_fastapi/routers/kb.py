import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from core.database import log_action
from rag.rag_compliance import RAGComplianceChecker, REGULATIONS
from python_fastapi.auth import get_current_user, require_roles
from python_fastapi.schemas import KBIngestUrlRequest, KBLoadPresetRequest

router = APIRouter(prefix="/api", tags=["knowledge-base"])

PRESETS = {
    "CFPB UDAAP": ("https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/", "udaap"),
    "Reg Z (TILA)": ("https://www.consumerfinance.gov/rules-policy/regulations/1026/", "tila"),
    "Reg B (ECOA)": ("https://www.consumerfinance.gov/rules-policy/regulations/1002/", "ecoa"),
    "Reg V (FCRA)": ("https://www.consumerfinance.gov/rules-policy/regulations/1022/", "fcra"),
    "Reg F (FDCPA)": ("https://www.consumerfinance.gov/rules-policy/regulations/1006/", "collections"),
    "SCRA Guide": ("https://www.consumerfinance.gov/consumer-tools/military-financial-relief/", "scra"),
    "Fed SR 11-7": ("https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm", "sr117"),
}


def get_checker(user: dict) -> RAGComplianceChecker:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "Server is not configured with an ANTHROPIC_API_KEY.")
    return RAGComplianceChecker(api_key=api_key, use_rag=True, company_name=user["company"])


def _scrape(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup.find_all(["script", "style", "nav", "footer"]):
        tag.decompose()
    text = (soup.find("main") or soup.body or soup).get_text(separator="\n", strip=True)
    if len(text) < 100:
        raise HTTPException(422, "Too little text extracted from that URL.")
    return text


@router.get("/regulations")
def list_regulations():
    return {"regulations": REGULATIONS}


@router.get("/kb/presets")
def kb_presets():
    return {"presets": [{"name": name, "url": url, "regulation": reg} for name, (url, reg) in PRESETS.items()]}


@router.get("/kb/stats")
def kb_stats(user: dict = Depends(get_current_user)):
    return get_checker(user).kb_stats()


@router.get("/kb/sources")
def kb_sources(user: dict = Depends(get_current_user)):
    return {"sources": get_checker(user).kb_sources()}


@router.get("/kb/retrieve")
def kb_retrieve(q: str, regulation: Optional[str] = None, top_k: int = 5, user: dict = Depends(get_current_user)):
    checker = get_checker(user)
    return {"query": q, "results": checker.kb.retrieve(q, regulation=regulation, top_k=top_k)}


@router.post("/kb/ingest")
async def kb_ingest(
    source: str = Form(...),
    regulation: str = Form("general"),
    doc_type: str = Form("regulation"),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(require_roles("compliance", "legal", "admin")),
):
    checker = get_checker(user)
    if file is not None:
        suffix = Path(file.filename or "upload").suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        try:
            n = checker.ingest_file(tmp_path, regulation=regulation, doc_type=doc_type, source=source)
        finally:
            os.unlink(tmp_path)
    elif text and text.strip():
        n = checker.ingest_text(text, source=source, regulation=regulation, doc_type=doc_type)
    else:
        raise HTTPException(400, "Provide a file or text.")
    log_action(user["id"], user["email"], "kb_ingest", "kb", source)
    return {"status": "ok", "chunks_added": n}


@router.post("/kb/ingest-url")
def kb_ingest_url(body: KBIngestUrlRequest, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    text = _scrape(body.url)
    n = get_checker(user).ingest_text(text, source=body.source, regulation=body.regulation, doc_type=body.doc_type)
    log_action(user["id"], user["email"], "kb_ingest_url", "kb", body.source, body.url)
    return {"status": "ok", "chunks_added": n, "chars_fetched": len(text)}


@router.post("/kb/load-preset")
def kb_load_preset(body: KBLoadPresetRequest, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    if body.name not in PRESETS:
        raise HTTPException(404, "Unknown preset.")
    url, reg = PRESETS[body.name]
    text = _scrape(url)
    n = get_checker(user).ingest_text(text, source=body.name, regulation=reg, doc_type="regulation")
    log_action(user["id"], user["email"], "kb_load_preset", "kb", body.name)
    return {"status": "ok", "chunks_added": n}


@router.delete("/kb/sources/{source_name}")
def kb_delete_source(source_name: str, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    n = get_checker(user).kb.delete_source(source_name)
    log_action(user["id"], user["email"], "kb_delete_source", "kb", source_name)
    return {"status": "deleted", "chunks_removed": n}

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from core.database import log_action
from rag.rag_compliance import RAGComplianceChecker
from rag.company_memory import DOC_TYPES
from python_fastapi.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/memory", tags=["memory"])

ROOT = Path(__file__).parent.parent.parent


def get_checker(user: dict) -> RAGComplianceChecker:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "Server is not configured with an ANTHROPIC_API_KEY.")
    return RAGComplianceChecker(api_key=api_key, use_rag=True, company_name=user["company"])


@router.get("/doc-types")
def doc_types():
    return {"doc_types": DOC_TYPES}


@router.get("/stats")
def stats(user: dict = Depends(get_current_user)):
    return get_checker(user).memory_stats()


@router.get("/documents")
def list_documents(doc_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    return {"documents": get_checker(user).memory_documents(doc_type)}


@router.post("/documents")
async def add_document(
    source: str = Form(...),
    doc_type: str = Form("marketing"),
    product: str = Form("general"),
    date: str = Form(""),
    version: str = Form(""),
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
            n = checker.add_company_file(tmp_path, doc_type=doc_type, source=source, product=product, date=date, version=version)
        finally:
            os.unlink(tmp_path)
    elif text and text.strip():
        n = checker.add_company_document(text, source=source, doc_type=doc_type, product=product, date=date, version=version)
    else:
        raise HTTPException(400, "Provide a file or text.")

    log_action(user["id"], user["email"], "add_company_memory", "memory", source)
    return {"status": "ok", "chunks_added": n, "source": source}


@router.delete("/documents/{source_name}")
def delete_document(source_name: str, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    n = get_checker(user).delete_company_document(source_name)
    log_action(user["id"], user["email"], "delete_company_memory", "memory", source_name)
    return {"status": "deleted", "chunks_removed": n}


@router.post("/bulk-load-samples")
def bulk_load_samples(user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    test_dir = ROOT / "test-docs"
    if not test_dir.exists():
        raise HTTPException(404, "No sample documents bundled with this deployment.")
    files = list(test_dir.glob("*.txt")) + list(test_dir.glob("*.docx"))
    checker = get_checker(user)
    loaded = []
    for f in files:
        fn = f.stem.lower()
        dt = ("marketing" if "marketing" in fn else
              "disclosure" if ("agreement" in fn or "disclosure" in fn) else
              "script" if "collection" in fn else "policy")
        try:
            checker.add_company_file(str(f), doc_type=dt, source=f.stem)
            loaded.append(f.stem)
        except Exception:
            pass
    log_action(user["id"], user["email"], "bulk_load_company_memory", "memory", f"{len(loaded)} files")
    return {"status": "ok", "loaded": loaded}

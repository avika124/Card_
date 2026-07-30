import os
import io
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from core.database import (
    create_submission, get_submissions, get_submission, save_findings, save_conflicts,
    get_findings, get_conflicts, get_reviews, create_review, mark_false_positive,
    get_users, create_notification, log_action,
)
from rag.rag_compliance import RAGComplianceChecker
from python_fastapi.docx_generator import generate_compliance_docx
from python_fastapi.auth import get_current_user, require_roles
from python_fastapi.schemas import ReviewDecisionRequest
from integrations.notifier import dispatch

router = APIRouter(prefix="/api", tags=["submissions"])


def get_checker(user: dict) -> RAGComplianceChecker:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "Server is not configured with an ANTHROPIC_API_KEY.")
    return RAGComplianceChecker(api_key=api_key, use_rag=True, company_name=user["company"])


def _extract_text_from_upload(tmp_path: str, suffix: str) -> str:
    import subprocess
    if suffix == ".txt":
        return Path(tmp_path).read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(p.extract_text() or "" for p in PdfReader(tmp_path).pages)
    if suffix in (".docx", ".doc"):
        result = subprocess.run(["pandoc", tmp_path, "-t", "plain"], capture_output=True, text=True)
        return result.stdout
    raise HTTPException(400, f"Unsupported file type: {suffix}")


def _assert_can_view_submission(user: dict, sub: dict):
    if sub["company"] != user["company"]:
        raise HTTPException(404, "Submission not found.")
    if user["role"] == "submitter" and sub["submitted_by"] != user["id"]:
        raise HTTPException(403, "You can only view your own submissions.")


@router.post("/submissions")
async def submit_document(
    title: str = Form(...),
    doc_type: str = Form("marketing"),
    product: str = Form("general"),
    channel: str = Form("general"),
    priority: str = Form("normal"),
    regulations: str = Form(...),  # comma-separated reg ids
    run_conflict: bool = Form(True),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
):
    reg_ids = [r.strip() for r in regulations.split(",") if r.strip()]
    if not title.strip() or not reg_ids:
        raise HTTPException(400, "Title and at least one regulation are required.")

    doc_name = "Pasted Text"
    doc_text = text or ""
    tmp_path = None
    try:
        if file is not None:
            doc_name = file.filename or "upload"
            suffix = Path(doc_name).suffix.lower()
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            doc_text = _extract_text_from_upload(tmp_path, suffix)

        if not doc_text.strip():
            raise HTTPException(400, "Document content is empty — paste text or upload a file.")

        checker = get_checker(user)
        try:
            result = checker.check_text(doc_text, reg_ids, product=product or None, run_conflict_check=run_conflict)
        except Exception as e:
            raise HTTPException(502, f"Compliance analysis failed: {e}")
    finally:
        if tmp_path:
            os.unlink(tmp_path)

    sid = create_submission(
        title=title, document_text=doc_text, document_name=doc_name, doc_type=doc_type,
        product=product or "general", channel=channel, submitted_by=user["id"], company=user["company"],
        regulations=reg_ids, run_conflict=run_conflict, priority=priority,
    )
    save_findings(sid, result.get("findings", []))
    save_conflicts(sid, (result.get("conflict_check") or {}).get("conflicts", []))

    for reviewer in [u for u in get_users(user["company"]) if u["role"] in ("compliance", "legal", "admin")]:
        create_notification(
            reviewer["id"], "review", f"New: {title}",
            f"{user['name']} submitted '{title}'. Risk: {result.get('overall_risk', '?').upper()}",
        )
    log_action(user["id"], user["email"], "submit", "submission", sid, title)

    return {"id": sid, "result": result}


@router.get("/submissions")
def list_submissions(status: Optional[str] = None, mine: bool = False, user: dict = Depends(get_current_user)):
    submitted_by = user["id"] if (mine or user["role"] == "submitter") else None
    return {"submissions": get_submissions(user["company"], status=status, submitted_by=submitted_by)}


@router.get("/submissions/{submission_id}")
def get_submission_detail(submission_id: str, user: dict = Depends(get_current_user)):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found.")
    _assert_can_view_submission(user, sub)
    return {
        "submission": sub,
        "findings": get_findings(submission_id),
        "conflicts": get_conflicts(submission_id),
        "reviews": get_reviews(submission_id),
    }


@router.post("/submissions/{submission_id}/review")
def review_submission(submission_id: str, body: ReviewDecisionRequest, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    sub = get_submission(submission_id)
    if not sub or sub["company"] != user["company"]:
        raise HTTPException(404, "Submission not found.")
    if body.decision in ("rejected", "escalated") and not body.notes.strip():
        raise HTTPException(400, "Notes are required for reject/escalate decisions.")

    create_review(submission_id, user["id"], body.decision, body.notes)

    sub_user = next((u for u in get_users(sub["company"]) if u["id"] == sub["submitted_by"]), None)
    if sub_user:
        create_notification(
            sub_user["id"], "decision", f"Decision: {body.decision.upper()}",
            f"Your submission '{sub['title']}' was {body.decision}. {body.notes[:80]}",
        )
    dispatch(
        "review_decision", submission=sub, decision=body.decision, reviewer_name=user["name"],
        notes=body.notes, submitter_email=sub_user["email"] if sub_user else None,
        submitter_name=sub_user["name"] if sub_user else None,
    )
    log_action(user["id"], user["email"], "review_decision", "submission", submission_id, body.decision)
    return {"ok": True}


@router.post("/findings/{finding_id}/false-positive")
def flag_finding_false_positive(finding_id: str, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    mark_false_positive(finding_id, "findings", user["id"])
    return {"ok": True}


@router.post("/conflicts/{conflict_id}/false-positive")
def flag_conflict_false_positive(conflict_id: str, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    mark_false_positive(conflict_id, "conflicts", user["id"])
    return {"ok": True}


@router.get("/submissions/{submission_id}/docx")
def download_submission_docx(submission_id: str, user: dict = Depends(get_current_user)):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found.")
    _assert_can_view_submission(user, sub)
    findings = get_findings(submission_id)
    conflicts = get_conflicts(submission_id)
    result = {"findings": findings, "conflict_check": {"conflicts": conflicts}}
    docx_bytes = generate_compliance_docx(result, document_name=sub["title"])
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="report_{submission_id[:8]}.docx"'},
    )

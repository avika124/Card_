from fastapi import APIRouter, Depends

from core.database import get_analytics, get_submissions, get_audit_log
from python_fastapi.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
def analytics(user: dict = Depends(get_current_user)):
    return get_analytics(user["company"])


@router.get("/export/submissions")
def export_submissions(user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    subs = get_submissions(user["company"])
    return {"submissions": [{"id": s["id"], "title": s["title"], "status": s["status"]} for s in subs]}


@router.get("/export/audit-log")
def export_audit_log(user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    return {"audit_log": get_audit_log(user["company"], limit=1000)}

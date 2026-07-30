from fastapi import APIRouter, Depends

from core.database import get_audit_log
from python_fastapi.auth import require_roles

router = APIRouter(prefix="/api/audit-log", tags=["audit"])


@router.get("")
def audit_log(limit: int = 200, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    return {"entries": get_audit_log(user["company"], limit=limit)}

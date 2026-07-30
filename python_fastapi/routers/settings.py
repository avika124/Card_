from fastapi import APIRouter, Depends

from integrations.notifier import send_slack
from python_fastapi.auth import require_roles

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.post("/test-slack")
def test_slack(user: dict = Depends(require_roles("admin"))):
    ok = send_slack("🧪 Test notification from Compliance Platform!")
    return {"ok": ok}

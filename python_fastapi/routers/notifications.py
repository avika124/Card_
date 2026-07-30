from fastapi import APIRouter, Depends

from core.database import get_notifications, mark_notifications_read
from python_fastapi.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread_only: bool = False, user: dict = Depends(get_current_user)):
    return {"notifications": get_notifications(user["id"], unread_only=unread_only)}


@router.post("/mark-read")
def mark_read(user: dict = Depends(get_current_user)):
    mark_notifications_read(user["id"])
    return {"ok": True}

from fastapi import APIRouter, Depends

from core.database import get_reg_watches, add_reg_watch, log_action
from monitor.reg_monitor import run_once, _seed_default_watches
from python_fastapi.auth import get_current_user, require_roles
from python_fastapi.schemas import RegWatchRequest

router = APIRouter(prefix="/api/reg-monitor", tags=["reg-monitor"])


@router.get("/watches")
def list_watches(user: dict = Depends(get_current_user)):
    return {"watches": get_reg_watches(user["company"])}


@router.post("/watches")
def add_watch(body: RegWatchRequest, user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    wid = add_reg_watch(user["company"], body.regulation, body.url, body.name, user["id"])
    log_action(user["id"], user["email"], "add_reg_watch", "reg_watch", wid, body.name)
    return {"id": wid}


@router.post("/seed-defaults")
def seed_defaults(user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    _seed_default_watches(user["company"])
    return {"watches": get_reg_watches(user["company"])}


@router.post("/run-check")
def run_check(user: dict = Depends(require_roles("compliance", "legal", "admin"))):
    if not get_reg_watches(user["company"]):
        _seed_default_watches(user["company"])
    results = run_once(user["company"])
    log_action(user["id"], user["email"], "run_reg_monitor_check", "reg_watch", "", str(results))
    return results

"""
python_fastapi/main.py — ComplyLine REST API

Full authenticated backend for the Credit Card Compliance Platform:
auth/sessions, submissions & review workflow, company memory, regulatory
knowledge base training, regulatory change monitoring, analytics, audit log.

Run:
  uvicorn python_fastapi.main:app --reload --port 8000
Docs at http://localhost:8000/docs
"""
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.database import init_db
from python_fastapi.routers import (
    auth as auth_router,
    submissions as submissions_router,
    memory as memory_router,
    kb as kb_router,
    reg_monitor as reg_monitor_router,
    analytics as analytics_router,
    notifications as notifications_router,
    audit as audit_router,
    settings as settings_router,
)

app = FastAPI(title="ComplyLine Compliance Platform API", version="1.0.0")

_origins = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/")
def root():
    return {"name": "ComplyLine API", "version": "1.0.0", "docs": "/docs"}


app.include_router(auth_router.router)
app.include_router(submissions_router.router)
app.include_router(memory_router.router)
app.include_router(kb_router.router)
app.include_router(reg_monitor_router.router)
app.include_router(analytics_router.router)
app.include_router(notifications_router.router)
app.include_router(audit_router.router)
app.include_router(settings_router.router)

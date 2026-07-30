# ComplyLine — Credit Card Compliance Platform

A full production compliance platform for credit card teams — AI-powered document analysis, review workflow, company memory conflict detection, regulatory change monitoring, analytics, and audit trail.

Backend: FastAPI REST API (Python). Frontend: React + Vite single-page app.

## Features

| Feature | Description |
|---------|-------------|
| 🔐 Multi-user auth | JWT sessions, role-based access: Admin, Compliance Officer, Legal, Submitter |
| 📋 Review workflow | Submit → Pending → Review → Approved/Rejected/Escalated |
| 🏢 Company Memory | Upload prior marketing/policies, auto-check for contradictions |
| 🧠 RAG Engine | Claude cites specific CFR sections using retrieved regulation text |
| 🛰️ Reg Monitor | Watches CFPB, Fed, FFIEC, OCC for regulatory changes — auto-alerts |
| 🔔 Notifications | In-app + Slack + Email alerts for reviews, decisions, reg changes |
| 📈 Analytics | Risk breakdown, top issues, submission trends, export reports |
| 📜 Audit Log | Every action logged with user, timestamp, and detail |
| ⚖️ 9 Regulations | UDAAP, TILA/Reg Z, ECOA/Reg B, FCRA, BSA/AML, PCI DSS, SCRA, Collections, SR 11-7 |
| 📥 Export | Color-coded DOCX reports, JSON findings |

## Quick Start

### 1. Backend (FastAPI)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and a random SECRET_KEY
# Generate one with: python -c "import secrets; print(secrets.token_hex(32))"

uvicorn python_fastapi.main:app --reload --port 8010
```

API docs at http://localhost:8010/docs

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL should point at the backend above
npm run dev
```

Open http://localhost:5173

**Demo login credentials (all passwords: password123):**
- admin@company.com — Admin (all access)
- compliance@company.com — Compliance Officer (review queue, decisions)
- legal@company.com — Legal Counsel (review, escalate)
- marketing@company.com — Submitter (submit docs, view own)

## First Run Checklist

1. Sign in as `compliance@company.com`
2. Go to **Train Regulations** → click the one-click preset buttons to load CFPB/Fed regulation text
3. Go to **Company Memory** → click "Bulk load Chase sample documents" to seed prior communications
4. Go to **Reg Monitor** → click "Load all default sources" → "Run Check Now"
5. Sign in as `marketing@company.com` → **Submit Document** → paste any marketing copy

## User Roles

| Role | Submit | Review Queue | Make Decisions | Analytics | Settings |
|------|--------|-------------|----------------|-----------|----------|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| Compliance | ✅ | ✅ | ✅ | ✅ | — |
| Legal | ✅ | ✅ | ✅ | ✅ | — |
| Submitter | ✅ | — | — | — | — |

## Project Structure

```
.
├── frontend/                    # React + Vite SPA
│   └── src/{pages,components,context,api}
├── python_fastapi/               # FastAPI REST API
│   ├── main.py                   # App entrypoint, CORS, router wiring
│   ├── auth.py                   # JWT sessions, role checks
│   ├── docx_generator.py         # Color-coded DOCX report export
│   └── routers/                  # auth, submissions, memory, kb, reg-monitor, analytics, notifications, audit, settings
├── core/
│   └── database.py               # SQLite: users, submissions, findings, reviews, audit
├── rag/
│   ├── knowledge_base.py         # Regulatory knowledge base (TF-IDF)
│   ├── rag_compliance.py         # Claude + RAG compliance checker
│   ├── company_memory.py         # Prior communications store
│   └── conflict_detector.py      # Contradiction detection engine
├── monitor/
│   └── reg_monitor.py            # Regulatory change monitor (daemon/CLI)
├── integrations/
│   └── notifier.py               # Slack + Email notification dispatcher
├── test-docs/                    # Chase-style sample documents for Company Memory
├── requirements.txt               # Backend dependencies
└── .env.example
```

## Regulatory Monitor (Background Daemon)

The same logic backing the in-app Reg Monitor page can also run standalone:

```bash
# Seed default watches for your company
python -m monitor.reg_monitor --seed "Acme Financial"

# Run one check cycle
python -m monitor.reg_monitor --run-once

# Run as daemon (checks every 24h)
python -m monitor.reg_monitor --daemon --interval 24
```

## REST API

Full interactive docs at `/docs` once the backend is running. Key routes:

```
POST   /api/auth/login
GET    /api/auth/me
POST   /api/submissions                 # submit + run compliance check
GET    /api/submissions                 # list (filtered by role/company)
GET    /api/submissions/{id}
POST   /api/submissions/{id}/review     # approve/reject/escalate
GET    /api/submissions/{id}/docx       # download report
GET    /api/memory/stats
POST   /api/memory/documents
GET    /api/kb/stats
POST   /api/kb/ingest-url
GET    /api/reg-monitor/watches
POST   /api/reg-monitor/run-check
GET    /api/analytics
GET    /api/audit-log
```

## Notification Setup

### Slack
1. Create an incoming webhook at api.slack.com/apps
2. Add `SLACK_WEBHOOK_URL` to `.env`
3. Go to Settings → Notifications → Test Slack

### Email
Add to `.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=compliance@company.com
```

## Deployment notes

- The backend uses SQLite + JSON-file vector stores (`data/`, `rag/company_db/`, `rag/json_db/`) — host it somewhere with a persistent disk (e.g. Render, Railway, Fly.io), not a pure serverless function platform.
- `pandoc` must be installed on the backend host for `.docx`/`.doc` text extraction.
- Set `FRONTEND_ORIGIN` (backend) and `VITE_API_URL` (frontend) to match wherever each is actually deployed.

## License
MIT

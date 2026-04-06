# Credit Card Compliance Platform v4

A full production compliance platform for credit card teams — AI-powered document analysis, review workflow, company memory conflict detection, regulatory change monitoring, analytics, and audit trail.

## Features

| Feature | Description |
|---------|-------------|
| 🔐 Multi-user auth | Role-based access: Admin, Compliance Officer, Legal, Submitter |
| 📋 Review workflow | Submit → Pending → Review → Approved/Rejected/Escalated |
| 🏢 Company Memory | Upload prior marketing/policies, auto-check for contradictions |
| 🧠 RAG Engine | Claude cites specific CFR sections using retrieved regulation text |
| 🛰️ Reg Monitor | Watches CFPB, Fed, FFIEC, OCC for regulatory changes — auto-alerts |
| 🔔 Notifications | In-app + Slack + Email alerts for reviews, decisions, reg changes |
| 📈 Analytics | Risk breakdown, top issues, submission trends, export reports |
| 📜 Audit Log | Every action logged with user, timestamp, and detail |
| ⚖️ 9 Regulations | UDAAP, TILA/Reg Z, ECOA/Reg B, FCRA, BSA/AML, PCI DSS, SCRA, Collections, SR 11-7 |
| 📥 Export | Color-coded DOCX reports, JSON findings, batch processing |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# 3. Run the platform
streamlit run ui/app.py
```

Open http://localhost:8501

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
compliance-agent/
├── ui/app.py                    # Main Streamlit platform (9 pages)
├── core/
│   └── database.py              # SQLite: users, submissions, findings, reviews, audit
├── rag/
│   ├── knowledge_base.py        # ChromaDB regulatory knowledge base
│   ├── rag_compliance.py        # Claude + RAG compliance checker
│   ├── company_memory.py        # Prior communications store
│   └── conflict_detector.py     # Contradiction detection engine
├── monitor/
│   └── reg_monitor.py           # Regulatory change monitor (daemon/CLI)
├── integrations/
│   └── notifier.py              # Slack + Email notification dispatcher
├── python-fastapi/              # REST API (all endpoints)
├── nodejs-express/              # Node.js equivalent
├── scripts/                     # CLI tools
├── test-docs/                   # Chase-style test documents
├── requirements.txt
└── .env.example
```

## Regulatory Monitor (Background Daemon)

```bash
# Seed default watches for your company
python -m monitor.reg_monitor --seed "Acme Financial"

# Run one check cycle
python -m monitor.reg_monitor --run-once

# Run as daemon (checks every 24h)
python -m monitor.reg_monitor --daemon --interval 24
```

## REST API

```bash
# Start the API
cd python-fastapi && uvicorn main:app --reload
# Docs at http://localhost:8000/docs

# Key endpoints:
POST /check/text          # Check text
POST /check/file          # Check uploaded file
POST /check/full          # Check + conflict detection in one call
POST /kb/ingest/url       # Add regulation from URL
POST /memory/add/file     # Add to company memory
GET  /memory/stats        # Company memory stats
DELETE /memory/document/{name}
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

## License
MIT

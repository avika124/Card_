# Credit Card Compliance Checker Agent

An AI-powered compliance checking agent that analyzes documents, images, and text against major credit card regulations and policies using the Anthropic Claude API.

## Regulations Covered

| Framework | Description |
|-----------|-------------|
| UDAAP | Unfair, Deceptive, or Abusive Acts or Practices |
| TILA / Reg Z / CARD Act | Truth in Lending Act |
| ECOA / Reg B | Equal Credit Opportunity Act |
| FCRA / Reg V | Fair Credit Reporting Act |
| BSA / AML / OFAC / CIP | Bank Secrecy Act / Anti-Money Laundering |
| PCI DSS | Payment Card Industry Data Security Standard |
| SCRA | Servicemembers Civil Relief Act |
| Collections Conduct | FDCPA / Collection Practices |
| SR 11-7 | Model Risk Management |

## Features

- **Document Upload** — PDF, DOCX, TXT analysis
- **Image Upload** — Claude reads text from scanned documents/images
- **Text Paste** — Direct text input for quick checks
- **Multi-regulation** — Check against any combination of 9 frameworks
- **Color-coded DOCX Output** — Generates corrected Word document with tracked changes:
  - 🟡 Yellow = Corrected/Changed
  - 🔴 Red strikethrough = Deleted
  - 🟢 Green = Added
  - ⬜ Gray = Unchanged
- **Severity Scoring** — High / Medium / Low / Pass per regulation
- **Remediation Phases** — Prioritized action plan (30 / 90 / 180 days)

## Available Implementations

| Folder | Stack | Best For |
|--------|-------|----------|
| `streamlit/` | Python + Streamlit | Quick internal tool, fastest to deploy |
| `python-fastapi/` | Python + FastAPI | REST API backend, production-grade |
| `nodejs-express/` | Node.js + Express | JavaScript teams, existing Node infra |
| `scripts/` | Python scripts | CLI usage, batch processing, automation |

## Quick Start

### Streamlit (Recommended for first run)
```bash
cd streamlit
pip install -r requirements.txt
cp .env.example .env   # Add your ANTHROPIC_API_KEY
streamlit run app.py
```

### FastAPI
```bash
cd python-fastapi
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

### Node.js / Express
```bash
cd nodejs-express
npm install
cp .env.example .env
node server.js
# Server at http://localhost:3000
```

### CLI Scripts
```bash
cd scripts
pip install -r requirements.txt
cp .env.example .env
python check.py --file path/to/document.pdf --regs udaap tila ecoa
python check.py --text "Your policy text here" --all
python generate_docx.py --findings findings.json --output corrected.docx
```

## Environment Variables

```env
ANTHROPIC_API_KEY=sk-ant-...
MODEL=claude-sonnet-4-20250514
MAX_TOKENS=4000
```

## Project Structure

```
compliance-agent/
├── README.md
├── .env.example
├── streamlit/
│   ├── app.py              # Main Streamlit app
│   ├── compliance.py       # Compliance checking logic
│   ├── docx_generator.py   # Color-coded DOCX generation
│   └── requirements.txt
├── python-fastapi/
│   ├── main.py             # FastAPI app + routes
│   ├── models.py           # Pydantic models
│   ├── compliance.py       # Compliance checking logic
│   ├── docx_generator.py   # DOCX generation
│   └── requirements.txt
├── nodejs-express/
│   ├── server.js           # Express server
│   ├── routes/
│   │   ├── check.js        # Compliance check route
│   │   └── docx.js         # DOCX generation route
│   ├── lib/
│   │   ├── compliance.js   # Claude API calls
│   │   └── docxGenerator.js
│   └── package.json
└── scripts/
    ├── check.py            # CLI compliance checker
    ├── generate_docx.py    # CLI DOCX generator
    ├── batch_check.py      # Batch processing
    └── requirements.txt
```

## License

MIT

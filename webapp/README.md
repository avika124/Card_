# ComplyLine — Web App (Standalone HTML)

A fully self-contained browser-based version of the Credit Card Compliance Platform.
No Python, no database, no server required for basic use.

## Files

| File | Purpose |
|------|---------|
| `ComplyLine_v4.html` | The full app — open in any browser |
| `server.js` | Local proxy server (Node.js) — fixes CORS for API calls |
| `server.py` | Local proxy server (Python) — alternative to server.js |
| `cloudflare-worker.js` | Free cloud proxy — deploy to workers.cloudflare.com |
| `start.bat` | Double-click launcher for Windows |
| `start.sh` | Double-click launcher for Mac / Linux |
| `assets/` | Logo files (SVG) |

---

## How to run

### Option 1 — Simplest: Chrome extension (no install)

1. Install **"Allow CORS: Access-Control-Allow-Origin"** from Chrome Web Store
2. Enable it (click icon → turns orange)
3. Open `ComplyLine_v4.html` in Chrome
4. Go to Settings → paste your Anthropic API key → Save

> Toggle the extension OFF when not using the app.

---

### Option 2 — Node.js local server (recommended)

**Requires:** Node.js — download free from [nodejs.org](https://nodejs.org)

```bash
# Put server.js and ComplyLine_v4.html in the same folder, then:
node server.js

# With your API key pre-loaded:
ANTHROPIC_API_KEY=sk-ant-... node server.js   # Mac/Linux
set ANTHROPIC_API_KEY=sk-ant-... && node server.js  # Windows
```

Browser opens automatically at `http://localhost:8080`

**Windows:** Double-click `start.bat`
**Mac/Linux:** Run `./start.sh`

---

### Option 3 — Python local server

**Requires:** Python 3.x — usually pre-installed on Mac/Linux

```bash
python3 server.py
# or
python server.py --key sk-ant-your-key
```

---

### Option 4 — Cloudflare Worker (free, no installs)

1. Go to [workers.cloudflare.com](https://workers.cloudflare.com) → sign up free
2. Create a new Worker → paste `cloudflare-worker.js`
3. Deploy — get a URL like `https://complyline.yourname.workers.dev`
4. In `ComplyLine_v4.html`, replace `https://api.anthropic.com/v1/messages`
   with `https://complyline.yourname.workers.dev/api/claude`
5. Open the HTML file directly in any browser

---

## Features

- ✅ **Submit documents** for compliance analysis (9 regulatory frameworks)
- ✅ **Company Memory** — upload prior marketing, policies, agreements
- ✅ **Conflict detection** — auto-checks new docs against prior communications
- ✅ **Regulatory Library** — store official regulations by agency (CFPB, Fed, OCC…)
- ✅ **Web Scraper** — fetch regulatory content from any URL + 12 preset sources
- ✅ **Daily scheduler** — auto-scrapes regulatory sources, generates change reports
- ✅ **Review workflow** — Pending → Review → Approve / Reject / Escalate
- ✅ **Notifications** — in-app alerts for high-risk submissions and reg changes
- ✅ **Analytics** — risk breakdown, top issues, submission history
- ✅ **Audit log** — every action logged with timestamp
- ✅ **Export** — JSON export for submissions, analytics, memory, audit log

## Data persistence

All data (checks, company memory, regulatory library, settings) is saved to
`localStorage` in your browser. Data persists across sessions on the same
machine and browser.

## API key

You need an Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com).

Enter it in the app under **Settings → API key**, or pre-load it via the
`ANTHROPIC_API_KEY` environment variable when running the local server.

---

## Regulations covered

| Code | Full name |
|------|-----------|
| UDAAP | Unfair, Deceptive, Abusive Acts or Practices |
| TILA / Reg Z / CARD Act | Truth in Lending Act |
| ECOA / Reg B | Equal Credit Opportunity Act |
| FCRA / Reg V | Fair Credit Reporting Act |
| BSA / AML / OFAC / CIP | Bank Secrecy Act |
| PCI DSS | Payment Card Industry Data Security Standard |
| SCRA | Servicemembers Civil Relief Act |
| Collections / FDCPA | Fair Debt Collection Practices Act |
| SR 11-7 | Model Risk Management (Federal Reserve) |

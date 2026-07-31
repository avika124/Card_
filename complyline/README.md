# ComplyLine — patches and web app

Fixes and companion tooling for the **Credit Card Compliance Agent**
(`compliance_engine`, `consistency_checker`, `revenue_optimizer`, `web_scraper`,
`regulatory_monitor`, `daily_scanner`, `report_generator`, `app`).

Nothing here replaces the agent. `patches/` repairs two defects in it;
`webapp/` is a standalone browser client that runs the same review flow without
a Python install.

---

## Start here

| Priority | File | What it fixes |
|---|---|---|
| **1** | `patches/json_extract.py` | The compliance engine's findings never reach the report. See below. |
| 2 | `patches/revenue_optimizer_patch.py` | Dead first-year fee cap, unquantified opportunities, an unsafe rationale. |
| 3 | `webapp/` | Browser client — no Python, no install. |

Read `patches/INTEGRATION.md` for the exact call sites to change.

---

## The defect that matters

`compliance_engine.py` and `consistency_checker.py` both extract Claude's reply with:

```python
re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
```

That pattern requires a markdown code fence. Both prompts end with *"Respond ONLY
with valid JSON in this exact format:"* — so the model returns bare JSON with no
fence, the pattern matches nothing, the parse raises, and the handler writes the
literal string `"Error parsing Claude response. Raw response saved."` into a
report field.

**Consequence:** on any run where this fires, the entire A1–J checklist produces
nothing. Findings that do appear come from `consistency_checker` alone.

**How to confirm it happened:** open a generated report and look for

- the string `Error parsing Claude response` anywhere in the body, and
- missing **Visual Verification**, **Operational Verification**, and
  **Checklist Review** sections — those arrays only ever come from the
  compliance engine.

Both are present in `compliance_report_20260415_151424.docx`.

The failure is silent by construction: the error text is written into a prose
field, so the report reads as complete.

`json_extract.py` parses bare JSON, fenced JSON, JSON after a preamble, nested
braces, braces inside string values, trailing commas, and output truncated at
`max_tokens`. It raises a typed `JSONExtractionError` instead of returning a
string, so a parse failure can never again be mistaken for analysis.

Run `python patches/json_extract.py` to see the old and new patterns compared
across every failure mode.

---

## Layout

```
complyline/
├── patches/
│   ├── json_extract.py              drop-in JSON extractor
│   ├── revenue_optimizer_patch.py   first-year cap, sizing, rationale
│   └── INTEGRATION.md               exact call-site replacements
├── webapp/
│   ├── ComplyLine.jsx               React client — runs inside Claude, no API key
│   ├── ComplyLine_v4.html           standalone browser client
│   ├── server.js                    local proxy (Node, no npm install)
│   ├── server.py                    local proxy (Python, stdlib only)
│   ├── cloudflare-worker.js         hosted proxy, free tier
│   ├── start.sh / start.bat         launchers
│   └── assets/                      logo set (SVG)
└── docs/
    ├── ARCHITECTURE.md              module map, data flow, folder conventions
    ├── FINDINGS.md                  full defect list with evidence
    ├── Compliance_Platform_Overview.pdf
    └── Compliance_Platform_Deck.pptx
```

---

## Web app

Three ways to run it, cheapest first.

**Inside Claude.** Open `webapp/ComplyLine.jsx` as an artifact. No API key, no
CORS, no install — artifacts call the API directly. Data persists per account.

**Locally with Node.** Put `server.js` and `ComplyLine_v4.html` in one folder:

```bash
node server.js          # http://localhost:8080
```

The proxy exists because browsers block direct calls to `api.anthropic.com`.
Opening the HTML file on its own produces `Failed to fetch`.

**Locally with Python.**

```bash
python3 server.py --key sk-ant-...
```

The web app covers document review, company memory with conflict detection, a
regulatory library, and pricing benchmarks. It does not run the scraper or the
daily scanner — those need a real process, so keep using the Python agent.

---

## Not fixed here

- `daily_scanner.py` ships with `your-email@gmail.com` and `your-app-password`
  as SMTP credentials. Scans run and write to `regulatory_updates/`; the alert
  email has almost certainly never sent. Supply real credentials or drop the
  email path in favour of reading `latest_alerts.json`.
- The revenue section computes `regulatory_violations_count` in isolation from
  the compliance findings, so a report can say "Regulatory Issues: 0" while
  section 3 lists eight. Worth wiring together.
- Late-fee safe harbors are indexed annually. The `$32 / $43` figures are the
  post-vacatur 2024 values; verify against the current threshold at mail date.

---

## Licence

Internal tooling. The compliance analysis it produces supports review work and
is not legal advice.

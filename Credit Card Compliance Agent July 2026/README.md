# Credit Card Compliance Agent — July 2026

Everything produced in the July 2026 working session on the Credit Card
Compliance Agent: two defect patches, a browser client, deployment scaffolding,
desktop tooling, and the architecture and defect documentation.

---

## Run the agent from this folder

This folder ships with the tooling but not the agent's eight Python modules —
those live in your existing folder and were never available to this session as
source, only as compiled `.pyc`.

**Double-click `setup_here.bat`.**

It finds your existing agent folder, copies the modules across, brings over your
reference documents and API key, places the patches where they need to be, and
launches. Your original folder is not modified — it stays as a fallback.

After that, this folder is the working agent and `run.bat` starts it.

```
setup_here.bat     once, to populate this folder
run.bat            every time after that
schedule_scanner.bat   once, as administrator, for the daily scan
```

---

## Read this first

`compliance_engine.py` and `consistency_checker.py` extract Claude's response
with a regex that requires a markdown code fence:

```python
re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
```

Both prompts instruct the model to return bare JSON. The pattern never matches,
the parse raises, and `"Error parsing Claude response. Raw response saved."` is
written into a report field as though it were analysis.

**Effect:** the A1–J checklist — the most valuable part of the system —
contributes nothing to reports. Findings that do appear come from the
consistency checker alone.

`patches/json_extract.py` fixes it. Two lines, two files. `setup_here.bat` puts
the file in place and tells you if the edit is still outstanding.

Full evidence in `docs/FINDINGS.md`.

---

## Contents

```
Credit Card Compliance Agent July 2026/
│
├── patches/                    apply to the agent
│   ├── json_extract.py         ← the critical fix
│   ├── revenue_optimizer_patch.py
│   └── INTEGRATION.md          exact before/after per call site
│
├── desktop/                    run it on Windows
│   ├── run.bat                 one-click setup and launch
│   ├── schedule_scanner.bat    registers the daily scan with Task Scheduler
│   └── README.md               runbook and failure modes
│
├── deploy/                     run it always-on
│   ├── Dockerfile
│   ├── render.yaml             web service + cron, shared disk
│   └── DEPLOY.md
│
├── webapp/                     browser client
│   ├── ComplyLine.jsx          runs inside Claude, no API key, carries the
│   │                           ported A1–H1 checklist
│   ├── ComplyLine_v4.html      standalone
│   ├── server.js / server.py   local CORS proxies
│   ├── cloudflare-worker.js    hosted proxy
│   └── assets/                 logo set
│
├── docs/
│   ├── ARCHITECTURE.md         module map from the compiled modules
│   ├── FINDINGS.md             seven defects, evidence, status
│   ├── Compliance_Platform_Overview.pdf
│   └── Compliance_Platform_Deck.pptx
│
├── brand/                      logo set (SVG)
└── test-documents/             seven synthetic documents with known defects
```

---

## Order of work

1. **`setup_here.bat`** — copies the agent modules, reference documents, and API
   key into this folder, places the patches, and launches. Once only.
2. **Apply the parse fix** — `patches/INTEGRATION.md`, two lines in two files.
   `setup_here.bat` tells you whether this is still outstanding.
3. **Verify** — run a document and confirm the report now has **Visual
   Verification**, **Operational Verification**, and **Checklist Review**
   sections. Those come only from the compliance engine.
4. **Load reference documents** into `input\marketing_copy\` and
   `input\policy_documents\` if `setup_here.bat` did not bring any across. The
   consistency checker compares against these; with empty folders it finds
   nothing and does not say why.
5. **`schedule_scanner.bat`** as administrator, for the daily regulatory scan.
6. Optionally apply `revenue_optimizer_patch.py`.
7. Optionally deploy — `deploy/DEPLOY.md`.

Stopping after step 4 gets you a working agent producing complete reports with
conflict detection.

---

## Defect summary

| # | Defect | Severity | Status |
|---|---|---|---|
| F1 | Compliance engine output never reaches the report | Critical | Patched |
| F2 | First-year fee cap defined but never read | High | Patched |
| F3 | Quasi-cash rationale rests on consumer misunderstanding | High | Patched |
| F4 | Opportunities unsized, so ranking is arbitrary | Medium | Patched |
| F5 | Revenue scorecard contradicts compliance findings | Medium | Open |
| F6 | Daily scanner has placeholder SMTP credentials | Medium | Open |
| F7 | Late fee safe harbors need annual re-verification | Low | Inherent |

---

## Test documents

`test-documents/` holds seven synthetic files with deliberate defects, for
checking the agent still catches what it should after a change:

| File | Expected |
|---|---|
| `chase_adverse_action_notice_template.txt` | HIGH — missing ECOA statement, wrong FCRA window |
| `chase_ink_collections_script.txt` | HIGH — FDCPA threatening language, no call-time limits |
| `chase_sapphire_reserve_rewards_terms.txt` | MED-HIGH — UDAAP points forfeiture, unilateral devaluation |
| `chase_sapphire_preferred_marketing.txt` | MEDIUM — APR missing from headline |
| `chase_freedom_unlimited_agreement.txt` | LOW-MED — penalty APR indefinite |
| `chase_freedom_rise_compliant_disclosure.txt` | PASS — clean baseline |
| `chase_sapphire_reserve_agreement.docx` | LOW — largely compliant |

The clean baseline matters as much as the others: a checker that flags
everything is as useless as one that flags nothing.

---

## Two corrections

Two criticisms raised against the revenue optimizer before the compiled modules
were available did not survive contact with the bytecode, and are recorded in
`docs/FINDINGS.md` so they are not repeated:

- **MAPR handling was said to be wrong.** It is not. The module has a `NEAR_CAP`
  branch stating correctly that the 36% ceiling includes ancillary product fees,
  credit insurance, and participation fees. It simply did not fire on the
  document being reviewed.
- **The 25% first-year cap was said to be missing.** The knowledge is present
  and correct. Only the wiring is absent.

Judging a module by a single report's output was the error in both cases.

---

*Compliance analysis produced by this tooling supports review work and is not
legal advice.*

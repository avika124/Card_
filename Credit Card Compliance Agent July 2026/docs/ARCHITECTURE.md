# Architecture

Reconstructed from the compiled modules (`*.pyc`, CPython 3.10 and 3.14). Source
was not available, so this describes observed structure — constants, prompts,
function names, and string tables — not line-level implementation.

---

## Modules

```
app.py                    Streamlit UI
│
├── compliance_engine.py       document vs. federal law
├── consistency_checker.py     document vs. your own prior documents
├── revenue_optimizer.py       pricing vs. market and regulatory ceilings
├── web_scraper.py             pulls issuer marketing pages
├── regulatory_monitor.py      pulls regulator sites
├── daily_scanner.py           schedules the monitor, emails alerts
└── report_generator.py        merges everything into DOCX
```

`app.py` imports: `run_compliance_check`, `run_compliance_check_on_text`,
`scan_input_folder`, `load_regulations`, `generate_reports`, `get_known_issuers`,
`auto_discover_from_url`, `KNOWN_ISSUERS`, `run_regulatory_scan`,
`get_latest_alerts`, `get_scan_history`, `get_source_list`, `get_all_source_ids`.

---

## compliance_engine

Nine frameworks: UDAAP (Dodd-Frank), TILA/Reg Z/CARD Act (12 CFR 1026),
ECOA/Reg B (1002), FCRA/Reg V (1022 + 16 CFR), BSA/AML/OFAC/CIP (31 CFR 1020),
PCI DSS, SCRA/MLA (32 CFR 232), FDCPA/Reg F (1006), SR 11-7.

Rules load from `regulations.json`. Analysis is a single Claude call carrying a
mandatory checklist the model must walk end to end:

| Group | Covers |
|---|---|
| **A1–A3** | Headline vs. footnote consistency; orphaned footnote symbols; prominent claims whose disclosure lives on a different piece |
| **B1–B9** | Schumer Box rows; "accurate as of [date]" per §1026.60(b)(4); late fee vs. safe harbor; payment allocation §1026.53; rate-increase triggers vs. §1026.55; 21-day grace §1026.5(b)(2)(ii); CFPB URL; balance method; penalty APR trigger and duration |
| **C1–C4** | FCRA prescreen — short notice type size (16 CFR 642.3(a)), long notice box and ≥12pt (642.3(b)), long notice content, firm-offer narrow grounds under §604(c) |
| **D1–D5** | Rewards claim footnote proximity per piece; benefit substantiation; definitive operational claims; urgency and exclusivity; prequalification vs. guaranteed approval |
| **E1–E4** | State equal-credit notices; geographic exclusions for disparate-impact review; prohibited-basis language; "subject to credit approval" |
| **F1–F2** | MLA disclosure per 32 CFR 232.6; MLA database check at origination |
| **G1–G3** | Multi-piece packages keyed off artwork codes (`-OE` envelope, `-LT` letter, `-FC` front cover, `-BS` buckslip, `-DS` disclosure); version-code consistency |
| **H1** | QR and URL destinations repeating required disclosures |
| **I** | Items text extraction cannot verify → `visual_verification_required` |
| **J** | Items needing external systems → `operational_verification_required` |

A **mandatory enumeration rule** requires every item to appear either as a
finding with `checklist_ref` set, or as an entry in `checklist_review` with a
PASS note — so nothing drops silently.

Finding shape: `regulation_id`, `regulation_name`, `checklist_ref`, `severity`,
`finding`, `excerpt`, `recommendation`, `confidence` (0–100).

Readers: PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX), with per-format
error strings when a library is absent. Retry uses separate exponential backoff
for API overload, rate limit, 5xx, and connection failure.

**Defect:** the JSON extraction regex requires a code fence the prompt guarantees
will not be there. See `docs/FINDINGS.md`.

---

## consistency_checker

Loads reference material from:

```
input/marketing_copy/       prior campaigns
input/policy_documents/     cardholder agreements, internal policy
scraping_info/              scraped competitor and issuer pages
regulatory_updates/         output of regulatory_monitor
```

Six conflict categories:

| Key | Meaning |
|---|---|
| `REGULATORY_VIOLATION` | Direct violation of federal regulation |
| `CROSS_DOC_CONFLICT` | Contradicts another marketing or policy document |
| `POLICY_MISMATCH` | Claim inconsistent with internal policy or agreement |
| `REGULATORY_CHANGE_IMPACT` | Affected by recent change, enforcement, or guidance |
| `DISCLOSURE_GAP` | Required disclosure present in policy docs, missing here |
| `NUMERICAL_INCONSISTENCY` | Conflicting APR, fee, rate, limit, or date |
| `TONE_RISK` | Language misleading relative to official disclosures |

Each finding carries the conflicting text from both sides plus the source
document name — which is what makes the output actionable rather than advisory.

Writes alerts to an `alerts/` directory.

---

## revenue_optimizer

Deterministic — regex extraction, no model call.

`TERM_PATTERNS` extracts ~30 terms: purchase APR range, cash advance APR, BT APR,
penalty APR, annual fee, late fee, returned payment fee, over-limit fee, BT fee
(percent and minimum), cash advance fee (percent and minimum), foreign
transaction fee, minimum interest charge, minimum payment formula and floor,
balance calculation method, cash back rate, signup bonus and spend threshold,
intro APR duration, grace period, variable margin range, plus booleans for
`quasi_cash_addressed` and `rewards_forfeiture_addressed`.

`classify_card_tier()` sorts the product into `no_fee`, `mid_fee`, `premium`, or
`super_premium`, each with typical ranges and named comparables.

`analyze_revenue_opportunities()` emits 17 findings, each with `current_value`,
`benchmark`, `regulatory_max`, `status`, `revenue_opportunity`, `recommendation`.

Status values: `GAP` / `BELOW_MARKET`, `AT_MARKET`, `ABOVE_MARKET`, `NEAR_CAP`,
`AT_CAP`, `EXCEEDS_CAP`.

`REGULATORY_MAXIMUMS` holds the MLA 36% MAPR cap (with the correct note that it
includes credit insurance, ancillary product fees, and application or
participation fees), CARD Act late fee safe harbors first and subsequent (with
the correct note that the CFPB's 2024 $8 rule was vacated by the Fifth Circuit
and the pre-vacatur harbors remain effective), the first-year fee cap at 25% of
the initial credit limit, the over-limit opt-in requirement, and state usury
variability with the Marquette exportation caveat.

Real ceiling checks fire for: late fee over safe harbor (`EXCEEDS_CAP`), purchase
APR approaching 36% MAPR (`NEAR_CAP`), grace period under 21 days (violation),
and two-cycle billing (prohibited under CARD Act §102(b)).

**Defects:** the 25% first-year cap constant is never read; opportunities are not
sized in dollars so a $45k lever sorts alongside a $1.35M one; the quasi-cash
rationale rests on consumer misunderstanding. All three patched.

---

## web_scraper

Auto-discovers card sub-pages from an issuer name or URL. Follows terms,
disclosure, rewards, and benefit links. Keys on phrases including
`balance transfer`, `cash advance`, `pre-approved`, `pre-qualified`. Ships a
`KNOWN_ISSUERS` map. Browser user-agent. Output to `scraping_info/`.

## regulatory_monitor

Nine agencies: CFPB, FTC, OCC, Federal Reserve, FDIC, FinCEN, NCUA, DOJ, PCI SSC.
Per-source named endpoints — for CFPB: Enforcement Actions, Rules & Policy, Final
Rules, Compliance & Guidance, Supervisory Highlights, Consumer Complaints.

State in `scrape_history.json`; alerts in `latest_alerts.json`. Change detection
diffs against the last scan.

## daily_scanner

Scheduled entry point for Windows Task Scheduler or cron. Scrapes all sources,
diffs, writes `regulatory_updates/`, and emails HIGH-priority changes.

**Defect:** SMTP credentials are placeholders (`your-email@gmail.com`,
`your-app-password`). Scans run; alert email does not send.

## report_generator

DOCX via python-docx. Sections: Executive Summary, Documents Analyzed, Detailed
Findings, By Issue Category, Category Summary, Visual Verification, Operational
Verification, Checklist Review, Revenue Optimization, Disclaimer.

The Visual Verification, Operational Verification, and Checklist Review sections
are fed **only** by `compliance_engine`. Their absence from a report is the
reliable signal that the parse defect fired on that run.

---

## Data flow

```
input/marketing_copy/     ─┐
input/policy_documents/   ─┤
scraping_info/            ─┼─→ consistency_checker ─┐
regulatory_updates/       ─┘                        │
        ↑                                           ├─→ report_generator → DOCX
        │                  document ─→ compliance_engine  │
regulatory_monitor                        │                │
        ↑                                 └─→ revenue_optimizer
   daily_scanner
```

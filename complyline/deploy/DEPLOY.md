# Running the whole agent

Four capabilities need a real process — a filesystem, outbound HTTP to arbitrary
sites, and a scheduler:

| Capability | Needs | Runs in a chat artifact? |
|---|---|---|
| Compliance engine | Claude API | Yes |
| Consistency checker | Claude API + reference files | Partly — paste instead of folders |
| Revenue optimizer | Regex only | Yes |
| **Web scraper** | Outbound HTTP, disk | **No** |
| **Regulatory monitor** | Outbound HTTP, disk | **No** |
| **Daily scanner** | Scheduler, disk, SMTP | **No** |
| **Report generator** | python-docx, disk | **No** |

Browsers block cross-origin requests, so a scraper cannot run in one. Chat
sessions are ephemeral, so nothing can be scheduled in one. Those four need a
host.

---

## Prerequisite

Everything here needs the **`.py` source files**, not the compiled `.pyc`.
Bytecode can be read for constants and prompts — that is how the architecture
was mapped — but it cannot be patched or deployed.

The eight files:

```
app.py                  compliance_engine.py    consistency_checker.py
revenue_optimizer.py    web_scraper.py          regulatory_monitor.py
daily_scanner.py        report_generator.py
```

Plus `regulations.json` and `requirements.txt`.

---

## Path A — Cowork (fastest)

Cowork is a desktop app with access to your actual folders. Point it at

```
C:\Users\khemu\OneDrive\Documents\Claude\Projects\Credit Card Compliance Agent
```

and the patches get applied in place, against real source, verified by running
the agent on a real document. No uploading, no splicing from markdown.

This is the shortest route from here to a working agent.

## Path B — Upload the source here

Attach the eight `.py` files plus `regulations.json` and `requirements.txt`.
Both patches get applied, the result comes back as a deployable package.

Slower than Cowork because every iteration is a round trip, but it works.

## Path C — Push the folder to GitHub

```bash
cd "C:\Users\khemu\OneDrive\Documents\Claude\Projects\Credit Card Compliance Agent"
git init
git add .
git commit -m "Credit Card Compliance Agent"
git remote add origin https://github.com/avika124/compliance-agent.git
git push -u origin main
```

Check `.gitignore` excludes `.env` and any file holding an API key before the
first commit. A key committed once stays in the history even after deletion.

---

## Then: deploy for always-on

`deploy/render.yaml` and `deploy/Dockerfile` are ready. Copy both to the repo
root and connect the repo at **render.com → New → Blueprint**.

You get two services on one shared disk:

- **complyline** — the Streamlit UI, always reachable at a URL
- **complyline-scan** — the daily scanner on cron, 11:00 UTC weekdays

The shared disk is the important part. The scanner writes to
`regulatory_updates/`, the consistency checker reads from it, and both survive a
redeploy. Without it every deploy wipes the scan history and the reference
corpus the checker compares against.

Set in the Render dashboard, not in the file:

```
ANTHROPIC_API_KEY   sk-ant-...
SMTP_HOST           smtp.gmail.com
SMTP_USER           your real sending address
SMTP_PASSWORD       app password, not the account password
ALERT_TO            where HIGH-priority alerts go
```

The SMTP variables replace the `your-email@gmail.com` / `your-app-password`
placeholders currently hardcoded in `daily_scanner.py`, which is why alert email
has never sent.

Cost is roughly $7/month per service on the starter plan plus disk. Cron services
bill only while running, so the scanner is close to free.

---

## Alternative hosts

**Railway** — same shape, slightly simpler UI. Cron via `railway.json`.

**Fly.io** — cheapest for a scheduler; `fly machine run --schedule daily`.

**Your own machine** — Windows Task Scheduler runs `daily_scanner.py` directly.
Free, but only scans while the machine is awake, and a laptop that sleeps
silently misses days.

---

## Order of work

1. **Apply `json_extract.py`.** The compliance engine has been contributing
   nothing to reports. Nothing else matters as much, and it is a two-line change
   in two files.
2. **Verify.** Run one document. Confirm the report now has Visual Verification,
   Operational Verification, and Checklist Review sections.
3. **Apply the revenue patch.** Wires up the dead first-year fee cap, sizes
   opportunities in dollars, fixes the quasi-cash rationale.
4. **Deploy.** Blueprint on Render, secrets in the dashboard.
5. **Confirm the scanner runs.** Check `regulatory_updates/` has fresh files the
   morning after the first cron fire.

Steps 1 and 2 are worth doing before anything else regardless of where it ends up
hosted — a deployed agent with a silent parse failure is a deployed agent
producing half-reports.

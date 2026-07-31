# Running the agent on your desktop

Windows. Assumes the agent lives at

```
C:\Users\khemu\OneDrive\Documents\Claude\Projects\Credit Card Compliance Agent
```

---

## First: your source is probably already there

The `.pyc` files you uploaded came out of a `__pycache__` folder, and Python only
ever writes `__pycache__` *inside* the folder holding the `.py` files it compiled.
So the source should be sitting one level up from it:

```
Credit Card Compliance Agent\
├── app.py                     ← these
├── compliance_engine.py
├── consistency_checker.py
├── revenue_optimizer.py
├── web_scraper.py
├── regulatory_monitor.py
├── daily_scanner.py
├── report_generator.py
├── regulations.json
├── requirements.txt
└── __pycache__\               ← the .pyc files came from here
```

Two builds exist — `cpython-310` and `cpython-314` — which means Python has run
on this machine under both versions. If `python --version` reports "not
recognized", the interpreter was uninstalled or removed from PATH, not that it
was never there.

---

## Setup

Copy `run.bat` into the agent folder, next to `app.py`, and double-click it.

It picks a Python (preferring 3.11), creates a `.venv` so the agent's
dependencies stay isolated, installs what is missing, creates the `input\`,
`regulatory_updates\`, `scraping_info\`, and `alerts\` folders, prompts once for
your API key and writes it to `.env`, then launches at
**http://localhost:8501**.

Safe to run again any time — it skips whatever is already done.

---

## Schedule the daily scan

`run.bat` gives you the UI. The regulatory monitor still needs something to wake
it up.

Copy `schedule_scanner.bat` into the same folder, right-click, **Run as
administrator**. It registers a Task Scheduler entry that runs
`daily_scanner.py` weekdays at 07:00.

Test it without waiting:

```cmd
schtasks /run /tn "ComplyLine Daily Scan"
```

Then look in `regulatory_updates\` for fresh files.

Worth knowing: a sleeping laptop misses its window and says nothing. Task
Scheduler can be told to run missed tasks on wake, but if the scan needs to be
dependable, host it — `deploy/DEPLOY.md` covers that.

---

## Apply the patches before you rely on the output

The agent runs fine unpatched. It just produces incomplete reports.

Copy `patches/json_extract.py` into the agent folder, then make the two-line
change described in `patches/INTEGRATION.md` — once in `compliance_engine.py`,
once in `consistency_checker.py`.

`run.bat` checks for this and prints a note if the old regex is still in place.

To confirm it worked, run one document and check the generated report for
**Visual Verification**, **Operational Verification**, and **Checklist Review**
sections. Those three come only from the compliance engine. If they are there,
the engine is contributing again.

---

## When it goes wrong

**`'python' is not recognized`** — not installed, or not on PATH. Get 3.11 from
python.org and tick "Add python.exe to PATH" during install.

**Dependency install fails with build errors** — you are on Python 3.13 or 3.14.
Several dependencies have no wheels for those yet. Install 3.11, delete the
`.venv` folder, run `run.bat` again.

**`ModuleNotFoundError: No module named 'fitz'`** — PyMuPDF is missing, so PDFs
cannot be read. `.venv\Scripts\python.exe -m pip install pymupdf`

**Port 8501 already in use** — an earlier instance is still running. Close it, or
`.venv\Scripts\python.exe -m streamlit run app.py --server.port=8502`

**"Error parsing Claude response" in a report** — the parse defect. See the
patches section above.

**OneDrive locks a file mid-write** — if the folder syncs while the scanner is
writing, you get intermittent permission errors. Either pause syncing during
scans, or move the agent outside the OneDrive tree and keep only the reports in
it.

---

## The easier route

Cowork is a desktop app with direct access to your folders. Point it at the agent
directory and the patches get applied in place, against real source, verified by
running the agent on a real document — instead of you copying edits out of a
markdown file.

Same fix for the problem you hit when I could not reach
`C:\Users\khemu\...` from this chat.

# Integration

Two patches, applied independently. Do `json_extract` first — it is the one that
changes what your reports contain.

---

## 1. `json_extract.py`

Fixes: the compliance engine's findings silently dropping out of every report.

### Install

Copy `json_extract.py` next to `compliance_engine.py` in your agent folder:

```
Credit Card Compliance Agent/
├── compliance_engine.py
├── consistency_checker.py
├── json_extract.py          ← here
└── ...
```

### Change 1 of 2 — `compliance_engine.py`

Find the JSON extraction inside the function that calls the API
(`analyze_with_claude`, or wherever the response is turned into a dict). It looks
roughly like this:

```python
# BEFORE
import re, json

match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
if match:
    result = json.loads(match.group(1))
else:
    result = {"assessment": "Error parsing Claude response. Raw response saved."}
```

Replace with:

```python
# AFTER
from json_extract import extract_json, JSONExtractionError

try:
    result = extract_json(response_text)
except JSONExtractionError as e:
    # Do NOT write this into a report field. A parse failure is a failure.
    logger.error(
        "Compliance analysis could not be parsed for %s: %s\nFirst 400 chars: %s",
        document_name, e, e.preview,
    )
    raise
```

If you would rather degrade than raise, make the failure visible in the report
rather than disguised as prose:

```python
except JSONExtractionError as e:
    logger.error("Parse failure for %s: %s", document_name, e)
    result = {
        "findings": [],
        "parse_failed": True,
        "assessment": (
            "ANALYSIS DID NOT COMPLETE — the model response could not be parsed. "
            "This document has NOT been reviewed against the checklist. Re-run."
        ),
    }
```

Then have `report_generator.py` check `parse_failed` and print a banner at the
top of the document rather than burying the message in section 4.

### Change 2 of 2 — `consistency_checker.py`

Same pattern, same replacement. Search for `` ``` `` in the file; there is one
occurrence.

### Verify

Run any document through the agent and confirm the generated report now contains
**Visual Verification**, **Operational Verification**, and **Checklist Review**
sections. Those arrays only ever come from the compliance engine — if they are
present, the engine's output is parsing.

---

## 2. `revenue_optimizer_patch.py`

Fixes three things in `revenue_optimizer.py`.

### Install

Copy `revenue_optimizer_patch.py` next to `revenue_optimizer.py`.

### At the top of `revenue_optimizer.py`

```python
from revenue_optimizer_patch import (
    check_first_year_fee_cap,
    size_opportunity,
    _finding_sort_key,
    QUASI_CASH_FINDING,
)
```

### Inside `analyze_revenue_opportunities()`

**a. Wire up the dead cap.** `REGULATORY_MAXIMUMS["card_act_fee_cap_first_year"]`
is defined with the correct 25% ratio and correct exclusions, but nothing reads
it. Add this after the findings list is assembled:

```python
cap_finding = check_first_year_fee_cap(extracted, credit_limit=credit_limit)
if cap_finding:
    findings.insert(0, cap_finding)   # violations lead
```

`credit_limit` is the **lowest initial line in the assignment table**, not the
average. The cap binds against the smallest line offered — a structure that
clears on $2,000 can still breach on $500. Add it as a parameter:

```python
def analyze_revenue_opportunities(text, product_name="", credit_limit=None, accounts=100_000):
```

**b. Size and sort.** Replace the final ordering with:

```python
findings = [size_opportunity(f, accounts) for f in findings]
findings.sort(key=_finding_sort_key)
```

For this to produce numbers, each below-market finding needs a `delta` — dollars
per incident for fee levers, percentage points for rate levers:

```python
findings.append({
    "item": "Late Payment Fee",
    ...
    "delta": safe_harbor_first - late_fee,   # e.g. 32 - 29 = 3
})
```

Without `delta` a finding reports `annual_impact_usd: 0` and flags itself as
unquantified rather than guessing.

**c. Swap the quasi-cash finding.** Replace the hardcoded dict with the import:

```python
if not extracted.get("quasi_cash_addressed"):
    findings.append(dict(QUASI_CASH_FINDING))
```

The recommendation is unchanged. The rationale no longer rests on customers not
noticing the cost — that argument is the abusive prong at 12 U.S.C. 5531(d)(2)(A)
and it is discoverable. Transaction economics carry the same conclusion safely.

### Also update the summary line

`revenue_opportunities_count` and `regulatory_violations_count` currently count
only within the revenue section. Have them inherit HIGH-severity findings from
the compliance and consistency results so a report cannot print
"Regulatory Issues: 0" above a section listing eight.

### Verify

```python
from revenue_optimizer_patch import check_first_year_fee_cap

# $1,000 line, $30/month → $360/yr against a $250 cap
r = check_first_year_fee_cap({"monthly_maintenance_fee": 30}, credit_limit=1000)
assert r["status"] == "EXCEEDS_CAP"
print(r["recommendation"])
# URGENT: first-year fees exceed the cap by $110. Either reduce qualifying fees
# to $250 or below, or raise the initial credit line to $1,440. ...
```

---

## Tuning

`INCIDENCE` in the patch holds conservative industry mid-points — the share of
accounts hitting each fee per year. Replace with your own portfolio's rates
before anyone treats a dollar figure as a forecast:

```python
INCIDENCE["Late Payment Fee"] = 0.22   # your actual annual delinquency incidence
```

`AVG_TICKET` converts a percentage-point change into dollars and should likewise
be set from your own transaction data.

# Findings

Defects in the Credit Card Compliance Agent, ordered by impact. Each carries the
evidence it was diagnosed from, so it can be re-verified independently.

---

## F1 — Compliance engine output never reaches the report

**Severity:** Critical · **Status:** Patched (`patches/json_extract.py`)

`compliance_engine.py` and `consistency_checker.py` extract the model response
with:

```python
re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
```

The pattern requires a markdown code fence. Both prompts end with *"Respond ONLY
with valid JSON in this exact format:"*, so the model returns bare JSON without a
fence. No match → parse raises → the handler writes
`"Error parsing Claude response. Raw response saved."` into a report field.

**Evidence**

1. The regex is present in both modules — confirmed in the 3.10 and 3.14 builds.
2. `compliance_report_20260415_151424.docx` §4.1 contains that exact string
   twice, in `Regulatory Assessment` and in `Assessment`.
3. That report has no Visual Verification, Operational Verification, or
   Checklist Review section. `report_generator` defines all three, and all three
   are fed only by `compliance_engine`.
4. All eight findings in that report carry consistency-checker category labels
   (Disclosure Gap, Numerical Inconsistency, Tone / Messaging Risk, Regulatory
   Change Impact). None carries a `checklist_ref`.

**Impact.** On any run where this fires, the A1–J checklist contributes nothing.
Item C2 — FCRA long notice boxed, ≥12pt, contrasting type — would have flagged
the Embark package. It appears as F6 in the independent review of the same
package and is absent from the generated report.

The failure is silent by construction: the error string lands in a prose field,
so the document reads as complete.

**Detection.** Search any generated report for `Error parsing Claude response`,
and check whether the three engine-only sections are present.

---

## F2 — First-year fee cap is a dead constant

**Severity:** High · **Status:** Patched (`patches/revenue_optimizer_patch.py`)

`REGULATORY_MAXIMUMS["card_act_fee_cap_first_year"]` is defined with the correct
0.25 ratio and the correct exclusion of penalty fees. `strings` finds exactly one
occurrence per build — the definition. Nothing in
`analyze_revenue_opportunities()` reads it.

**Impact.** No product is tested against 12 CFR 1026.52(a). A $1,000 line with a
$30 monthly fee charges $360 in year one against a $250 cap and passes the
revenue optimizer clean.

The patched check returns `EXCEEDS_CAP` with the two remediation paths: reduce
qualifying fees to $250, or raise the initial line to $1,440.

**Note.** The cap binds against the **lowest** initial line in the assignment
table, not the average.

---

## F3 — Quasi-cash rationale rests on consumer misunderstanding

**Severity:** High (legal exposure) · **Status:** Patched

The shipped `revenue_opportunity` text reads:

> "...properly classifying quasi-cash transactions as cash advances generates
> substantial revenue... **Consumers often use cards for wire transfers and
> gambling without realizing the higher cost.**"

That sentence describes revenue derived from a consumer's lack of understanding
of a material cost, which is the abusive prong at 12 U.S.C. 5531(d)(2)(A). It is
generated into a Word document that circulates internally and is discoverable.

**The recommendation itself is sound** — quasi-cash reclassification is standard
and defensible. Only the justification needs to change. The patched version
argues from transaction economics: no merchant recourse, no chargeback recovery,
immediate liquidity, higher first-payment-default rates. Same conclusion,
defensible basis.

---

## F4 — Opportunities are not sized, so ranking is arbitrary

**Severity:** Medium · **Status:** Patched

Findings say things like *"this is meaningful incremental fee revenue"* without a
number, and are emitted in evaluation order.

Sized against 100k accounts:

| Lever | Annual impact |
|---|---|
| Late payment fee, $29 → $32 | ~$45,000 |
| Variable margin, +1pp | ~$1,350,000 |

A 30× spread between two findings the report presents as peers. `size_opportunity()`
attaches `annual_impact_usd` and sorts violations first, then by dollars.

Incidence assumptions in the patch are conservative industry mid-points and
should be replaced with the portfolio's own rates.

---

## F5 — Revenue scorecard contradicts the compliance findings

**Severity:** Medium · **Status:** Open

`regulatory_violations_count` counts only within the revenue section. The April
15 report prints "Regulatory Issues: 0" in §5.1 while §3 lists eight compliance
findings on the same document, and §3.4 flags the package for emphasising "NO
ANNUAL FEE" against a 22.99–31.99% APR — immediately before §5 proposes raising
three fees.

**Fix.** Have the revenue summary inherit HIGH-severity findings from the
compliance and consistency results, and attach any relevant UDAAP flag to the
specific term it bears on.

---

## F6 — Daily scanner cannot send alerts

**Severity:** Medium · **Status:** Open

`daily_scanner.py` contains `your-email@gmail.com`, `smtp.gmail.com`, and
`your-app-password` as literals. Scans run and write to `regulatory_updates/`;
the HIGH-priority alert email has almost certainly never sent.

**Fix.** Move credentials to environment variables and fail loudly when unset, or
drop the email path and read `latest_alerts.json` from the UI.

---

## F7 — Late fee safe harbors need annual verification

**Severity:** Low · **Status:** Open (inherent)

The $32 / $43 figures are correct post-vacatur values and the module's note about
the Fifth Circuit vacating the CFPB's $8 rule is accurate. These thresholds index
annually.

**Fix.** Date-stamp the constant and warn when it is more than twelve months old
rather than treating it as static.

---

## What the review got wrong

Two criticisms raised against the revenue optimizer before the compiled modules
were available did not hold up:

**MAPR handling was said to be incorrect.** It is not. The module has a
`NEAR_CAP` branch whose remediation reads: *"Verify MLA database check at
origination; APR this close to 36% can breach MAPR cap when ancillary-product
fees, credit insurance, or participation fees are included."* That is correct and
more precise than the proposed replacement. It did not fire on Embark because
31.99% is not close enough to trigger it, so the report showed only the flattened
`regulatory_max` string.

**The 25% cap was said to be absent.** The knowledge is present and correct; only
the wiring is missing (F2).

Recorded because judging a module by one report's output was the error in both
cases, and the same mistake is easy to repeat.

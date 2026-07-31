"""
revenue_optimizer_patch.py
==========================
Drop-in additions for revenue_optimizer.py.

Three changes, in order of importance:

  1. check_first_year_fee_cap()
     REGULATORY_MAXIMUMS["card_act_fee_cap_first_year"] is defined in the module
     with the correct 25% ratio and the correct exclusions, but nothing in
     analyze_revenue_opportunities() ever reads it. It is a dead constant. This
     wires it up as a real EXCEEDS_CAP check.

  2. size_opportunity()
     Findings currently say things like "this is meaningful incremental fee
     revenue" without a number. On 100k accounts at a 15% delinquency rate, the
     $3 late-fee uplift is about $45k/yr — real, but two orders of magnitude
     below the quasi-cash and variable-margin levers it sorts alongside. Sizing
     every opportunity in annual dollars makes the ranking honest.

  3. QUASI_CASH_FINDING
     The shipped rationale reads: "Consumers often use cards for wire transfers
     and gambling without realizing the higher cost." That sentence describes
     revenue derived from consumer misunderstanding, which is the abusive prong
     at 12 U.S.C. 5531(d)(2)(A). The recommendation is sound; the justification
     needs to rest on transaction economics instead.

Integration
-----------
    from revenue_optimizer_patch import (
        check_first_year_fee_cap, size_opportunity, QUASI_CASH_FINDING,
    )

    # inside analyze_revenue_opportunities(), after the findings list is built:
    cap = check_first_year_fee_cap(extracted, credit_limit=credit_limit)
    if cap:
        findings.insert(0, cap)          # violations lead

    findings = [size_opportunity(f, accounts) for f in findings]
    findings.sort(key=_finding_sort_key)
"""

from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# 1. CARD Act first-year fee cap — 12 CFR 1026.52(a)
# ─────────────────────────────────────────────────────────────────────────────

# Fees counted toward the 25% cap. Penalty fees are excluded by 1026.52(a)(2):
# late payment, returned payment, and over-limit fees do not count.
FIRST_YEAR_COUNTED_FEES = (
    "annual_fee",
    "application_fee",
    "participation_fee",
    "setup_fee",
    "program_fee",
    "monthly_maintenance_fee",
    "authorized_user_fee",
)

FIRST_YEAR_EXCLUDED_FEES = (
    "late_fee",
    "returned_payment_fee",
    "overlimit_fee",
    "cash_advance_fee",       # transaction-based, not required to open/maintain
    "balance_transfer_fee",
    "foreign_transaction_fee",
)


def check_first_year_fee_cap(extracted: dict, credit_limit: Optional[float] = None) -> Optional[dict]:
    """
    Total fees a consumer must pay in the first year after account opening may
    not exceed 25% of the initial credit limit (12 CFR 1026.52(a)).

    Returns a finding dict in the module's existing shape, or None when the
    check cannot run or the product is within the cap with room to spare.

    `credit_limit` is the *initial* line. Extract it from the offer, or pass the
    lowest line in the assignment table — the cap binds against the smallest
    line offered, not the average.
    """
    if not credit_limit or credit_limit <= 0:
        return {
            "item": "First-Year Fee Cap (CARD Act)",
            "current_value": "Cannot evaluate — initial credit limit not found",
            "benchmark": "Total first-year fees at or below 25% of initial credit line",
            "regulatory_max": "12 CFR 1026.52(a) — 25% of initial credit limit",
            "status": "UNVERIFIED",
            "revenue_opportunity": (
                "BLOCKED — the cap cannot be tested without the initial credit line. "
                "Any fee increase is unsafe to recommend until it is."
            ),
            "recommendation": (
                "Supply the lowest initial credit line in the assignment table. The cap "
                "binds against the smallest line offered, so a fee structure that clears "
                "on a $2,000 line can still breach on a $500 line."
            ),
            "annual_impact_usd": 0,
        }

    charged = 0.0
    components = []
    for key in FIRST_YEAR_COUNTED_FEES:
        val = extracted.get(key)
        if val:
            try:
                amount = float(val)
            except (TypeError, ValueError):
                continue
            # monthly fees bill twelve times in the first year
            if "monthly" in key:
                amount *= 12
            charged += amount
            components.append(f"{key.replace('_', ' ')} ${amount:,.0f}")

    cap = credit_limit * 0.25
    headroom = cap - charged

    if charged == 0:
        return None  # no qualifying fees, cap is not in play

    breakdown = " + ".join(components)

    if charged > cap:
        overage = charged - cap
        return {
            "item": "First-Year Fee Cap (CARD Act)",
            "current_value": f"${charged:,.0f} in year one ({breakdown}) on a ${credit_limit:,.0f} line",
            "benchmark": f"${cap:,.0f} maximum (25% of ${credit_limit:,.0f})",
            "regulatory_max": "12 CFR 1026.52(a) — 25% of initial credit limit",
            "status": "EXCEEDS_CAP",
            "revenue_opportunity": "NEGATIVE — REGULATORY VIOLATION. Do not mail.",
            "recommendation": (
                f"URGENT: first-year fees exceed the cap by ${overage:,.0f}. Either reduce "
                f"qualifying fees to ${cap:,.0f} or below, or raise the initial credit line to "
                f"${charged / 0.25:,.0f}. Penalty fees (late, returned payment, over-limit) are "
                f"excluded from this calculation under 1026.52(a)(2) and cannot be used to "
                f"create headroom."
            ),
            "annual_impact_usd": 0,
        }

    if headroom < cap * 0.15:  # inside 15% of the ceiling
        return {
            "item": "First-Year Fee Cap (CARD Act)",
            "current_value": f"${charged:,.0f} of ${cap:,.0f} available ({breakdown})",
            "benchmark": f"${cap:,.0f} maximum (25% of ${credit_limit:,.0f})",
            "regulatory_max": "12 CFR 1026.52(a) — 25% of initial credit limit",
            "status": "NEAR_CAP",
            "revenue_opportunity": (
                f"CONSTRAINED — only ${headroom:,.0f} of fee headroom remains in year one. "
                f"Any annual, participation, or monthly fee increase must be tested against "
                f"this ceiling before it is proposed."
            ),
            "recommendation": (
                "Model any new recurring fee against the lowest initial line in the assignment "
                "table, not the average. Consider whether the fee can begin in month 13, which "
                "falls outside the first-year cap."
            ),
            "annual_impact_usd": 0,
        }

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Portfolio-sized opportunity quantification
# ─────────────────────────────────────────────────────────────────────────────

# Per-account annual incidence assumptions. Override per portfolio — these are
# conservative industry mid-points, not your book.
INCIDENCE = {
    "Late Payment Fee":             0.15,   # accounts incurring >=1 late fee/yr
    "Returned Payment Fee":         0.03,
    "Cash Advance Fee":             0.06,
    "Balance Transfer Fee":         0.08,
    "Foreign Transaction Fee":      0.12,
    "Minimum Interest / Finance Charge": 0.04,
    "Annual Fee":                   1.00,
    "Variable Margin (upper)":      0.45,   # share of accounts revolving
    "Purchase APR (upper bound)":   0.45,
}

# Average transaction size used to convert a percentage-point change to dollars.
AVG_TICKET = {
    "Cash Advance Fee":        500.0,
    "Balance Transfer Fee":  2_500.0,
    "Foreign Transaction Fee": 1_200.0,   # annual foreign spend per affected account
    "Variable Margin (upper)": 3_000.0,   # average revolving balance
    "Purchase APR (upper bound)": 3_000.0,
}


def size_opportunity(finding: dict, accounts: int = 100_000) -> dict:
    """
    Attach `annual_impact_usd` to a finding so opportunities can be ranked by
    what they are actually worth rather than by the order they were evaluated.

    Leaves any finding that already carries a non-zero impact untouched, and
    never assigns impact to a violation — a breach is remediation, not revenue.
    """
    item = finding.get("item", "")
    status = finding.get("status", "")

    if finding.get("annual_impact_usd"):
        return finding
    if status in ("EXCEEDS_CAP", "NEAR_CAP", "UNVERIFIED"):
        finding["annual_impact_usd"] = 0
        return finding
    if status not in ("BELOW_MARKET", "GAP"):
        finding["annual_impact_usd"] = 0
        return finding

    delta = finding.get("delta")  # set by the caller: $ per incident or pp of rate
    if delta is None:
        finding["annual_impact_usd"] = 0
        finding["impact_note"] = "Not quantified — supply `delta` to size this lever."
        return finding

    rate = INCIDENCE.get(item, 0.0)
    ticket = AVG_TICKET.get(item)

    if ticket:                                   # delta expressed in percentage points
        per_account = ticket * (float(delta) / 100.0)
    else:                                        # delta expressed in dollars per incident
        per_account = float(delta)

    impact = per_account * rate * accounts
    finding["annual_impact_usd"] = round(impact)
    finding["impact_note"] = (
        f"~${impact:,.0f}/yr across {accounts:,} accounts "
        f"(assumes {rate:.0%} incidence). Verify incidence against your own book."
    )
    return finding


def _finding_sort_key(finding: dict):
    """Violations first, then by annual dollars descending."""
    severity = {"EXCEEDS_CAP": 0, "NEAR_CAP": 1, "UNVERIFIED": 2}.get(finding.get("status"), 3)
    return (severity, -(finding.get("annual_impact_usd") or 0))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Quasi-cash finding — same recommendation, defensible rationale
# ─────────────────────────────────────────────────────────────────────────────

QUASI_CASH_FINDING = {
    "item": "Quasi-Cash / Cash-Like Transactions",
    "current_value": "Not explicitly addressed in this document",
    "benchmark": (
        "Industry standard: wire transfers, money orders, travelers checks, lottery, "
        "gambling/casino, P2P cash-out transfers, and cryptocurrency purchases treated "
        "as cash advances (cash advance APR, cash advance fee, no grace period)"
    ),
    "regulatory_max": "No federal cap — disclosure required in the Cardmember Agreement",
    "status": "GAP",
    "revenue_opportunity": (
        "HIGH — these transactions convert credit into cash or cash equivalents, so they "
        "carry the loss profile of a cash advance rather than a retail purchase: no "
        "merchant recourse, no chargeback recovery, immediate liquidity to the cardholder, "
        "and materially higher first-payment-default rates. Pricing them as retail "
        "purchases means the retail book subsidises them. Classifying them as cash "
        "advances aligns price to the risk being taken."
    ),
    "recommendation": (
        "Add an explicit Quasi-Cash / Cash-Like transaction section to the Cardmember "
        "Agreement and reference it from the Schumer Box. Typical categories: (1) money "
        "orders, wire transfers, cashier's checks, travelers checks; (2) lottery tickets "
        "and gambling; (3) cryptocurrency purchases; (4) P2P cash-out transfers; "
        "(5) overdraft protection transfers. Disclose plainly, at the point of the fee "
        "schedule, that the cash advance APR applies and no grace period is available — "
        "a customer who understands the cost before transacting is both the compliant "
        "outcome and the one that survives an exam. Maintain the MCC list operationally "
        "and review it as new payment types appear."
    ),
    "risk": (
        "Do not justify this change on customers being unaware of the cost. Revenue that "
        "depends on a consumer's lack of understanding of material costs is the abusive "
        "prong at 12 U.S.C. 5531(d)(2)(A), and the internal rationale is discoverable. "
        "The economics of the transaction are sufficient justification on their own."
    ),
    "annual_impact_usd": 0,   # set via size_opportunity() once volume is known
}

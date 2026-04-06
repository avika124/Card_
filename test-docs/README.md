# Chase Credit Card — Test & Training Documents

Synthetic documents modeled on publicly available Chase cardmember agreements
(CFPB database, Q3 2025) and chase.com marketing pages.
Used for training and testing the Credit Card Compliance Checker Agent.

## Documents

| File | Type | Purpose | Intentional Issues |
|------|------|---------|-------------------|
| `chase_freedom_unlimited_agreement.txt` | Cardholder Agreement | Full agreement with rates, fees, arbitration, SCRA | Penalty APR indefinite application (UDAAP watch) |
| `chase_sapphire_preferred_marketing.txt` | Marketing Copy | Product page / email copy | APR missing from promotional headline (TILA Reg Z §1026.16) |
| `chase_adverse_action_notice_template.txt` | Adverse Action Notice | Internal template | Missing ECOA statement; wrong FCRA dispute window (30 vs 60 days) |
| `chase_ink_collections_script.txt` | Collections Script | Call center training | FDCPA threatening language; no call-time restrictions |
| `chase_sapphire_reserve_rewards_terms.txt` | Rewards T&Cs | Ultimate Rewards program | Points forfeiture on closure (UDAAP); unilateral devaluation without notice |
| `chase_freedom_rise_compliant_disclosure.txt` | Product Disclosure | Largely compliant baseline | Intentionally clean — tests "pass" detection |
| `chase_sapphire_reserve_agreement.docx` | Cardholder Agreement | Full rich-format agreement | Includes SCRA, FCRA, ECOA, billing dispute, data security sections |

## Compliance Issues by Regulation

| Regulation | Document | Issue |
|-----------|---------|-------|
| TILA / Reg Z | Marketing copy | APR not in promotional headline (12 CFR 1026.16(b)) |
| UDAAP | Rewards terms | Unilateral point devaluation without notice |
| UDAAP | Rewards terms | Points forfeiture on voluntary account closure, no grace period |
| UDAAP | Rewards terms | Reduced Amazon redemption rate (0.8¢) not prominently disclosed |
| ECOA / Reg B | Adverse action | Missing required ECOA anti-discrimination statement |
| FCRA | Adverse action | 30-day dispute window stated instead of required 60 days |
| Collections (FDCPA) | Collections script | Threatening lawsuit/garnishment not authorized at this stage |
| Collections (FDCPA) | Collections script | No restriction on calling before 8 AM / after 9 PM |
| SCRA | Cardholder agreement | Compliant — included as positive example |
| PCI DSS | Sapphire agreement | Disclosure present — compliant example |

## Usage

### Run a single document through the compliance checker:
```bash
cd scripts
python check.py --file ../test-docs/chase_sapphire_preferred_marketing.txt --all
python check.py --file ../test-docs/chase_adverse_action_notice_template.txt --regs ecoa fcra
python check.py --file ../test-docs/chase_ink_collections_script.txt --regs collections udaap --docx report.docx
```

### Run all documents in batch:
```bash
python batch_check.py --dir ../test-docs --all --output-dir ./results --docx
```

### Expected results summary:
- `chase_freedom_rise_compliant_disclosure.txt` → Overall: **PASS / LOW**
- `chase_sapphire_preferred_marketing.txt` → Overall: **MEDIUM** (TILA headline issue)
- `chase_adverse_action_notice_template.txt` → Overall: **HIGH** (ECOA missing, FCRA wrong)
- `chase_ink_collections_script.txt` → Overall: **HIGH** (FDCPA violations)
- `chase_sapphire_reserve_rewards_terms.txt` → Overall: **MEDIUM–HIGH** (UDAAP)
- `chase_freedom_unlimited_agreement.txt` → Overall: **LOW–MEDIUM** (penalty APR)
- `chase_sapphire_reserve_agreement.docx` → Overall: **LOW–PASS** (largely compliant)

## Data Sources

These documents are synthetic but modeled on:
- CFPB Credit Card Agreement Database (public domain, Q3 2025):
  https://www.consumerfinance.gov/credit-cards/agreements/issuer/jpmorgan-chase-bank-national-association/
- Chase.com public product pages:
  https://creditcards.chase.com/
- Actual regulatory text: TILA (15 U.S.C. §1601), ECOA (15 U.S.C. §1691),
  FCRA (15 U.S.C. §1681), FDCPA (15 U.S.C. §1692), SCRA (50 U.S.C. §3901)

Not affiliated with JPMorgan Chase & Co. For testing purposes only.

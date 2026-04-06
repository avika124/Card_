"""
monitor/reg_monitor.py — Regulatory Change Monitor

Watches configured government URLs for content changes.
When a change is detected, notifies relevant users and flags
submissions that may be affected.

Run:
  python -m monitor.reg_monitor --run-once
  python -m monitor.reg_monitor --daemon  (runs every 24h)
"""

import os
import sys
import hashlib
import argparse
import time
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.database import (get_reg_watches, update_watch_hash,
                            create_notification, get_users, log_action, add_reg_watch)

HEADERS = {"User-Agent": "Mozilla/5.0 ComplianceMonitorBot/3.0"}

# ── Default regulatory sources to watch ───────────────────────────────────────

DEFAULT_WATCHES = [
    ("udaap",       "https://www.consumerfinance.gov/compliance/supervisory-guidance/unfair-deceptive-abusive-acts-or-practices-udaaps/", "CFPB UDAAP Guidance"),
    ("tila",        "https://www.consumerfinance.gov/rules-policy/regulations/1026/", "CFPB Regulation Z"),
    ("ecoa",        "https://www.consumerfinance.gov/rules-policy/regulations/1002/", "CFPB Regulation B"),
    ("fcra",        "https://www.consumerfinance.gov/rules-policy/regulations/1022/", "CFPB Regulation V"),
    ("collections", "https://www.consumerfinance.gov/rules-policy/regulations/1006/", "CFPB Regulation F"),
    ("scra",        "https://www.consumerfinance.gov/consumer-tools/military-financial-relief/", "CFPB SCRA Guide"),
    ("sr117",       "https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm", "Fed SR 11-7"),
    ("bsa",         "https://bsaaml.ffiec.gov/manual/Introduction/01", "FFIEC BSA/AML Manual"),
    ("pci",         "https://www.pcisecuritystandards.org/standards/pci-dss/", "PCI DSS Standards"),
    ("general",     "https://www.consumerfinance.gov/rules-policy/final-rules/", "CFPB Final Rules"),
    ("general",     "https://www.fdic.gov/news/financial-institution-letters/", "FDIC FIL Letters"),
    ("general",     "https://www.occ.gov/news-issuances/bulletins/", "OCC Bulletins"),
]


def _fetch_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.body or soup
        return main.get_text(separator="\n", strip=True)[:50000]
    except Exception as e:
        print(f"  Fetch error {url}: {e}")
        return ""


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def _notify_users(company: str, regulation: str, source_name: str, url: str):
    """Notify all compliance/admin users for a company about a regulatory change."""
    users = get_users(company)
    for user in users:
        if user["role"] in ("compliance", "legal", "admin"):
            create_notification(
                user_id=user["id"],
                ntype="reg_change",
                title=f"⚠️ Regulatory Change Detected — {regulation.upper()}",
                message=(
                    f"Changes detected on {source_name}. "
                    f"Review your approved materials for compliance with updated {regulation.upper()} guidance."
                ),
                link=url,
            )


def check_watch(watch: dict) -> bool:
    """Check one watch entry. Returns True if changed."""
    url = watch["source_url"]
    print(f"  Checking [{watch['regulation'].upper()}] {watch['source_name']}…")

    text = _fetch_text(url)
    if not text:
        return False

    new_hash = _hash(text)
    old_hash = watch.get("last_content_hash", "")

    if old_hash and new_hash != old_hash:
        print(f"  🔴 CHANGE DETECTED: {watch['source_name']}")
        update_watch_hash(watch["id"], new_hash)
        _notify_users(watch["company"], watch["regulation"], watch["source_name"], url)
        log_action(
            user_id="system", user_email="monitor@system",
            action="regulatory_change_detected",
            entity_type="reg_watch", entity_id=watch["id"],
            detail=f"{watch['source_name']} changed"
        )
        return True
    else:
        if not old_hash:
            print(f"  ⚪ First check — baseline recorded")
        else:
            print(f"  ✅ No change")
        update_watch_hash(watch["id"], new_hash)
        return False


def run_once(company: Optional[str] = None) -> dict:
    """Run one check cycle for all watches."""
    from core.database import get_reg_watches
    from core.database import get_users

    # Get all companies if not specified
    if company:
        companies = [company]
    else:
        users = get_users()
        companies = list(set(u["company"] for u in users))

    results = {"checked": 0, "changed": 0, "errors": 0}

    for co in companies:
        watches = get_reg_watches(co)
        if not watches:
            # Auto-seed default watches for new companies
            _seed_default_watches(co)
            watches = get_reg_watches(co)

        print(f"\n[{co}] Checking {len(watches)} regulatory sources…")
        for watch in watches:
            try:
                changed = check_watch(watch)
                results["checked"] += 1
                if changed:
                    results["changed"] += 1
                time.sleep(1.5)  # polite delay
            except Exception as e:
                print(f"  Error: {e}")
                results["errors"] += 1

    return results


def _seed_default_watches(company: str):
    """Add default regulatory watches for a company."""
    from core.database import get_users
    users = get_users(company)
    admin = next((u for u in users if u["role"] == "admin"), None)
    created_by = admin["id"] if admin else "system"

    existing = get_reg_watches(company)
    existing_urls = {w["source_url"] for w in existing}

    for regulation, url, name in DEFAULT_WATCHES:
        if url not in existing_urls:
            add_reg_watch(company, regulation, url, name, created_by)
    print(f"  Seeded {len(DEFAULT_WATCHES)} default regulatory watches for {company}")


def run_daemon(interval_hours: int = 24):
    """Run continuously, checking every interval_hours."""
    print(f"Regulatory Monitor Daemon started — checking every {interval_hours}h")
    while True:
        print(f"\n{'='*50}")
        print(f"  Check cycle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        results = run_once()
        print(f"\nCycle complete: {results['checked']} checked, {results['changed']} changed, {results['errors']} errors")
        print(f"Next check in {interval_hours} hours…")
        time.sleep(interval_hours * 3600)


# Allow Optional import
from typing import Optional

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regulatory Change Monitor")
    parser.add_argument("--run-once", action="store_true", help="Run one check cycle and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=24, help="Check interval in hours (daemon mode)")
    parser.add_argument("--company", type=str, help="Check only this company")
    parser.add_argument("--seed", type=str, help="Seed default watches for a company")
    args = parser.parse_args()

    from core.database import init_db
    init_db()

    if args.seed:
        _seed_default_watches(args.seed)
    elif args.run_once:
        results = run_once(args.company)
        print(f"\nDone: {results}")
    elif args.daemon:
        run_daemon(args.interval)
    else:
        parser.print_help()

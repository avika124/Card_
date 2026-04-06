#!/usr/bin/env python3
"""
check.py — CLI compliance checker
Usage:
  python check.py --text "Your policy text" --all
  python check.py --file document.pdf --regs udaap tila ecoa
  python check.py --file image.png --all --output findings.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "python-fastapi"))
from compliance import check_text, check_file, REGULATIONS

load_dotenv()

SEVERITY_ICONS = {"high": "🔴", "medium": "🟡", "low": "🟠", "pass": "🟢"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "pass": 3}


def print_results(result: dict, verbose: bool = True):
    overall = result.get("overall_risk", "unknown")
    icon = SEVERITY_ICONS.get(overall, "⚪")
    print(f"\n{'='*60}")
    print(f"  Overall Risk: {icon} {overall.upper()}")
    print(f"{'='*60}")
    print(f"\n{result.get('summary', '')}\n")

    findings = sorted(
        result.get("findings", []),
        key=lambda f: SEVERITY_ORDER.get(f.get("severity", "low"), 2)
    )

    counts = {"high": 0, "medium": 0, "low": 0, "pass": 0}
    for f in findings:
        counts[f.get("severity", "low")] = counts.get(f.get("severity", "low"), 0) + 1

    print(f"  🔴 High: {counts['high']}  🟡 Medium: {counts['medium']}  🟠 Low: {counts['low']}  🟢 Pass: {counts['pass']}\n")

    for f in findings:
        sev = f.get("severity", "low")
        icon = SEVERITY_ICONS.get(sev, "⚪")
        print(f"{'─'*60}")
        print(f"  {icon} [{sev.upper()}] {f.get('regulation', '')}")
        print(f"  {f.get('issue', '')}")
        if verbose:
            print(f"\n  {f.get('detail', '')}")
            if f.get("excerpt"):
                print(f"\n  📌 Excerpt: \"{f['excerpt']}\"")
            if f.get("recommendation"):
                print(f"\n  ✅ Recommendation: {f['recommendation']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Credit Card Compliance Checker CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", type=str, help="Text content to analyze")
    group.add_argument("--file", type=str, help="Path to file (PDF, DOCX, TXT, image)")

    reg_group = parser.add_mutually_exclusive_group(required=True)
    reg_group.add_argument("--all", action="store_true", help="Check against all regulations")
    reg_group.add_argument("--regs", nargs="+", choices=list(REGULATIONS.keys()),
                           help="Specific regulations to check")

    parser.add_argument("--output", type=str, help="Save findings JSON to file")
    parser.add_argument("--docx", type=str, help="Generate color-coded DOCX report at this path")
    parser.add_argument("--quiet", action="store_true", help="Only show issue titles, no detail")

    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set. Add to .env or export it.", file=sys.stderr)
        sys.exit(1)

    reg_ids = list(REGULATIONS.keys()) if args.all else args.regs
    print(f"\nChecking against: {', '.join(reg_ids)}")

    try:
        if args.text:
            print("Analyzing text input...")
            result = check_text(args.text, reg_ids)
        else:
            print(f"Analyzing file: {args.file}")
            result = check_file(args.file, reg_ids)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print_results(result, verbose=not args.quiet)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Findings saved to: {args.output}")

    if args.docx:
        from docx_generator import generate_compliance_docx
        docx_bytes = generate_compliance_docx(
            result,
            document_name=args.file or "Text Input",
            original_text_excerpt=args.text[:500] if args.text else "",
        )
        with open(args.docx, "wb") as f:
            f.write(docx_bytes)
        print(f"Color-coded DOCX saved to: {args.docx}")


if __name__ == "__main__":
    main()

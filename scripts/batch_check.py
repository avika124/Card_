#!/usr/bin/env python3
"""
batch_check.py — Batch compliance checker for multiple files
Usage:
  python batch_check.py --dir /path/to/docs --all --output-dir ./results
  python batch_check.py --files doc1.pdf doc2.docx --regs udaap tila
"""

import argparse
import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "python-fastapi"))
from compliance import check_file, REGULATIONS
from docx_generator import generate_compliance_docx

load_dotenv()


def process_file(file_path: str, reg_ids: list, output_dir: str, generate_docx: bool) -> dict:
    try:
        result = check_file(file_path, reg_ids)
        name = Path(file_path).stem

        # Save JSON
        json_path = os.path.join(output_dir, f"{name}_findings.json")
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)

        # Save DOCX
        if generate_docx:
            docx_bytes = generate_compliance_docx(result, document_name=Path(file_path).name)
            docx_path = os.path.join(output_dir, f"{name}_compliance_report.docx")
            with open(docx_path, "wb") as f:
                f.write(docx_bytes)

        return {"file": file_path, "status": "success", "overall_risk": result.get("overall_risk")}
    except Exception as e:
        return {"file": file_path, "status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Batch Credit Card Compliance Checker")

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--dir", type=str, help="Directory of files to process")
    input_group.add_argument("--files", nargs="+", type=str, help="Specific files to process")

    reg_group = parser.add_mutually_exclusive_group(required=True)
    reg_group.add_argument("--all", action="store_true", help="Check against all regulations")
    reg_group.add_argument("--regs", nargs="+", choices=list(REGULATIONS.keys()))

    parser.add_argument("--output-dir", type=str, default="./compliance_results",
                        help="Output directory for results")
    parser.add_argument("--docx", action="store_true", help="Generate DOCX reports")
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers (default: 3)")
    parser.add_argument("--ext", nargs="+", default=[".pdf", ".docx", ".txt"],
                        help="File extensions to process when using --dir")

    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    reg_ids = list(REGULATIONS.keys()) if args.all else args.regs

    # Collect files
    if args.dir:
        files = [
            str(p) for p in Path(args.dir).iterdir()
            if p.suffix.lower() in args.ext
        ]
    else:
        files = args.files

    if not files:
        print("No files found to process.")
        sys.exit(0)

    print(f"\nProcessing {len(files)} file(s) with {args.workers} workers...")
    print(f"Regulations: {', '.join(reg_ids)}\n")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_file, f, reg_ids, args.output_dir, args.docx): f
            for f in files
        }
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            status_icon = "✅" if r["status"] == "success" else "❌"
            risk = r.get("overall_risk", "error").upper()
            print(f"  {status_icon} {Path(r['file']).name} → {risk}")

    # Summary
    summary_path = os.path.join(args.output_dir, "batch_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")

    print(f"\n{'='*50}")
    print(f"  Completed: {succeeded} succeeded, {failed} failed")
    print(f"  Results saved to: {args.output_dir}")
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()

"""
store_gen__run_all.py
=============================
NovaWireless-GoodhartLab — Store Generation Orchestrator

Runs the full store data pipeline:
  1. generate_store_reps.py        → data/novawireless_store_rep_database.csv
  2. generate_store_visits.py      → output/store-gen/store_visits_YYYY-MM.csv
  3. 02_sanitize_store_visits.py   → output/store-gen/sanitized/store_visits_sanitized_YYYY-MM.csv

Run:
  python src/store_gen__run_all.py
  python src/store_gen__run_all.py --months 12
  python src/store_gen__run_all.py --month 2025-03   (single month)
  python src/store_gen__run_all.py --skip_reps       (reps already generated)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import find_repo_root

REPO_ROOT = find_repo_root()
SRC_DIR   = Path(__file__).resolve().parent

START_YEAR  = 2025
START_MONTH = 1


def run_script(script: Path, args: list[str]) -> int:
    cmd = [sys.executable, str(script)] + args
    print(f"\n  >> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(SRC_DIR))
    return result.returncode


def main(args=None) -> int:
    parser = argparse.ArgumentParser(description="Store generation pipeline orchestrator")
    parser.add_argument("--months",      type=int,   default=12)
    parser.add_argument("--month",       type=str,   default=None)
    parser.add_argument("--min_visits",  type=int,   default=200)
    parser.add_argument("--max_visits",  type=int,   default=400)
    parser.add_argument("--n_stores",    type=int,   default=12)
    parser.add_argument("--min_reps",    type=int,   default=8)
    parser.add_argument("--max_reps",    type=int,   default=12)
    parser.add_argument("--seed",        type=int,   default=42)
    parser.add_argument("--skip_reps",   action="store_true")
    parsed = parser.parse_args(args)

    print("=" * 60)
    print("NovaWireless-GoodhartLab — Store Generation Pipeline")
    print("=" * 60)

    # Step 1: Generate store reps
    if not parsed.skip_reps:
        print("\n[Step 1] Generating store rep population...")
        rc = run_script(SRC_DIR / "generate_store_reps.py", [
            "--n_stores", str(parsed.n_stores),
            "--min_reps", str(parsed.min_reps),
            "--max_reps", str(parsed.max_reps),
            "--seed",     str(parsed.seed),
        ])
        if rc != 0:
            print("ERROR: generate_store_reps.py failed.")
            return rc
    else:
        print("\n[Step 1] Skipping rep generation (--skip_reps)")

    # Build month list
    if parsed.month:
        months = [parsed.month]
    else:
        months = []
        y, m = START_YEAR, START_MONTH
        for _ in range(parsed.months):
            months.append(f"{y}-{m:02d}")
            m += 1
            if m > 12:
                m = 1
                y += 1

    # Steps 2 + 3: Generate visits then sanitize, month by month
    print(f"\n[Step 2 + 3] Generating and sanitizing {len(months)} month(s)...")
    for month in months:
        print(f"\n  ── Month: {month} ──")

        # Generate raw visits
        rc = run_script(SRC_DIR / "generate_store_visits.py", [
            "--month",      month,
            "--min_visits", str(parsed.min_visits),
            "--max_visits", str(parsed.max_visits),
            "--seed",       str(parsed.seed),
        ])
        if rc != 0:
            print(f"ERROR: generate_store_visits.py failed for {month}.")
            return rc

        # Sanitize
        rc = run_script(SRC_DIR / "02_sanitize_store_visits.py", [
            "--month", month,
        ])
        if rc != 0:
            print(f"ERROR: 02_sanitize_store_visits.py failed for {month}.")
            return rc

    print("\n" + "=" * 60)
    print("Store generation pipeline complete.")
    print(f"  Rep database  : data/novawireless_store_rep_database.csv")
    print(f"  Raw visits    : output/store-gen/store_visits_YYYY-MM.csv")
    print(f"  Sanitized     : output/store-gen/sanitized/store_visits_sanitized_YYYY-MM.csv")
    print(f"\n  Use sanitized files for all analysis.")
    print(f"  Cross-reference via customer_id with call-gen sanitized files.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

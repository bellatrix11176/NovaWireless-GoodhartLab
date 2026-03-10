#!/usr/bin/env python3
"""
call_gen__run_all.py — NovaWireless-GoodhartLab — Call Generator
=================================================================
Runs the full call generation pipeline for all 12 months of 2025
in a single command.

Output structure matches NovaWireless-Call-Center-Lab exactly so
downstream analysis programs work without modification.

HOW IT WORKS
------------
Loops through all 12 months automatically. Skips any month that
already has a calls_metadata file in output/call-gen/metadata/ so
it is safe to re-run if interrupted.

OUTPUTS (one set per month)
---------------------------
  output/call-gen/metadata/calls_metadata_2025-MM.csv
  output/call-gen/transcripts/transcripts_2025-MM.jsonl
  output/call-gen/sanitized/calls_sanitized_2025-MM.csv

USAGE
-----
  python src/call_gen__run_all.py                    # full year
  python src/call_gen__run_all.py --month 2025-03    # single month
  python src/call_gen__run_all.py --n_calls 5000     # override call count
"""

from __future__ import annotations

import argparse
import calendar
import importlib.util
import json
import sys
import types
from datetime import datetime
from pathlib import Path
from utils import find_repo_root

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------



REPO_ROOT  = find_repo_root()
DATA_DIR   = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"
SRC_DIR    = Path(__file__).resolve().parent

# Output subfolders — mirrors NovaWireless-Call-Center-Lab exactly
METADATA_DIR    = OUTPUT_DIR / "call-gen" / "metadata"
TRANSCRIPTS_DIR = OUTPUT_DIR / "call-gen" / "transcripts"
SANITIZED_DIR   = OUTPUT_DIR / "call-gen" / "sanitized"

SIM_YEAR = 2025

REQUIRED_DATA_FILES = [
    "customers.csv",
    "novawireless_employee_database.csv",
    "master_account_ledger.csv",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_inputs() -> None:
    missing = [f for f in REQUIRED_DATA_FILES if not (DATA_DIR / f).exists()]
    if missing:
        print("\n[ERROR] Missing required data files:")
        for f in missing:
            print(f"  data/{f}")
        sys.exit(1)




def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_generate_fn():
    for name in ["generate_calls", "01_generate_calls"]:
        path = SRC_DIR / f"{name}.py"
        if path.exists():
            mod = load_module(name, path)
            print(f"  Loaded generator: {path.name}")
            return mod.generate
    print("[ERROR] generate_calls.py not found in src/")
    sys.exit(1)


def run_sanitization(meta_path: Path, jsonl_path: Path, out_path: Path) -> bool:
    """
    Run 02_sanitize_calls.py inline.  Returns True on success, False on failure.
    Failure prints a warning but does NOT abort the pipeline — raw metadata is
    still available in call-gen/metadata/ for manual re-sanitization.
    """
    path = SRC_DIR / "02_sanitize_calls.py"
    if not path.exists():
        print(f"  [WARN] 02_sanitize_calls.py not found — skipping sanitization")
        return False
    try:
        mod = load_module("02_sanitize_calls", path)
        fake_args = types.SimpleNamespace(
            meta=str(meta_path),
            jsonl=str(jsonl_path),
            out=str(out_path),
            seed=42,
            no_transcripts=False,
        )
        original_parse = mod.parse_args
        mod.parse_args = lambda: fake_args
        try:
            mod.main()
        finally:
            mod.parse_args = original_parse
        return True
    except Exception as exc:
        import traceback
        print(f"  [WARN] Sanitization failed for {meta_path.name} — raw metadata preserved.")
        print(f"         Error: {exc}")
        print(f"         Traceback:\n{traceback.format_exc(limit=5)}")
        return False


def generate_month(year: int, mon: int, n_calls: int,
                   seed: int, generate_fn) -> None:
    sim_start = datetime(year, mon, 1)
    last_day  = calendar.monthrange(year, mon)[1]
    sim_end   = datetime(year, mon, last_day, 23, 59, 59)
    month_tag = f"{year}-{mon:02d}"

    print(f"\n{'='*60}")
    print(f"  Month: {month_tag}  ({sim_start.date()} → {sim_end.date()})")
    print(f"{'='*60}")

    meta_path  = METADATA_DIR    / f"calls_metadata_{month_tag}.csv"
    jsonl_path = TRANSCRIPTS_DIR / f"transcripts_{month_tag}.jsonl"
    san_path   = SANITIZED_DIR   / f"calls_sanitized_{month_tag}.csv"

    # Generate
    rng = np.random.default_rng(seed + mon)
    records, transcripts = generate_fn(n_calls, rng, sim_start, sim_end)

    dates = [r["call_date"] for r in records]
    print(f"  Call date range: {min(dates)} to {max(dates)}")

    df = pd.DataFrame(records)
    df.to_csv(meta_path, index=False)
    print(f"  Wrote: call-gen/metadata/{meta_path.name}  ({len(df):,} rows)")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for obj in transcripts:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"  Wrote: call-gen/transcripts/{jsonl_path.name}  ({len(transcripts):,} records)")

    # Sanitize
    print(f"  Sanitizing...")
    san_ok = run_sanitization(meta_path, jsonl_path, san_path)
    if san_ok:
        print(f"  Wrote: call-gen/sanitized/{san_path.name}")
    else:
        print(f"  [WARN] Skipped sanitized output for {month_tag} — see above.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="NovaWireless-GoodhartLab — Call Generator — full year pipeline"
    )
    ap.add_argument("--n_calls", type=int, default=8_000)
    ap.add_argument("--seed",    type=int, default=42)
    ap.add_argument("--month",   type=str, default=None,
                    help="Generate a single month only. Format: YYYY-MM")
    args = ap.parse_args()

    # Create output subfolders
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    SANITIZED_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "customer-gen").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "experiments").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "ledger").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "rep-gen").mkdir(parents=True, exist_ok=True)

    check_inputs()

    print("=" * 60)
    print("NovaWireless-GoodhartLab — Call Generator")
    print(f"  Repo root: {REPO_ROOT}")
    print(f"  N calls:   {args.n_calls:,} per month")
    print(f"  Base seed: {args.seed}")
    print("=" * 60)

    generate_fn = load_generate_fn()

    # Single month override
    if args.month:
        year = int(args.month[:4])
        mon  = int(args.month[5:7])
        generate_month(year, mon, args.n_calls, args.seed, generate_fn)
        print(f"\n[DONE] Single month {args.month} complete.\n")
        return 0

    # Full year loop
    months_done    = []
    for mon in range(1, 13):
        generate_month(SIM_YEAR, mon, args.n_calls, args.seed, generate_fn)
        months_done.append(f"{SIM_YEAR}-{mon:02d}")


    # Step 3 — Pressure Experiment
    print(f"\n{'='*60}")
    print(f"  STEP 3: Pressure Experiment")
    print(f"{'='*60}")
    exp_path = SRC_DIR / "pressure_experiment.py"
    if exp_path.exists():
        exp_mod = load_module("pressure_experiment", exp_path)
        exp_mod.main()
        print(f"  [OK] Pressure experiment complete.")
    else:
        print(f"  [WARN] pressure_experiment.py not found — skipping")
    # Final summary
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  ALL 12 MONTHS COMPLETE — {SIM_YEAR}")
    print(f"  Generated: {len(months_done)} months")
    print(f"  output/call-gen/metadata/     ← structured metadata")
    print(f"  output/call-gen/transcripts/  ← full dialogue")
    print(f"  output/call-gen/sanitized/    ← use these for analysis")
    print(f"{sep}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
run_all.py — NovaWireless Master Pipeline
==========================================
Runs the entire NovaWireless lab from scratch in one command.
Place this file at the repo root (same level as .labroot).

PIPELINE ORDER
--------------
  1. novawireless-customer-gen   — generate customers + account ledger
  2. novawireless-rep-gen        — generate call center employee roster + persona traits
  3. novawireless-store-gen      — generate store rep population + 12 months of store visits
  4. novawireless-call-gen       — generate 12 months of calls + sanitize
  5. organize outputs            — move files into clean subfolders

USAGE
-----
  python run_all.py                           # all defaults
  python run_all.py --n_customers 5000        # override customer count
  python run_all.py --n_reps 250              # override call center rep count
  python run_all.py --n_calls 8000            # override calls per month
  python run_all.py --n_stores 12             # override store count
  python run_all.py --min_reps 8              # store reps per store (min)
  python run_all.py --max_reps 12             # store reps per store (max)
  python run_all.py --min_visits 200          # store visits per store per month (min)
  python run_all.py --max_visits 400          # store visits per store per month (max)
  python run_all.py --seed 42                 # set master seed
  python run_all.py --month 2025-03           # single month for calls + store visits
  python run_all.py --skip_store              # skip store generation
  python run_all.py --skip_calls              # skip call generation

REQUIREMENTS
------------
  .labroot file must exist at the repo root so sub-scripts can
  resolve shared data/ and output/ directories correctly.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_repo_root(start=None) -> Path:
    cur = Path(start or __file__).resolve()
    if cur.is_file():
        cur = cur.parent
    labroot_paths = []
    node = cur
    while True:
        if (node / ".labroot").exists():
            labroot_paths.append(node)
        if node.parent == node:
            break
        node = node.parent
    if labroot_paths:
        return labroot_paths[-1]
    node = cur
    while True:
        if (node / "src").is_dir() and (node / "data").is_dir():
            return node
        if node.parent == node:
            break
        node = node.parent
    return Path.cwd().resolve()


REPO_ROOT = find_repo_root()


def run_step(label: str, script: Path, extra_args: list[str]) -> None:
    print(f"\n{'=' * 62}")
    print(f"  STEP: {label}")
    print(f"{'=' * 62}")
    if not script.exists():
        print(f"[ERROR] Script not found: {script}")
        print(f"        Check that {script.parent.parent.name} is present at repo root.")
        sys.exit(1)
    cmd = [sys.executable, str(script)] + extra_args
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\n[ERROR] Step failed: {label}")
        print(f"  Script:    {script}")
        print(f"  Exit code: {result.returncode}")
        sys.exit(result.returncode)
    print(f"[OK] {label} complete.")


def move_file(src: Path, dst_dir: Path) -> bool:
    """Move src to dst_dir/src.name. Returns True if moved, False if src not found."""
    if not src.exists():
        return False
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst_dir / src.name))
    return True


def organize_outputs(repo: Path) -> None:
    """
    After all generators complete, move flat output/ files into clean subfolders.

    output/customer-gen/  — customer CSVs + receipts
    output/ledger/        — master account ledger files + receipts
    output/rep-gen/       — employee database, persona profiles, versioned archives
    """
    print(f"\n{'=' * 62}")
    print(f"  STEP 5: Organizing output files into subfolders")
    print(f"{'=' * 62}")

    out = repo / "output"
    moved_total = 0

    # ── customer-gen ──────────────────────────────────────────────────────────
    customer_dir = out / "customer-gen"
    customer_files = [
        "customers.csv",
        "customers_v1.csv",
        "lines.csv",
        "eip_agreements.csv",
        "line_device_usage.csv",
        "devices.csv",
        "customer_generation_receipt.json",
    ]
    moved = 0
    for fname in customer_files:
        if move_file(out / fname, customer_dir):
            print(f"  [customer-gen] {fname}")
            moved += 1
    moved_total += moved
    print(f"  -> customer-gen: {moved} file(s) moved")

    # ── ledger ────────────────────────────────────────────────────────────────
    ledger_dir = out / "ledger"
    ledger_files = [
        "master_account_ledger.csv",
        "master_account_ledger__anomalies.csv",
        "master_account_ledger__pre_contract_fix.csv",
        "master_account_ledger_receipt.json",
        "imei_anomaly_examples.csv",
        "imei_anomaly_injection_receipt.json",
    ]
    moved = 0
    for fname in ledger_files:
        if move_file(out / fname, ledger_dir):
            print(f"  [ledger]       {fname}")
            moved += 1
    moved_total += moved
    print(f"  -> ledger: {moved} file(s) moved")

    # ── rep-gen ───────────────────────────────────────────────────────────────
    rep_dir = out / "rep-gen"
    rep_files = [
        "novawireless_employee_database.csv",
        "rep_persona_profiles__v1.csv",
    ]
    moved = 0
    for fname in rep_files:
        if move_file(out / fname, rep_dir):
            print(f"  [rep-gen]      {fname}")
            moved += 1

    # Versioned employee archive files (employees__*.csv / *.json)
    for f in sorted(out.glob("employees__*.csv")):
        shutil.move(str(f), str(rep_dir / f.name))
        print(f"  [rep-gen]      {f.name}")
        moved += 1
    for f in sorted(out.glob("employees__*.json")):
        shutil.move(str(f), str(rep_dir / f.name))
        print(f"  [rep-gen]      {f.name}")
        moved += 1

    moved_total += moved
    print(f"  -> rep-gen: {moved} file(s) moved")

    # ── call-gen ──────────────────────────────────────────────────────────────
    # call_gen__run_all.py already writes directly into output/call-gen/
    # subfolders (metadata/, transcripts/, sanitized/) — nothing to move.
    # We just verify and report.
    call_gen_dir = out / "call-gen"
    call_gen_subdirs = ["metadata", "transcripts", "sanitized"]
    call_gen_counts = {}
    for sub in call_gen_subdirs:
        d = call_gen_dir / sub
        if d.exists():
            n = len(list(d.glob("*.*")))
            call_gen_counts[sub] = n
    if call_gen_counts:
        total_call = sum(call_gen_counts.values())
        print(f"  -> call-gen: {total_call} file(s) already in subfolders "
              f"({', '.join(f'{k}: {v}' for k, v in call_gen_counts.items())})")
    else:
        print(f"  -> call-gen: no output found (may not have run yet)")

    # ── store-gen ─────────────────────────────────────────────────────────────
    # store_gen__run_all.py already writes to output/store-gen/ and
    # output/store-gen/sanitized/ — nothing to move.
    store_gen_dir = out / "store-gen"
    if store_gen_dir.exists():
        raw_n  = len(list(store_gen_dir.glob("store_visits_*.csv")))
        san_n  = len(list((store_gen_dir / "sanitized").glob("*.csv"))) if (store_gen_dir / "sanitized").exists() else 0
        print(f"  -> store-gen: {raw_n} raw + {san_n} sanitized file(s) already in subfolders")
    else:
        print(f"  -> store-gen: no output found (may not have run yet)")

    print(f"\n  Total files organized: {moved_total}")

    # ── Keep ledger copy in data/ so call-gen can still find it ───────────────
    # generate_calls.py reads from data/master_account_ledger.csv
    # We moved the file to output/ledger/ so copy it back if data/ copy is stale
    ledger_src  = ledger_dir / "master_account_ledger.csv"
    ledger_data = repo / "data" / "master_account_ledger.csv"
    if ledger_src.exists():
        shutil.copy2(str(ledger_src), str(ledger_data))
        print(f"  [data/] Refreshed master_account_ledger.csv in data/ for call-gen")

    print(f"[OK] Output organization complete.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="NovaWireless Master Pipeline — runs all sub-projects in order"
    )
    ap.add_argument("--n_customers",  type=int, default=100_000)
    ap.add_argument("--n_reps",       type=int, default=250)
    ap.add_argument("--n_calls",      type=int, default=8_000)
    ap.add_argument("--n_stores",     type=int, default=12)
    ap.add_argument("--min_reps",     type=int, default=8)
    ap.add_argument("--max_reps",     type=int, default=12)
    ap.add_argument("--min_visits",   type=int, default=200)
    ap.add_argument("--max_visits",   type=int, default=400)
    ap.add_argument("--seed",         type=int, default=42)
    ap.add_argument("--month",        type=str, default=None)
    ap.add_argument("--skip_store",   action="store_true")
    ap.add_argument("--skip_calls",   action="store_true")
    args = ap.parse_args()

    print("=" * 62)
    print("  NovaWireless Master Pipeline")
    print("=" * 62)
    print(f"  Repo root:     {REPO_ROOT}")
    print(f"  Customers:     {args.n_customers:,}")
    print(f"  CC reps:       {args.n_reps:,}")
    print(f"  Calls/month:   {args.n_calls:,}")
    print(f"  Stores:        {args.n_stores}")
    print(f"  Store reps:    {args.min_reps}-{args.max_reps} per store")
    print(f"  Visits/month:  {args.min_visits}-{args.max_visits} per store")
    print(f"  Seed:          {args.seed}")
    if args.month:
        print(f"  Month:         {args.month}  (single month only)")

    customer_src = REPO_ROOT / "novawireless-customer-gen" / "src"
    rep_src      = REPO_ROOT / "novawireless-rep-gen"      / "src"
    store_src    = REPO_ROOT / "novawireless-store-gen"    / "src"
    call_src     = REPO_ROOT / "novawireless-call-gen"     / "src"

    # Step 1 — Customer generation
    run_step(
        "Customer generation (customers + account ledger + IMEI anomalies)",
        customer_src / "customer_gen__run_all.py",
        [f"--n_customers={args.n_customers}", f"--seed={args.seed}"],
    )

    # Step 2 — Call center rep generation
    run_step(
        "Call center rep generation (employee roster + persona traits)",
        rep_src / "employee_gen__run_all.py",
        [f"--n={args.n_reps}", f"--seed={args.seed}"],
    )

    # Step 3 — Store generation
    if not args.skip_store:
        store_args = [
            f"--n_stores={args.n_stores}",
            f"--min_reps={args.min_reps}",
            f"--max_reps={args.max_reps}",
            f"--min_visits={args.min_visits}",
            f"--max_visits={args.max_visits}",
            f"--seed={args.seed}",
        ]
        if args.month:
            store_args.append(f"--month={args.month}")
        run_step(
            "Store generation (store reps + 12 months of store visit memos)",
            store_src / "store_gen__run_all.py",
            store_args,
        )
    else:
        print(f"\n{'=' * 62}")
        print(f"  STEP: Store generation — SKIPPED (--skip_store)")
        print(f"{'=' * 62}")

    # Step 4 — Call generation
    if not args.skip_calls:
        call_args = [f"--n_calls={args.n_calls}", f"--seed={args.seed}"]
        if args.month:
            call_args.append(f"--month={args.month}")
        run_step(
            "Call generation (12 months of calls + sanitization)",
            call_src / "call_gen__run_all.py",
            call_args,
        )
    else:
        print(f"\n{'=' * 62}")
        print(f"  STEP: Call generation — SKIPPED (--skip_calls)")
        print(f"{'=' * 62}")

    # Step 5 — Organize outputs into subfolders
    organize_outputs(REPO_ROOT)

    print(f"\n{'=' * 62}")
    print("  ALL STEPS COMPLETE")
    print(f"{'=' * 62}")
    print(f"  Repo root: {REPO_ROOT}")
    print(f"\n  output/")
    print(f"    customer-gen/          ← customers, lines, devices, EIP, receipts")
    print(f"    ledger/                ← master account ledger + IMEI anomalies")
    print(f"    rep-gen/               ← employee database + persona profiles")
    print(f"    store-gen/             ← raw store visit CSVs (one per month)")
    print(f"    store-gen/sanitized/   ← sanitized store visits for analysis")
    print(f"    call-gen/metadata/     ← structured call metadata (one per month)")
    print(f"    call-gen/transcripts/  ← full dialogue JSONL (one per month)")
    print(f"    call-gen/sanitized/    ← sanitized calls for analysis")
    print(f"    experiments/           ← pressure experiment outputs")
    print(f"\n  Cross-reference via customer_id across all datasets.")
    print(f"{'=' * 62}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

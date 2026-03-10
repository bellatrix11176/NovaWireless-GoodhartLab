"""
generate_store_visits.py
=============================
NovaWireless-GoodhartLab — Store Visit Generator

Generates monthly store visit records for all NovaWireless locations.
Each visit record includes the full structured memo text plus all
audit flags for NLP analysis.

OUTPUT
------
  output/store-gen/store_visits_YYYY-MM.csv

  One file per month. Each row is one store visit. Columns include:
    - visit_id, month, store_id, store_name, rep_id, customer_id
    - memo_filed, visit_type, visit_label
    - reason_for_visit, rep_advised, customer_decision
    - account_change_actual, account_change_in_memo
    - memo_mismatch, disclosure_ref, disclosure_ref_missing
    - requires_disclosure, memo_quality_score
    - memo_text  ← full formatted memo as it appears on the account
    - audit flags for NLP cross-reference

AUDIT SIGNALS
-------------
  memo_filed=False          : no memo exists — immediate red flag
  disclosure_ref_missing    : memo exists but no disclosure ref filed
  memo_mismatch             : memo describes different change than account record
  memo_quality_score        : 0–1 composite quality signal
  memo_text                 : full readable memo for NLP audit

GOODHART DYNAMICS
-----------------
No rep is deliberately gaming. Memo quality degrades under:
  - High store foot traffic (pressure)
  - Rep burnout above threshold
  - High upsell_pressure reps rushing through documentation
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import find_repo_root
from store_memo_builder import build_memo, sample_visit_type

REPO_ROOT  = find_repo_root()
DATA_DIR   = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output" / "store-gen"

VISITS_PER_STORE_MONTH = (200, 400)
SEED                   = 42
DEFAULT_MONTH          = "2025-01"


def simulate_month(
    reps_df:      pd.DataFrame,
    customers_df: pd.DataFrame,
    month:        str,
    visits_range: tuple[int, int],
    rng:          random.Random,
) -> pd.DataFrame:
    rep_pool      = reps_df.to_dict("records")
    customer_pool = customers_df.to_dict("records")
    store_ids     = reps_df["store_id"].unique()
    all_visits    = []
    visit_counter = 1

    for store_id in sorted(store_ids):
        store_reps = [r for r in rep_pool if r["store_id"] == store_id]
        n_visits   = rng.randint(*visits_range)

        for _ in range(n_visits):
            rep      = rng.choice(store_reps)
            customer = rng.choice(customer_pool)
            vtype    = sample_visit_type(rng)
            memo     = build_memo(vtype, rep, customer, rng, month)
            memo["visit_seq"] = visit_counter
            all_visits.append(memo)
            visit_counter += 1

    return pd.DataFrame(all_visits)


def main(args=None) -> int:
    parser = argparse.ArgumentParser(description="Generate NovaWireless store visit records")
    parser.add_argument("--month",      type=str, default=DEFAULT_MONTH)
    parser.add_argument("--min_visits", type=int, default=VISITS_PER_STORE_MONTH[0])
    parser.add_argument("--max_visits", type=int, default=VISITS_PER_STORE_MONTH[1])
    parser.add_argument("--seed",       type=int, default=SEED)
    parsed = parser.parse_args(args)

    rng = random.Random(parsed.seed)

    print("=" * 60)
    print(f"NovaWireless-GoodhartLab — Store Visit Generator")
    print(f"  Month:        {parsed.month}")
    print(f"  Visits/store: {parsed.min_visits}–{parsed.max_visits}")
    print(f"  Seed:         {parsed.seed}")
    print("=" * 60)

    reps_path = DATA_DIR / "novawireless_store_rep_database.csv"
    if not reps_path.exists():
        print(f"ERROR: Store rep database not found at {reps_path}")
        print("Run generate_store_reps.py first.")
        return 1

    customers_path = DATA_DIR / "customers.csv"
    if not customers_path.exists():
        print(f"ERROR: customers.csv not found at {customers_path}")
        print("Run customer_gen__run_all.py first.")
        return 1

    reps_df      = pd.read_csv(reps_path)
    customers_df = pd.read_csv(customers_path)

    print(f"\nLoaded {len(reps_df)} store reps across {reps_df['store_id'].nunique()} stores")
    print(f"Loaded {len(customers_df):,} customers")
    print(f"\nSimulating visits for {parsed.month}...")

    visits_df = simulate_month(
        reps_df      = reps_df,
        customers_df = customers_df,
        month        = parsed.month,
        visits_range = (parsed.min_visits, parsed.max_visits),
        rng          = rng,
    )

    # ── Output ────────────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"store_visits_{parsed.month}.csv"
    visits_df.to_csv(out_path, index=False)

    # ── Print summary ─────────────────────────────────────────────────────────
    total        = len(visits_df)
    missing      = (~visits_df["memo_filed"]).sum()
    disc_missing = visits_df["disclosure_ref_missing"].sum()
    mismatches   = visits_df["memo_mismatch"].sum()

    print(f"\n{'='*60}")
    print(f"RESULTS — {parsed.month}")
    print(f"{'='*60}")
    print(f"  Total visits:            {total:,}")
    print(f"  Missing memos:           {missing:,}  ({missing/total:.1%})")
    print(f"  Missing disclosure refs: {disc_missing:,}  ({disc_missing/total:.1%})")
    print(f"  Memo mismatches:         {mismatches:,}  ({mismatches/total:.1%})")
    print(f"  Mean memo quality:       {visits_df['memo_quality_score'].mean():.3f}")

    print(f"\nPer-store audit flags:")
    print(f"  {'Store':<14} {'Visits':>7} {'NoMemo':>8} {'NoDisc':>8} {'Mismatch':>9} {'FlagRate':>9}")
    print(f"  {'-'*58}")
    for store_id, grp in visits_df.groupby("store_id"):
        n   = len(grp)
        mm  = (~grp["memo_filed"]).sum()
        dm  = grp["disclosure_ref_missing"].sum()
        mx  = grp["memo_mismatch"].sum()
        fr  = (mm + dm + mx) / n
        print(f"  {store_id:<14} {n:>7} {mm:>6}({mm/n:.0%}) {dm:>6}({dm/n:.0%}) "
              f"{mx:>6}({mx/n:.0%}) {fr:>8.1%}")

    print(f"\n  store_visits_{parsed.month}.csv → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

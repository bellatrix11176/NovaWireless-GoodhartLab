"""
02_sanitize_store_visits.py
=============================
NovaWireless-GoodhartLab — Store Visit Sanitizer

Reads raw store_visits_YYYY-MM.csv and produces a clean,
analysis-ready sanitized file.

WHAT THIS DOES
--------------
  1. Enforces consistent column order and correct data types
  2. Derives the composite audit_flag column
  3. Derives audit_flag_reason — human-readable explanation of any flag
  4. Keeps memo_text as a dedicated column for NLP analysis
  5. Writes to output/store-gen/sanitized/

OUTPUT COLUMNS
--------------
  Identity
    visit_id, visit_seq, month, store_id, store_name, rep_id, customer_id

  Visit Info
    visit_type, visit_label, can_complete

  Memo Content (for NLP)
    reason_for_visit, rep_advised, customer_decision
    account_change_actual, account_change_in_memo
    disclosure_ref
    memo_text

  Audit Signals
    memo_filed              : bool — False = no memo filed at all
    memo_mismatch           : bool — memo change != actual change
    disclosure_ref_missing  : bool — required ref not filed
    requires_disclosure     : bool — was a ref required for this visit
    system_restriction_violation : bool — store completed restricted action
    memo_quality_score      : float 0–1

  Composite Audit
    audit_flag              : bool — any of the above is True
    audit_flag_reason       : str  — pipe-separated list of triggered flags

  Cross-reference
    customer_id links to customers.csv and to call-gen sanitized files.
    A store visit followed by a call center contact within 30 days on
    the same issue is a strong signal of a memo/advice failure.

USAGE
-----
  python src/02_sanitize_store_visits.py
  python src/02_sanitize_store_visits.py --month 2026-01
  python src/02_sanitize_store_visits.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import find_repo_root

REPO_ROOT  = find_repo_root()
RAW_DIR    = REPO_ROOT / "output" / "store-gen"
CLEAN_DIR  = REPO_ROOT / "output" / "store-gen" / "sanitized"

# ── Column order for sanitized output ────────────────────────────────────────

IDENTITY_COLS = [
    "visit_id",
    "visit_seq",
    "month",
    "store_id",
    "store_name",
    "rep_id",
    "customer_id",
]

VISIT_COLS = [
    "visit_type",
    "visit_label",
    "can_complete",
]

MEMO_CONTENT_COLS = [
    "reason_for_visit",
    "rep_advised",
    "customer_decision",
    "account_change_actual",
    "account_change_in_memo",
    "disclosure_ref",
]

AUDIT_SIGNAL_COLS = [
    "memo_filed",
    "memo_mismatch",
    "disclosure_ref_missing",
    "requires_disclosure",
    "system_restriction_violation",
    "memo_quality_score",
]

COMPOSITE_COLS = [
    "audit_flag",
    "audit_flag_reason",
]

NLP_COLS = [
    "memo_text",
]

FINAL_COL_ORDER = (
    IDENTITY_COLS
    + VISIT_COLS
    + MEMO_CONTENT_COLS
    + AUDIT_SIGNAL_COLS
    + COMPOSITE_COLS
    + NLP_COLS
)


# ── Sanitize logic ────────────────────────────────────────────────────────────

def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and enrich one month of raw store visit data.
    """
    out = df.copy()

    # ── Type enforcement ──────────────────────────────────────────────────────
    bool_cols = [
        "memo_filed", "memo_mismatch", "disclosure_ref_missing",
        "requires_disclosure", "system_restriction_violation", "can_complete",
    ]
    for col in bool_cols:
        if col in out.columns:
            out[col] = out[col].fillna(False).astype(bool)

    float_cols = ["memo_quality_score"]
    for col in float_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0).round(4)

    int_cols = ["visit_seq"]
    for col in int_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    str_cols = [
        "visit_id", "month", "store_id", "store_name", "rep_id", "customer_id",
        "visit_type", "visit_label", "reason_for_visit", "rep_advised",
        "customer_decision", "account_change_actual", "account_change_in_memo",
        "disclosure_ref", "memo_text",
    ]
    for col in str_cols:
        if col in out.columns:
            out[col] = out[col].fillna("N/A").astype(str).str.strip()

    # ── Add missing columns with defaults ────────────────────────────────────
    if "system_restriction_violation" not in out.columns:
        out["system_restriction_violation"] = False
    if "visit_seq" not in out.columns:
        out["visit_seq"] = range(1, len(out) + 1)

    # ── Composite audit flag ──────────────────────────────────────────────────
    def build_flag_reason(row) -> str:
        reasons = []
        if not row["memo_filed"]:
            reasons.append("MISSING_MEMO")
        if row["memo_mismatch"]:
            reasons.append("MEMO_MISMATCH")
        if row["disclosure_ref_missing"]:
            reasons.append("MISSING_DISCLOSURE_REF")
        if row["system_restriction_violation"]:
            reasons.append("SYSTEM_RESTRICTION_VIOLATION")
        return " | ".join(reasons) if reasons else "clean"

    out["audit_flag"]        = (
        ~out["memo_filed"]
        | out["memo_mismatch"]
        | out["disclosure_ref_missing"]
        | out["system_restriction_violation"]
    )
    out["audit_flag_reason"] = out.apply(build_flag_reason, axis=1)

    # ── Sort ──────────────────────────────────────────────────────────────────
    out = out.sort_values(["store_id", "visit_seq"]).reset_index(drop=True)

    # ── Select and reorder columns ────────────────────────────────────────────
    available = [c for c in FINAL_COL_ORDER if c in out.columns]
    extra     = [c for c in out.columns if c not in FINAL_COL_ORDER]
    return out[available + extra]


# ── Main ──────────────────────────────────────────────────────────────────────

def sanitize_month(month: str) -> int:
    raw_path = RAW_DIR / f"store_visits_{month}.csv"
    if not raw_path.exists():
        print(f"  [SKIP] {raw_path.name} not found.")
        return 0

    print(f"  Sanitizing {raw_path.name}...")
    df      = pd.read_csv(raw_path)
    clean   = sanitize(df)

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CLEAN_DIR / f"store_visits_sanitized_{month}.csv"
    clean.to_csv(out_path, index=False)

    total     = len(clean)
    flagged   = clean["audit_flag"].sum()
    missing   = (~clean["memo_filed"]).sum()
    mismatch  = clean["memo_mismatch"].sum()
    no_disc   = clean["disclosure_ref_missing"].sum()
    quality   = clean["memo_quality_score"].mean()

    print(f"    Rows:              {total:,}")
    print(f"    Audit flagged:     {flagged:,}  ({flagged/total:.1%})")
    print(f"      Missing memo:    {missing:,}  ({missing/total:.1%})")
    print(f"      Memo mismatch:   {mismatch:,}  ({mismatch/total:.1%})")
    print(f"      Missing disc ref:{no_disc:,}  ({no_disc/total:.1%})")
    print(f"    Mean memo quality: {quality:.3f}")
    print(f"    Written → {out_path}")
    return total


def find_all_months() -> list[str]:
    return sorted([
        p.stem.replace("store_visits_", "")
        for p in RAW_DIR.glob("store_visits_????-??.csv")
    ])


def main(args=None) -> int:
    parser = argparse.ArgumentParser(
        description="Sanitize store visit records for analysis"
    )
    parser.add_argument("--month", type=str, default=None,
                        help="Sanitize a single month (YYYY-MM)")
    parser.add_argument("--all",   action="store_true",
                        help="Sanitize all available months")
    parsed = parser.parse_args(args)

    print("=" * 60)
    print("NovaWireless-GoodhartLab — Store Visit Sanitizer")
    print("=" * 60)

    if parsed.month:
        months = [parsed.month]
    elif parsed.all:
        months = find_all_months()
        if not months:
            print(f"No raw store visit files found in {RAW_DIR}")
            return 1
        print(f"Found {len(months)} month(s): {', '.join(months)}")
    else:
        # Default: sanitize all available
        months = find_all_months()
        if not months:
            print(f"No raw store visit files found in {RAW_DIR}")
            print("Run generate_store_visits.py first.")
            return 1
        print(f"Found {len(months)} month(s): {', '.join(months)}")

    total_rows = 0
    for month in months:
        total_rows += sanitize_month(month)

    print(f"\n{'='*60}")
    print(f"Sanitization complete.")
    print(f"  Total rows processed: {total_rows:,}")
    print(f"  Output: {CLEAN_DIR}")
    print(f"  Use store_visits_sanitized_*.csv for all analysis.")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

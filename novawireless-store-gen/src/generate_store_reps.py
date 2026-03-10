"""
generate_store_reps.py
=============================
NovaWireless-GoodhartLab — Store Rep Generator

Generates a population of retail store representatives across
NovaWireless store locations.

DESIGN NOTES
------------
Store reps are a separate workforce from call center reps.
Department: retail
They are assigned to specific store locations and have persona traits
that influence visit outcome quality, memo completeness, and
disclosure compliance.

GOODHART DYNAMICS
-----------------
Store reps are NOT deliberately gaming the system. Memo quality
degrades under burnout and foot-traffic pressure:
  - High burnout → missing or vague memos
  - High pressure → missing disclosure references
  - Low ownership_bias → account changes not reflected in memo

This is the same unintentional drift observed in call center reps.
The memo audit is designed to catch this degradation pattern.

STORES
------
12 store locations. Each store has 8-12 reps.
Store IDs: NW-STORE-01 through NW-STORE-12
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import find_repo_root

REPO_ROOT  = find_repo_root()
DATA_DIR   = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"

# ── Config ────────────────────────────────────────────────────────────────────
N_STORES        = 12
REPS_PER_STORE  = (8, 12)   # min, max
BASE_STRAIN     = 0.52
BASE_TRAINING   = 6.5       # months
SEED            = 2026_02_26

STORE_NAMES = [
    "Dalton Towne Center", "Chattanooga Eastgate", "Calhoun Commons",
    "Rome Marketplace", "Cartersville Crossing", "Ringgold Ridge",
    "Fort Oglethorpe Plaza", "Cleveland Square", "Jasper Junction",
    "Gainesville Galleria", "Cumming Station", "Canton Crossroads",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def z_noise(rng: random.Random, sigma: float = 0.12) -> float:
    u1 = max(1e-9, rng.random())
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2) * sigma

# ── Rep synthesis ─────────────────────────────────────────────────────────────
def synthesize_store_rep(
    rng: random.Random,
    store_id: str,
    store_strain: float,
    training: float,
) -> dict:
    """
    Synthesize one retail store rep persona and KPI profile.

    Traits
    ------
    product_knowledge   : accuracy of plan/device/promo advice
    disclosure_diligence: likelihood of correctly filing disclosure ref
    ownership_bias      : takes accountability for account changes
    upsell_pressure     : tendency to recommend higher-tier products
    memo_thoroughness   : quality and completeness of memos filed
    conflict_tolerance  : handles frustrated customers without shortcuts
    emotional_regulation: stays composed under busy-store pressure
    burnout_index       : composite burnout signal
    gaming_propensity   : burnout-driven memo degradation (NOT intentional)

    Goodhart dynamics
    -----------------
    gaming_propensity is driven ONLY by burnout and upsell_pressure.
    High upsell_pressure reps may file memos that describe a different
    product than what was sold — not fraud, just sloppy documentation
    under quota pressure.
    """
    patience           = clamp(0.510 + z_noise(rng, 0.08))
    empathy            = clamp(0.500 + z_noise(rng, 0.07))
    burnout_risk_prior = clamp(0.460 + z_noise(rng, 0.10))

    burnout = clamp(
        0.50 * burnout_risk_prior
        + 0.30 * store_strain
        + 0.10 * (1.0 - patience)
        + z_noise(rng, 0.09)
    )

    product_knowledge = clamp(
        0.60
        + 0.15 * (training / 12.0)
        - 0.20 * burnout
        + z_noise(rng, 0.07)
    )

    disclosure_diligence = clamp(
        0.65
        + 0.12 * (training / 12.0)
        - 0.25 * burnout
        + 0.10 * empathy
        + z_noise(rng, 0.08)
    )

    ownership_bias = clamp(0.55 + z_noise(rng, 0.10))

    upsell_pressure = clamp(0.40 + z_noise(rng, 0.12))

    memo_thoroughness = clamp(
        0.70
        - 0.30 * burnout
        + 0.15 * ownership_bias
        - 0.10 * upsell_pressure
        + z_noise(rng, 0.08)
    )

    conflict_tolerance   = clamp(0.50 + z_noise(rng, 0.10))
    emotional_regulation = clamp(1.0 - burnout * 0.60 + z_noise(rng, 0.08))

    compliance_risk = clamp(
        0.10
        + 0.35 * burnout
        + 0.20 * (1.0 - disclosure_diligence)
        + 0.15 * upsell_pressure
        + z_noise(rng, 0.06)
    )

    # Goodhart: gaming_propensity is burnout + upsell_pressure driven
    # NOT metric chasing — just degraded memo quality under pressure
    gaming_propensity = clamp(
        0.55 * burnout
        + 0.25 * upsell_pressure
        - 0.20 * memo_thoroughness
        + z_noise(rng, 0.04),
        0.0, 0.60
    )

    strain_score = clamp(0.6 * store_strain + 0.4 * clamp(0.15 + 0.85 * burnout))
    if strain_score < 0.35:   strain_tier = "low"
    elif strain_score < 0.55: strain_tier = "medium"
    elif strain_score < 0.75: strain_tier = "high"
    else:                      strain_tier = "peak"

    return {
        "store_id":             store_id,
        "department":           "retail",
        "product_knowledge":    round(product_knowledge,    4),
        "disclosure_diligence": round(disclosure_diligence, 4),
        "ownership_bias":       round(ownership_bias,       4),
        "upsell_pressure":      round(upsell_pressure,      4),
        "memo_thoroughness":    round(memo_thoroughness,    4),
        "conflict_tolerance":   round(conflict_tolerance,   4),
        "emotional_regulation": round(emotional_regulation, 4),
        "burnout_index":        round(clamp(0.15 + 0.85 * burnout), 4),
        "compliance_risk":      round(compliance_risk,      4),
        "gaming_propensity":    round(gaming_propensity,    4),
        "strain_tier":          strain_tier,
        "strain_score":         round(strain_score,         4),
        "patience":             round(patience,             4),
        "empathy":              round(empathy,              4),
        "training_months":      round(training,             1),
    }


# ── Store population builder ──────────────────────────────────────────────────
def build_store_population(
    n_stores: int,
    reps_range: tuple[int, int],
    base_strain: float,
    training: float,
    rng: random.Random,
) -> pd.DataFrame:
    rows = []
    rep_counter = 1

    for store_idx in range(n_stores):
        store_id   = f"NW-STORE-{store_idx + 1:02d}"
        store_name = STORE_NAMES[store_idx % len(STORE_NAMES)]
        n_reps     = rng.randint(*reps_range)

        # Each store has its own strain modifier (±0.08 from base)
        store_strain = clamp(base_strain + z_noise(rng, 0.08))

        for _ in range(n_reps):
            rep = synthesize_store_rep(rng, store_id, store_strain, training)
            rep["rep_id"]     = f"STORE-REP-{rep_counter:04d}"
            rep["store_name"] = store_name
            rows.append(rep)
            rep_counter += 1

    df = pd.DataFrame(rows)
    # Reorder columns sensibly
    front = ["rep_id", "store_id", "store_name", "department"]
    rest  = [c for c in df.columns if c not in front]
    return df[front + rest]


# ── Main ──────────────────────────────────────────────────────────────────────
def main(args=None) -> int:
    parser = argparse.ArgumentParser(description="Generate NovaWireless store rep population")
    parser.add_argument("--n_stores",  type=int,   default=N_STORES,      help="Number of store locations")
    parser.add_argument("--min_reps",  type=int,   default=REPS_PER_STORE[0])
    parser.add_argument("--max_reps",  type=int,   default=REPS_PER_STORE[1])
    parser.add_argument("--strain",    type=float, default=BASE_STRAIN)
    parser.add_argument("--training",  type=float, default=BASE_TRAINING)
    parser.add_argument("--seed",      type=int,   default=SEED)
    parsed = parser.parse_args(args)

    rng = random.Random(parsed.seed)

    print("=" * 60)
    print("NovaWireless-GoodhartLab — Store Rep Generator")
    print(f"  Stores:       {parsed.n_stores}")
    print(f"  Reps/store:   {parsed.min_reps}–{parsed.max_reps}")
    print(f"  Base strain:  {parsed.strain}")
    print(f"  Training:     {parsed.training} months")
    print(f"  Seed:         {parsed.seed}")
    print("=" * 60)

    df = build_store_population(
        n_stores   = parsed.n_stores,
        reps_range = (parsed.min_reps, parsed.max_reps),
        base_strain= parsed.strain,
        training   = parsed.training,
        rng        = rng,
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "novawireless_store_rep_database.csv"
    df.to_csv(out_path, index=False)

    print(f"\nStore rep database written → {out_path}")
    print(f"  Total reps:  {len(df)}")
    print(f"  Stores:      {df['store_id'].nunique()}")
    print(f"\nPer-store breakdown:")
    for sid, grp in df.groupby("store_id"):
        name = grp["store_name"].iloc[0]
        print(f"  {sid}  {name:<28}  {len(grp)} reps  "
              f"burnout_mean={grp['burnout_index'].mean():.3f}  "
              f"memo_mean={grp['memo_thoroughness'].mean():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

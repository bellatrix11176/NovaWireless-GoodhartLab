"""
pressure_experiment_governance.py
===================================
NovaWireless-GovernanceLab — Ecosystem Pressure Experiment

WHAT THIS SHOWS
---------------
Your theory: if you remove the metrics that reward gaming, reps won't
game the system — even under pressure.

This experiment tests that. Reps in the governance regime are measured
on honest metrics (DAR, DOV, trust delta) — not proxy FCR. So there is
no metric to game. The only path to gaming behavior is pure burnout:
a rep so exhausted and overwhelmed that they cut corners not because
they're chasing a number, but because they're breaking down.

HOW IT DIFFERS FROM pressure_experiment.py
-------------------------------------------
  - SCENARIO_MIX: no gaming/fraud scenarios in the base pool
  - Burnout-driven gaming bleed: at HIGH burnout only (>0.75), a very
    small probability of gaming behavior bleeds in — not metric-chasing,
    just stress-induced corner-cutting
  - gaming_propensity formula: driven ONLY by burnout, not compliance
    or QA (those are governance-aligned signals, not gaming incentives)
  - Figure 5: should show near-flat bars — almost no scenario shift
    compared to GoodhartLab's big orange bars
  - Figure titles clarify this is the governance regime

WHAT TO COMPARE
---------------
  GoodhartLab  pressure_experiment.py           → big gaming shift under pressure
  GovernanceLab pressure_experiment_governance.py → near-flat gaming shift

That difference is your theory in chart form.

Run:
  python src/pressure_experiment_governance.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from utils import find_repo_root

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

if __name__ == "__main__":
    # Guard sys.path mutation so it does not pollute the import namespace
    # when pressure_experiment is imported by another module (e.g. run_governance_lab.py).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from transcript_builder import build_transcript, transcript_to_text  # noqa: E402
else:
    # When imported as a module the caller is responsible for sys.path.
    # Import lazily so the module can still be parsed without transcript_builder on path.
    try:
        from transcript_builder import build_transcript, transcript_to_text
    except ImportError:
        def build_transcript(*args, **kwargs):  # type: ignore[misc]
            raise ImportError("transcript_builder not on sys.path — run as __main__ or set path first")
        def transcript_to_text(*args, **kwargs):  # type: ignore[misc]
            raise ImportError("transcript_builder not on sys.path — run as __main__ or set path first")

# ── Paths ─────────────────────────────────────────────────────────────────────


REPO_ROOT  = find_repo_root()
OUTPUT_DIR = REPO_ROOT / "output"
EXP_DIR    = OUTPUT_DIR / "experiments"
FIG_DIR    = EXP_DIR / "experiment_figures"

# ── Experiment config ─────────────────────────────────────────────────────────
SEED          = 2026_02_26
N_REPS        = 250
N_CALLS       = 5_000
BASE_TRAINING = 6.5

CONDITIONS = {
    "baseline": {
        "base_strain":  0.52,
        "pressure":     0.14,
        "label":        "Baseline",
        "color":        "#2E5FA3",
    },
    "high_pressure": {
        "base_strain":  0.72,
        "pressure":     0.62,
        "label":        "High Pressure",
        "color":        "#C45B1A",
    },
}

# KEY CHANGE: no gaming or fraud scenarios in the base mix.
# Governance metrics give reps nothing to game.
# Weight redistributed to clean and honest scenarios.
SCENARIO_MIX = {
    "clean":               0.62,
    "unresolvable_clean":  0.14,
    "activation_clean":    0.10,
    "activation_failed":   0.06,
    "line_add_legitimate": 0.08,
}

# KEY CHANGE: gaming scenarios still defined so burnout-bleed routing
# can access them — but they are NOT in the base SCENARIO_MIX.
# They only appear if a rep's burnout crosses the stress threshold.
BURNOUT_BLEED_SCENARIOS = {"gamed_metric"}   # only the softest gaming — no fraud
BURNOUT_BLEED_THRESHOLD = 0.75               # burnout must be > 75% before bleed occurs
BURNOUT_BLEED_MAX_PROB  = 0.22               # aligned with scenario_router.py — at peak burnout, 22% chance of bleed per call

# All scenarios that count as gaming for reporting
GAMING_SCENARIOS = {"gamed_metric"}

# ── KPI synthesis ─────────────────────────────────────────────────────────────

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))

def z_noise(rng: random.Random, sigma: float = 0.15) -> float:
    u1 = max(1e-9, rng.random())
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2) * sigma

def synthesize_rep(rng: random.Random, base_strain: float,
                   pressure: float, training: float) -> dict:
    """
    Synthesize one rep's persona and KPI profile — governance-aligned.

    KEY CHANGE vs GoodhartLab version:
    gaming_propensity is now ONLY a function of burnout.
    In the governance regime, reps are not rewarded for gaming proxy
    metrics, so compliance_risk and qa no longer feed into gaming_propensity.
    A rep can only drift toward gaming if they are severely burned out.
    """
    patience           = clamp(0.505 + z_noise(rng, 0.08))
    empathy            = clamp(0.500 + z_noise(rng, 0.07))
    escalation_prone   = clamp(0.512 + z_noise(rng, 0.09))
    burnout_risk_prior = clamp(0.481 + z_noise(rng, 0.10))

    burnout    = clamp(0.55 * burnout_risk_prior
                       + 0.30 * base_strain
                       + 0.15 * (pressure - 0.5)
                       - 0.10 * patience
                       + z_noise(rng, 0.10))
    resilience = clamp(1.0 - burnout * 0.65
                       + (training / 12.0) * 0.20
                       + z_noise(rng, 0.08))
    volatility = clamp(0.30 + burnout * 0.60 + z_noise(rng, 0.12))

    qa = clamp(0.58
               + 0.12 * patience
               + 0.10 * (training / 12.0)
               - 0.18 * burnout
               + z_noise(rng, 0.06))

    fcr = clamp(0.55
                + 0.18 * qa
                + 0.10 * patience
                - 0.18 * burnout
                - 0.08 * (pressure - 0.5)
                + z_noise(rng, 0.06), 0.10, 0.95)

    base_aht = 560.0
    aht = clamp(base_aht
                * (1.0 + 0.35 * burnout + 0.18 * (pressure - 0.5))
                * (1.0 - 0.08 * (training / 12.0))
                * (1.0 - 0.06 * qa)
                + z_noise(rng, 0.20) * 120,
                240.0, 1600.0)

    escalation = clamp(0.05
                       + 0.18 * escalation_prone
                       + 0.10 * burnout
                       - 0.12 * qa
                       + z_noise(rng, 0.04), 0.01, 0.55)

    repeat_rate = clamp(0.08
                        + 0.65 * (1.0 - fcr)
                        + 0.06 * (pressure - 0.5)
                        + z_noise(rng, 0.04), 0.02, 0.80)

    compliance = clamp(0.10
                       + 0.35 * burnout
                       + 0.25 * (1.0 - qa)
                       + 0.12 * escalation
                       + z_noise(rng, 0.06), 0.01, 0.95)

    aht_norm      = clamp((1600.0 - aht) / (1600.0 - 240.0))
    productivity  = clamp(0.42 * fcr + 0.33 * qa + 0.25 * aht_norm
                          - 0.15 * burnout + z_noise(rng, 0.04))

    strain_score = clamp(0.6 * base_strain + 0.4 * clamp(0.15 + 0.85 * burnout))
    if strain_score < 0.35:   strain_tier = "low"
    elif strain_score < 0.55: strain_tier = "medium"
    elif strain_score < 0.75: strain_tier = "high"
    else:                      strain_tier = "peak"

    # KEY CHANGE: gaming_propensity driven ONLY by burnout.
    # No compliance_risk, no QA penalty — those are governance signals.
    # Only a rep breaking down from pure exhaustion drifts toward gaming.
    # Maximum gaming propensity is capped much lower than GoodhartLab.
    burnout_normalized = clamp(burnout)
    gaming_propensity  = clamp(
        0.60 * burnout_normalized                    # burnout is the only driver
        - 0.20 * empathy                             # empathetic reps resist even when burned out
        + z_noise(rng, 0.04),
        0.0, 0.50                                    # hard cap at 0.50 — no metric chasing
    )

    return {
        "fcr_30d":             round(fcr, 4),
        "qa_score":            round(qa, 4),
        "aht_secs":            round(aht, 2),
        "compliance_risk":     round(compliance, 4),
        "repeat_contact_rate": round(repeat_rate, 4),
        "burnout_index":       round(clamp(0.15 + 0.85 * burnout), 4),
        "resilience_index":    round(resilience, 4),
        "volatility_index":    round(volatility, 4),
        "productivity_index":  round(productivity, 4),
        "escalation_rate":     round(escalation, 4),
        "strain_tier":         strain_tier,
        "strain_score":        round(strain_score, 4),
        "gaming_propensity":   round(gaming_propensity, 4),
        "patience":            round(patience, 4),
        "empathy":             round(empathy, 4),
    }


def build_roster(condition_name: str, cfg: dict, n: int, rng: random.Random) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rep = synthesize_rep(rng, cfg["base_strain"], cfg["pressure"], BASE_TRAINING)
        rep["rep_id"]    = f"{condition_name.upper()[:3]}-REP{i+1:04d}"
        rep["condition"] = condition_name
        rows.append(rep)
    return pd.DataFrame(rows)


# ── Call simulation ───────────────────────────────────────────────────────────

def sample_scenario(rng: np.random.Generator, rep: dict) -> str:
    """
    KEY CHANGE: scenario sampling is governance-first.

    Base pool has no gaming scenarios. However, if a rep's burnout
    exceeds the bleed threshold, there is a small probability that
    their exhaustion causes a gamed_metric call to bleed in.
    This is NOT metric-chasing — it is stress-induced corner-cutting.
    """
    burnout = rep.get("burnout_index", 0.0)

    # Burnout bleed — only activates above threshold
    if burnout > BURNOUT_BLEED_THRESHOLD:
        # Probability scales from 0 at threshold to max at burnout=1.0
        bleed_range = 1.0 - BURNOUT_BLEED_THRESHOLD
        bleed_intensity = (burnout - BURNOUT_BLEED_THRESHOLD) / bleed_range
        bleed_prob = bleed_intensity * BURNOUT_BLEED_MAX_PROB
        if rng.random() < bleed_prob:
            return "gamed_metric"   # stress-induced corner cut, not metric gaming

    # Normal governance scenario
    keys  = list(SCENARIO_MIX.keys())
    probs = np.array(list(SCENARIO_MIX.values()), dtype=float)
    probs /= probs.sum()
    return str(rng.choice(keys, p=probs))


CALL_TYPE_PRIORS = {
    "clean":               ["Billing Dispute", "Network Coverage", "Device Issue",
                            "Promotion Inquiry", "Account Inquiry", "Payment Arrangement"],
    "unresolvable_clean":  ["Account Inquiry"],
    "activation_clean":    ["Device Issue"],
    "activation_failed":   ["Device Issue"],
    "line_add_legitimate": ["Account Inquiry"],
    "gamed_metric":        ["Billing Dispute"],   # bleed-through scenario
}

CLEAN_CALL_TYPE_WEIGHTS = [0.30, 0.22, 0.18, 0.14, 0.10, 0.06]


def simulate_call(rng: np.random.Generator, rep: dict, scenario: str) -> dict:
    """
    Simulate one call — governance-aligned outcome probabilities.

    KEY CHANGES vs GoodhartLab:
    - Proxy resolution is NOT inflated by gaming_propensity
    - True and proxy resolution are close (gap is small)
    - Compliance events scale with burnout, not gaming scenario routing
    - gamed_metric calls only appear via burnout bleed, not routing weight
    """
    is_gaming = scenario in GAMING_SCENARIOS

    # True resolution — governance scenarios have high honest resolution
    BASE_TRUE_RES = {
        "clean":               0.92,
        "unresolvable_clean":  0.10,
        "activation_clean":    0.95,
        "activation_failed":   0.08,
        "line_add_legitimate": 0.92,
        "gamed_metric":        0.18,  # bleed-through: still low true res
    }
    base_true_res = BASE_TRUE_RES.get(scenario, 0.70)
    fcr_adj = (rep["fcr_30d"] - 0.70) * 0.3 if scenario == "clean" else 0.0
    true_res = bool(rng.random() < clamp(base_true_res + fcr_adj))

    # Proxy resolution — honest in governance regime, close to true
    # KEY CHANGE: no gaming inflation. Reps mark what actually happened.
    BASE_PROXY_RES = {
        "clean":               0.91,   # nearly matches true
        "unresolvable_clean":  0.12,   # honest: reps don't falsely close these
        "activation_clean":    0.94,
        "activation_failed":   0.09,   # honest: failed activations not marked resolved
        "line_add_legitimate": 0.91,
        "gamed_metric":        0.88,   # bleed-through: rep still games the close
    }
    proxy_res = bool(rng.random() < BASE_PROXY_RES.get(scenario, 0.70))

    # Repeat contact
    BASE_REPEAT = {
        "clean":               0.06,
        "unresolvable_clean":  0.30,
        "activation_clean":    0.05,
        "activation_failed":   0.40,
        "line_add_legitimate": 0.06,
        "gamed_metric":        0.52,
    }
    repeat_adj = (rep["repeat_contact_rate"] - 0.245) * 0.5
    repeat_30d = bool(rng.random() < clamp(BASE_REPEAT.get(scenario, 0.10) + repeat_adj))

    # Compliance event — scales with burnout in governance, not gaming routing
    # KEY CHANGE: burnout drives compliance events, not gaming scenario type
    burnout_compliance_mult = 1.0 + rep.get("burnout_index", 0.0) * 0.8
    compliance_event = bool(rng.random() < rep["compliance_risk"]
                            * (burnout_compliance_mult if not is_gaming else 1.4))

    # AHT
    AHT_MULT = {
        "clean":               1.00,
        "unresolvable_clean":  1.25,
        "activation_clean":    1.10,
        "activation_failed":   1.35,
        "line_add_legitimate": 1.20,
        "gamed_metric":        0.80,
    }
    aht = rep["aht_secs"] * AHT_MULT.get(scenario, 1.0) * (1.0 + rng.normal(0, 0.08))

    # Call type
    ct_options = CALL_TYPE_PRIORS.get(scenario, ["Account Inquiry"])
    if scenario == "clean":
        wts = np.array(CLEAN_CALL_TYPE_WEIGHTS[:len(ct_options)], dtype=float)
        wts /= wts.sum()
        call_type = str(rng.choice(ct_options, p=wts))
    else:
        call_type = ct_options[0]

    # Transcript
    agent_dict    = {"rep_name": rep.get("rep_id", "Agent"), "rep_id": rep.get("rep_id")}
    customer_dict = {"customer_id": f"CUST-{abs(hash(rep['rep_id']))%99999:05d}",
                     "account_id":  f"ACCT-{abs(hash(rep['rep_id']))%99999:05d}",
                     "monthly_charges": 85.0,
                     "lines_on_account": 2,
                     "patience": rep.get("patience", 0.5),
                     "trust_baseline": 65.0,
                     "churn_risk_score": 0.30}
    scenario_meta = {"rep_aware_gaming": bool(rep.get("gaming_propensity", 0) > 0.40)}
    credit_info   = {"credit_applied": False, "credit_amount": 0.0,
                     "credit_type": "none", "credit_authorized": True}
    turns = build_transcript(scenario, call_type, agent_dict, customer_dict,
                             scenario_meta, credit_info, rng, is_repeat_call=False)
    transcript_text = transcript_to_text(turns)

    return {
        "scenario":         scenario,
        "call_type":        call_type,
        "is_gaming":        is_gaming,
        "true_resolution":  true_res,
        "proxy_resolution": proxy_res,
        "repeat_30d":       repeat_30d,
        "compliance_event": compliance_event,
        "aht_secs":         round(max(aht, 120.0), 1),
        "rep_fcr":          rep["fcr_30d"],
        "rep_compliance":   rep["compliance_risk"],
        "rep_burnout":      rep["burnout_index"],
        "rep_gaming_prop":  rep["gaming_propensity"],
        "rep_strain_tier":  rep["strain_tier"],
        "transcript":       transcript_text,
    }


def run_condition(condition_name: str, cfg: dict,
                  np_rng: np.random.Generator,
                  py_rng: random.Random) -> tuple[pd.DataFrame, pd.DataFrame]:
    print(f"  Synthesizing {N_REPS} reps [{cfg['label']}]...")
    roster = build_roster(condition_name, cfg, N_REPS, py_rng)

    print(f"  Simulating {N_CALLS:,} calls [{cfg['label']}]...")
    rep_pool  = roster.to_dict("records")
    call_rows = []

    for i in range(N_CALLS):
        # KEY CHANGE: rep selected randomly first, then scenario sampled
        # per THAT rep's burnout. No routing weight toward gaming reps.
        idx = int(np_rng.integers(0, len(rep_pool)))
        rep = rep_pool[idx]
        scenario = sample_scenario(np_rng, rep)
        result = simulate_call(np_rng, rep, scenario)
        result["call_id"]   = f"{condition_name.upper()[:3]}-CALL-{i+1:06d}"
        result["condition"] = condition_name
        result["rep_id"]    = rep["rep_id"]
        call_rows.append(result)

    calls_df = pd.DataFrame(call_rows)
    return roster, calls_df


# ── Analysis ──────────────────────────────────────────────────────────────────

def compute_summary(calls: pd.DataFrame, roster: pd.DataFrame,
                    condition_name: str, cfg: dict) -> dict:
    gaming_calls = calls[calls["is_gaming"]]
    gc_compliance = gaming_calls["rep_compliance"].mean() if len(gaming_calls) > 0 else 0.0
    gc_burnout    = gaming_calls["rep_burnout"].mean()    if len(gaming_calls) > 0 else 0.0
    gc_repeat     = gaming_calls["repeat_30d"].mean()     if len(gaming_calls) > 0 else 0.0
    return {
        "condition":               condition_name,
        "label":                   cfg["label"],
        "base_strain":             cfg["base_strain"],
        "pressure":                cfg["pressure"],
        "roster_mean_fcr":         round(roster["fcr_30d"].mean(), 4),
        "roster_mean_compliance":  round(roster["compliance_risk"].mean(), 4),
        "roster_mean_burnout":     round(roster["burnout_index"].mean(), 4),
        "roster_mean_aht":         round(roster["aht_secs"].mean(), 1),
        "roster_pct_high_strain":  round((roster["strain_tier"].isin(["high","peak"])).mean(), 4),
        "call_mean_fcr":           round(calls["rep_fcr"].mean(), 4),
        "call_true_res_rate":      round(calls["true_resolution"].mean(), 4),
        "call_proxy_res_rate":     round(calls["proxy_resolution"].mean(), 4),
        "call_res_gap":            round(calls["proxy_resolution"].mean() - calls["true_resolution"].mean(), 4),
        "call_repeat_30d_rate":    round(calls["repeat_30d"].mean(), 4),
        "call_compliance_event_rate": round(calls["compliance_event"].mean(), 4),
        "call_mean_aht":           round(calls["aht_secs"].mean(), 1),
        "gaming_call_share":       round(calls["is_gaming"].mean(), 4),
        "gaming_mean_compliance":  round(gc_compliance, 4),
        "gaming_mean_burnout":     round(gc_burnout, 4),
        "gaming_repeat_rate":      round(gc_repeat, 4),
        "n_calls":                 len(calls),
        "n_reps":                  len(roster),
    }


# ── Figures ───────────────────────────────────────────────────────────────────

PALETTE = {"baseline": "#2E5FA3", "high_pressure": "#C45B1A"}
LABELS  = {"baseline": "Baseline", "high_pressure": "High Pressure"}


def bar_comparison(metric_pairs, summaries, title, fname, higher_is_bad=False):
    n  = len(metric_pairs)
    x  = np.arange(n)
    w  = 0.32
    fig, ax = plt.subplots(figsize=(max(8, n * 1.8), 5.2))
    fig.patch.set_facecolor("white")
    b_vals  = [summaries["baseline"][k]      for _, k, _ in metric_pairs]
    hp_vals = [summaries["high_pressure"][k] for _, k, _ in metric_pairs]
    labels_x = [l for l, _, _ in metric_pairs]
    bars_b  = ax.bar(x - w/2, b_vals,  w, color=PALETTE["baseline"],      label="Baseline",      alpha=0.88, zorder=3)
    bars_hp = ax.bar(x + w/2, hp_vals, w, color=PALETTE["high_pressure"], label="High Pressure", alpha=0.88, zorder=3)
    for bar, val in [(bars_b, b_vals), (bars_hp, hp_vals)]:
        for b, v in zip(bar, val):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.003,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=8, color="#333")
    for i, (bv, hv) in enumerate(zip(b_vals, hp_vals)):
        delta = hv - bv
        sign  = "+" if delta >= 0 else ""
        color = "#8B0000" if (delta > 0) == higher_is_bad else "#1A7A6E"
        ax.text(i, max(bv, hv) + 0.030, f"Δ{sign}{delta:.3f}",
                ha="center", va="bottom", fontsize=8.5, color=color, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels_x, fontsize=9)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=14)
    ax.set_ylim(0, max(max(b_vals), max(hp_vals)) * 1.28)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(FIG_DIR / fname, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"    Saved: {fname}")


def rep_distribution_plot(rosters, metric, xlabel, fname):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    fig.patch.set_facecolor("white")
    for cond, roster in rosters.items():
        vals = roster[metric].dropna()
        ax.hist(vals, bins=30, alpha=0.55, color=PALETTE[cond],
                label=LABELS[cond], density=True, edgecolor="white", linewidth=0.4)
        ax.axvline(vals.mean(), color=PALETTE[cond], linestyle="--",
                   linewidth=1.8, label=f"{LABELS[cond]} mean = {vals.mean():.3f}")
    ax.set_xlabel(xlabel, fontsize=10)
    ax.set_ylabel("Density", fontsize=10)
    ax.set_title(f"Rep Population Distribution: {xlabel}", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(FIG_DIR / fname, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"    Saved: {fname}")


def gaming_shift_plot(calls_dict, fname):
    """
    KEY CHANGE: Figure 5 for governance version.
    Shows scenario mix shift — expect near-flat bars with only tiny
    gamed_metric bleed at high pressure from burnout only.
    Title clarifies this is governance regime.
    """
    rows = []
    all_scenarios = set()
    for cond, calls in calls_dict.items():
        sc_share = calls["scenario"].value_counts(normalize=True)
        all_scenarios.update(sc_share.index)
        for sc, p in sc_share.items():
            rows.append({"condition": LABELS[cond], "scenario": sc, "share": p})

    df = pd.DataFrame(rows).pivot(index="scenario", columns="condition", values="share").fillna(0)
    df["delta_pp"] = (df.get("High Pressure", 0) - df.get("Baseline", 0)) * 100

    # Order: clean scenarios first, then any gaming bleed
    gov_order = ["clean", "unresolvable_clean", "activation_clean",
                 "activation_failed", "line_add_legitimate", "gamed_metric"]
    df = df.reindex([s for s in gov_order if s in df.index])

    fig, ax = plt.subplots(figsize=(8, 4.2))
    fig.patch.set_facecolor("white")

    colors = []
    for sc in df.index:
        is_gam = sc in GAMING_SCENARIOS
        delta  = df.loc[sc, "delta_pp"]
        if is_gam:
            colors.append("#C45B1A" if delta > 0 else "#8B0000")
        else:
            colors.append("#2E5FA3" if delta < 0 else "#555")

    y    = np.arange(len(df))
    bars = ax.barh(y, df["delta_pp"], color=colors, alpha=0.80, zorder=3)

    for bar, val in zip(bars, df["delta_pp"]):
        sign   = "+" if val >= 0 else ""
        offset = 0.02 if val >= 0 else -0.02
        ax.text(val + offset,
                bar.get_y() + bar.get_height() / 2,
                f"{sign}{val:.2f}pp", va="center",
                ha="left" if val >= 0 else "right", fontsize=8.5, color="#333")

    ax.set_yticks(y)
    ax.set_yticklabels(df.index, fontsize=9)
    ax.axvline(0, color="#888", linewidth=1.0)
    ax.set_xlabel("Δ Call Share (High Pressure − Baseline, percentage points)", fontsize=9)
    ax.set_title("Scenario Mix Shift Under High Pressure\n(Governance Regime — gaming only from burnout)",
                 fontsize=11, fontweight="bold")
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    legend_items = [
        mpatches.Patch(color="#2E5FA3", alpha=0.8, label="Honest scenario (share change)"),
        mpatches.Patch(color="#C45B1A", alpha=0.8, label="Burnout-bleed gaming (tiny under pressure)"),
    ]
    ax.legend(handles=legend_items, fontsize=8.5, loc="lower right")
    plt.tight_layout()
    plt.savefig(FIG_DIR / fname, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"    Saved: {fname}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    # Recreate output dirs here so re-runs via call_gen__run_all work correctly
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    EXP_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("NovaWireless-GovernanceLab — Pressure Experiment")
    print("  Theory: remove gaming metrics → pressure causes burnout")
    print("  but NOT gaming scenario shift")
    print(f"  N_REPS:  {N_REPS} per condition")
    print(f"  N_CALLS: {N_CALLS:,} per condition")
    print(f"  Seed:    {SEED}")
    print("=" * 60)

    rng_seed = SEED
    np_rng   = np.random.default_rng(rng_seed)
    py_rng   = random.Random(rng_seed)

    all_rosters = {}
    all_calls   = {}
    summaries   = {}

    for condition, cfg in CONDITIONS.items():
        print(f"\n[{cfg['label']}]  strain={cfg['base_strain']}  pressure={cfg['pressure']}")
        roster, calls = run_condition(condition, cfg, np_rng, py_rng)
        all_rosters[condition] = roster
        all_calls[condition]   = calls
        summaries[condition]   = compute_summary(calls, roster, condition, cfg)

    b = summaries["baseline"]
    h = summaries["high_pressure"]

    print("\n" + "=" * 60)
    print("EXPERIMENT RESULTS — GovernanceLab")
    print("=" * 60)

    metrics = [
        ("Rep Population", [
            ("Mean FCR",               "roster_mean_fcr",        False),
            ("Mean Compliance Risk",   "roster_mean_compliance", True),
            ("Mean Burnout Index",     "roster_mean_burnout",    True),
            ("% High/Peak Strain",     "roster_pct_high_strain", True),
        ]),
        ("Call Outcomes", [
            ("True Resolution Rate",   "call_true_res_rate",         False),
            ("Proxy Resolution Rate",  "call_proxy_res_rate",        None),
            ("Res Gap (proxy−true)",   "call_res_gap",               True),
            ("Repeat Contact 30d",     "call_repeat_30d_rate",       True),
            ("Compliance Event Rate",  "call_compliance_event_rate", True),
        ]),
        ("Gaming Concentration (burnout-bleed only)", [
            ("Gaming Call Share",      "gaming_call_share",      True),
            ("Gaming Mean Burnout",    "gaming_mean_burnout",    True),
        ]),
    ]

    for section, items in metrics:
        print(f"\n  ── {section} ──")
        print(f"  {'Metric':<30} {'Baseline':>10} {'HighPres':>10} {'Delta':>10}")
        print(f"  {'-'*62}")
        for label, key, higher_is_bad in items:
            bv    = b[key]
            hv    = h[key]
            delta = hv - bv
            sign  = "+" if delta >= 0 else ""
            flag  = ("▲" if (delta > 0 and higher_is_bad)
                     else ("▼" if (delta < 0 and higher_is_bad is False) else ""))
            print(f"  {label:<30} {bv:>10.4f} {hv:>10.4f} {sign}{delta:>+9.4f}  {flag}")

    print(f"\nGenerating figures → {FIG_DIR}")

    bar_comparison(
        [("True FCR",       "call_true_res_rate",  "call_true_res_rate"),
         ("Proxy FCR",      "call_proxy_res_rate", "call_proxy_res_rate"),
         ("Resolution Gap", "call_res_gap",        "call_res_gap"),
         ("Repeat 30d",     "call_repeat_30d_rate","call_repeat_30d_rate")],
        summaries,
        "Figure 1 — FCR & Repeat Contact: Baseline vs. High Pressure\n(Governance Regime)",
        "fig1_fcr_repeat.png",
        higher_is_bad=False,
    )

    bar_comparison(
        [("Compliance Risk",    "roster_mean_compliance",     "roster_mean_compliance"),
         ("Burnout Index",      "roster_mean_burnout",        "roster_mean_burnout"),
         ("% High/Peak Strain", "roster_pct_high_strain",     "roster_pct_high_strain"),
         ("Compliance Events",  "call_compliance_event_rate", "call_compliance_event_rate")],
        summaries,
        "Figure 2 — Risk & Strain Accumulation: Baseline vs. High Pressure\n(Governance Regime)",
        "fig2_compliance_strain.png",
        higher_is_bad=True,
    )

    rep_distribution_plot(all_rosters, "fcr_30d",
                          "First Contact Resolution (FCR)", "fig3_fcr_distribution.png")
    rep_distribution_plot(all_rosters, "compliance_risk",
                          "Compliance Risk", "fig4_compliance_distribution.png")

    gaming_shift_plot(all_calls, "fig5_gaming_shift.png")

    print(f"\nWriting data outputs → {EXP_DIR}")
    all_roster_df = pd.concat(all_rosters.values(), ignore_index=True)
    all_calls_df  = pd.concat(all_calls.values(),   ignore_index=True)
    summary_df    = pd.DataFrame(summaries.values())
    all_roster_df.to_csv(EXP_DIR / "experiment_rep_rosters.csv",    index=False)
    all_calls_df.to_csv( EXP_DIR / "experiment_calls.csv",          index=False)
    summary_df.to_csv(   EXP_DIR / "experiment_summary.csv",        index=False)
    print(f"  experiment_rep_rosters.csv  ({len(all_roster_df)} rows)")
    print(f"  experiment_calls.csv        ({len(all_calls_df):,} rows)")
    print(f"  experiment_summary.csv      (2 rows)")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

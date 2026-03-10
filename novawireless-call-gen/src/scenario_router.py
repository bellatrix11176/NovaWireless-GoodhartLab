"""
scenario_router.py
==============================
NovaWireless-GoodhartLab — Scenario Router

Counterfactual to scenario_router.py.

WHAT CHANGED vs. the original:
  - Removed scenarios: gamed_metric, fraud_store_promo, fraud_line_add,
                       fraud_hic_exchange, fraud_care_promo
  - Their weight is redistributed to clean and legitimate scenarios
  - proxy_resolution no longer inflated by gaming_propensity
  - true_resolution no longer degraded by gaming_propensity
  - AHT no longer shortened by gaming (no cherry-picking, no rushing)
  - bandaid credit type REMOVED from CREDIT_CONFIG
  - rep_aware_gaming flag always False (no gaming awareness possible)
  - Three new governance output flags:
      dar_signal    — documentation accuracy signal for this call
      dov_signal    — rep verbalized discomfort/limitation honestly
      trust_delta   — trust change this call (+positive, -negative)

WHAT STAYED THE SAME:
  - clean, unresolvable_clean, activation_clean, activation_failed,
    line_add_legitimate scenarios are unchanged
  - Same probability table structure
  - Same credit types for legitimate scenarios (courtesy, service_credit,
    dispute_credit, fee_waiver)
  - Same AHT multiplier structure for legitimate scenarios

HYPOTHESIS:
  With gaming_propensity=0.0 and no gaming scenarios in the mix,
  proxy_resolution and true_resolution should converge.
  The gap collapses because there's nothing inflating the proxy.
"""

import numpy as np
import pandas as pd
from typing import Tuple


# ---------------------------------------------------------------------------
# Governance experiment scenario mix
# NOTE: fraud/gaming scenarios removed, weight redistributed
# ---------------------------------------------------------------------------

GOODHART_SCENARIO_MIX = {
    "clean":               0.58,   # calibrated to produce 67.6% true FCR
    "unresolvable_clean":  0.17,   # honest unresolvable calls — drives repeat + DOV signal
    "activation_clean":    0.10,
    "activation_failed":   0.07,   # failed activations — honest disclosure required
    "line_add_legitimate": 0.08,
}

# ---------------------------------------------------------------------------
# Burnout-driven gaming bleed
# ---------------------------------------------------------------------------
# In the governance regime, reps have no metric to game.
# The ONLY path to gaming behavior is pure burnout — a rep so exhausted
# they start cutting corners not to hit a number, but because they are
# breaking down. This bleed is intentionally small and only activates
# above a high burnout threshold.
BURNOUT_BLEED_THRESHOLD = 0.75   # burnout_level must exceed this
BURNOUT_BLEED_MAX_PROB  = 0.22   # calibrated: produces ~16.5% gaming share by Dec at peak burnout
BURNOUT_BLEED_SCENARIO  = "gamed_metric"  # softest gaming only — no fraud

# ---------------------------------------------------------------------------
# Outcome probability tables — governance-aligned
# ---------------------------------------------------------------------------

TRUE_RESOLUTION_PROBS = {
    "clean":               0.84,   # hard but resolvable — expert rep earns this, not a freebie
    "unresolvable_clean":  0.10,
    "activation_clean":    0.95,
    "activation_failed":   0.08,
    "line_add_legitimate": 0.93,
    "gamed_metric":        0.20,   # burnout bleed
}

# KEY CHANGE: proxy resolution is no longer inflated by gaming.
# Proxy resolution calibrated to produce 79.8% annual average.
# Unresolvable calls: system still partially misreads these as resolved.
PROXY_RESOLUTION_PROBS = {
    "clean":               0.89,   # calibrated — honest proxy, slightly below true
    "unresolvable_clean":  0.52,   # system still partially misreads unresolvable calls
    "activation_clean":    0.89,
    "activation_failed":   0.48,   # system correctly records most failed activations
    "line_add_legitimate": 0.88,
    "gamed_metric":        0.88,   # burnout bleed — rushed behavior fools the FCR system
}

REPEAT_30D_PROBS = {
    "clean":               0.06,   # calibrated — genuine resolution keeps repeat low
    "unresolvable_clean":  0.38,   # calibrated — unresolved issues drive callbacks
    "activation_clean":    0.05,
    "activation_failed":   0.44,   # calibrated — failed activations drive callbacks
    "line_add_legitimate": 0.06,
    "gamed_metric":        0.50,   # burnout bleed — high repeat
}

REPEAT_31_60D_PROBS = {
    "clean":               0.04,
    "unresolvable_clean":  0.25,
    "activation_clean":    0.03,
    "activation_failed":   0.30,
    "line_add_legitimate": 0.04,
    "gamed_metric":        0.45,
}

# Detection signal probabilities
# (imei_mismatch, nrf_generated, promo_override_post_call,
#  line_added_no_usage, line_added_same_day_store)
# KEY CHANGE: promo_override and gaming-related signals are near-zero
# because there's no gaming behavior to detect
SIGNAL_PROBS = {
    "clean":               (0.02, 0.01, 0.01, 0.01, 0.00),
    "unresolvable_clean":  (0.05, 0.02, 0.02, 0.01, 0.00),
    "activation_clean":    (0.03, 0.00, 0.00, 0.00, 0.00),
    "activation_failed":   (0.60, 0.00, 0.00, 0.00, 0.00),
    "line_add_legitimate": (0.02, 0.00, 0.00, 0.05, 0.00),
    "gamed_metric":        (0.05, 0.03, 0.08, 0.02, 0.00),
}

# rep_aware_gaming: always 0.0 — no gaming awareness in governance regime
REP_AWARE_PROBS = {
    "clean":               0.00,
    "unresolvable_clean":  0.00,
    "activation_clean":    0.00,
    "activation_failed":   0.00,
    "line_add_legitimate": 0.00,
    "gamed_metric":        0.00,   # burnout bleed — rep not strategically aware
}

AHT_MULTIPLIERS = {
    "clean":               1.00,
    "unresolvable_clean":  1.25,   # honest handling of hard calls takes longer
    "activation_clean":    1.10,
    "activation_failed":   1.35,
    "line_add_legitimate": 1.20,
    "gamed_metric":        0.80,   # burnout bleed — rushed call
}

ESCALATION_PROBS = {
    "clean":               0.05,
    "unresolvable_clean":  0.25,
    "activation_clean":    0.03,
    "activation_failed":   0.30,
    "line_add_legitimate": 0.04,
    "gamed_metric":        0.45,
}

SCENARIO_CALL_TYPE = {
    "clean":               None,
    "unresolvable_clean":  None,
    "activation_clean":    "Device Issue",
    "activation_failed":   "Device Issue",
    "line_add_legitimate": "Account Inquiry",
    "gamed_metric":        None,
}

SCENARIO_SUBREASON = {
    "clean":               None,
    "unresolvable_clean":  None,
    "activation_clean":    "Device activation",
    "activation_failed":   "Activation failed",
    "line_add_legitimate": "Add a line",
    "gamed_metric":        None,
}

SCENARIO_CHURN_MULTIPLIERS = {
    "clean":               1.00,
    "unresolvable_clean":  1.40,
    "activation_clean":    0.90,
    "activation_failed":   1.35,
    "line_add_legitimate": 0.85,
    "gamed_metric":        1.25,
}

SCENARIO_TRUST_DECAY = {
    "clean":               0.00,
    "unresolvable_clean":  0.05,   # trust decays when issues can't be resolved — but honestly
    "activation_clean":    0.00,
    "activation_failed":   0.04,
    "line_add_legitimate": 0.00,
    "gamed_metric":        0.00,   # burnout bleed — rep not strategically aware
}

# ---------------------------------------------------------------------------
# Governance signal tables — NEW
# ---------------------------------------------------------------------------

# DAR signal: probability that this call's documentation is fully accurate
# Higher for clean/simple calls, lower for complex unresolvable ones
DAR_SIGNAL_PROBS = {
    "clean":               0.894,  # calibrated: 0.58×0.894 + other scenarios = 91.5% annual avg
    "unresolvable_clean":  0.93,   # governance coaching improves documentation accuracy
    "activation_clean":    0.97,
    "activation_failed":   0.90,   # complex but well-documented under governance
    "line_add_legitimate": 0.98,
    "gamed_metric":        0.45,   # burnout bleed — poor documentation
}

# DOV signal: probability rep verbalized a limitation honestly this call
# High on unresolvable (rep had to say "I can't fix this")
# Lower on clean calls (nothing to disclose)
DOV_SIGNAL_PROBS = {
    "clean":               0.15,   # low — most clean calls don't require DOV
    "unresolvable_clean":  0.91,   # calibrated — produces 89.2% weighted DOV benchmark
    "activation_clean":    0.10,
    "activation_failed":   0.91,   # symmetric with unresolvable_clean
    "line_add_legitimate": 0.12,
    "gamed_metric":        0.05,   # burnout bleed — rep not honest about limitation
    # NOTE: gamed_metric is EXCLUDED from DOV denominator in l06_dov.py
    # DOV is only measured on structurally-unresolvable calls (unresolvable_clean, activation_failed)
}

# Trust delta: expected trust change this call
# Positive = trust built, negative = trust lost
TRUST_DELTA_EXPECTED = {
    "clean":               +0.10,   # calibrated — produces +0.059 annual avg trust delta
    "unresolvable_clean":  -0.01,   # honest disclosure softens trust loss
    "activation_clean":    +0.09,
    "activation_failed":   -0.04,
    "line_add_legitimate": +0.10,   # calibrated
    "gamed_metric":        -0.06,   # burnout bleed — trust erodes
}


# ---------------------------------------------------------------------------
# Credit tables — governance-aligned
# ---------------------------------------------------------------------------
# "bandaid" credit type REMOVED — unauthorized credits that suppress repeat
# contact / game FCR do not exist in the governance regime.
#
# gamed_metric credits remain but use "courtesy" (lower probability, authorized)
# — a burned-out rep may reflexively apply a small goodwill credit, not as
# deliberate gaming but as a cognitive shortcut to close a difficult call.
#
# Remaining credit types:
#   "none"           — no credit applied
#   "courtesy"       — legitimate goodwill credit, authorized
#   "service_credit" — appeasement for unresolved issue, authorized
#   "dispute_credit" — interim credit while investigation is open, authorized
#   "fee_waiver"     — erroneous fee reversed, authorized

CREDIT_CONFIG = {
    "clean_billing":       (0.70, "courtesy",       True,  10.0, 15.0),
    "clean_promo":         (0.90, "courtesy",       True,  10.0, 10.0),
    "clean_other":         (0.00, "none",            True,   0.0,  0.0),
    "unresolvable_clean":  (0.85, "service_credit",  True,  20.0, 25.0),
    # gamed_metric: burnout-bleed scenario.
    #   _aware  — rep semi-consciously applies a small credit to soften the close.
    #             Uses "courtesy" (NOT "bandaid") — the rep isn't strategically gaming,
    #             just defaulting to an easy close under cognitive load.
    #   _naive  — rep closes without a credit (most common; no intent present).
    "gamed_metric_aware":  (0.35, "courtesy",        True,  5.0,  15.0),
    "gamed_metric_naive":  (0.00, "none",             True,  0.0,   0.0),
    "activation_clean":    (0.00, "none",            True,   0.0,  0.0),
    "activation_failed":   (0.90, "service_credit",  True,   5.0, 10.0),
    "line_add_legitimate": (0.00, "none",            True,   0.0,  0.0),
}


def build_credit(
    rng: np.random.Generator,
    scenario: str,
    call_type: str,
    rep_aware: bool,   # always False in governance regime, kept for interface compatibility
) -> dict:
    """
    Determine credit for governance-aligned calls.
    bandaid credit type does not exist in this regime.
    All credits are authorized.
    """
    if scenario == "clean":
        if call_type in ("Billing Dispute", "Payment Arrangement"):
            key = "clean_billing"
        elif call_type == "Promotion Inquiry":
            key = "clean_promo"
        else:
            key = "clean_other"
    elif scenario == "gamed_metric":
        key = "gamed_metric_aware" if rep_aware else "gamed_metric_naive"
    else:
        key = scenario

    cfg = CREDIT_CONFIG.get(key, (0.00, "none", True, 0.0, 0.0))
    prob, credit_type, authorized, amt_min, amt_max = cfg

    if prob == 0.0 or rng.random() > prob:
        return {
            "credit_applied":    False,
            "credit_amount":     0.0,
            "credit_type":       "none",
            "credit_authorized": True,
        }

    amount = round(float(rng.uniform(amt_min, amt_max)), 2) if amt_max > amt_min else amt_min

    return {
        "credit_applied":    True,
        "credit_amount":     amount,
        "credit_type":       credit_type,
        "credit_authorized": authorized,
    }


# ---------------------------------------------------------------------------
# Detection flags — governance-aligned
# ---------------------------------------------------------------------------

def build_detection_flags(
    rng: np.random.Generator,
    scenario: str,
    ledger_row,
    rep_state: dict | None = None,
) -> dict:
    """
    Build detection flags for governance-aligned calls.

    KEY CHANGES:
    - gaming_propensity is 0.0 — no amplification of promo_override
    - rep_aware_gaming is always False
    - Fraud scenarios don't exist so their signal patterns are gone
    """
    probs = SIGNAL_PROBS[scenario]
    p_imei, p_nrf, p_promo_override, p_no_usage, p_store_same_day = probs

    # gaming_propensity is 0.0 in governance regime — no amplification
    skill = rep_state.get("policy_skill", 0.5) if rep_state else 0.5

    # p_promo_override is already near-zero in governance tables
    # No gaming amplification applied
    if scenario in {"clean", "unresolvable_clean"}:
        p_nrf      = p_nrf      * max(0.1, 1.0 - skill * 0.5)
        p_no_usage = p_no_usage * max(0.1, 1.0 - skill * 0.5)

    fraud_scenarios = {"fraud_line_add", "fraud_hic_exchange"}   # kept for safety but never called
    if (scenario in fraud_scenarios and ledger_row is not None
            and "imei_mismatch_flag" in ledger_row.index):
        imei_mismatch = bool(ledger_row["imei_mismatch_flag"])
    else:
        imei_mismatch = bool(rng.random() < p_imei)

    return {
        "imei_mismatch_flag":        imei_mismatch,
        "nrf_generated_flag":        bool(rng.random() < p_nrf),
        "promo_override_post_call":  bool(rng.random() < p_promo_override),
        "line_added_no_usage_flag":  bool(rng.random() < p_no_usage),
        "line_added_same_day_store": bool(rng.random() < p_store_same_day),
        "rep_aware_gaming":          False,   # always False in governance regime
    }


# ---------------------------------------------------------------------------
# Outcome flags — governance-aligned
# ---------------------------------------------------------------------------

def build_outcome_flags(
    rng: np.random.Generator,
    scenario: str,
    agent_friction_tier: str,
    rep_state: dict | None = None,
) -> dict:
    """
    Build outcome flags for governance-aligned calls.

    KEY CHANGES:
    - gaming_propensity is 0.0 — proxy resolution no longer inflated
    - true_resolution no longer degraded by gaming
    - proxy and true resolution should be close (this is the gap collapse)
    - Three new governance signal columns added
    - incorrect_info_given: driven by rep misinformation_risk (tenure-based)
      — degrades true_resolution and raises repeat_contact_31_60d
    - churned: binary outcome tied to true_resolution + scenario
      — NOT tied to resolution_flag (proxy) to preserve TER signal
    """
    friction_mult = {"low": 0.85, "normal": 1.00, "high": 1.15, "peak": 1.30}
    fm          = friction_mult.get(agent_friction_tier, 1.0)
    burnout     = rep_state.get("burnout_level",       0.0) if rep_state else 0.0
    skill       = rep_state.get("policy_skill",        0.5) if rep_state else 0.5
    misinfo     = rep_state.get("misinformation_risk", 0.0) if rep_state else 0.0
    tenure_band = rep_state.get("tenure_band",     "senior") if rep_state else "senior"

    # ── incorrect_info_given ──────────────────────────────────────────────────
    # Driven purely by misinformation_risk (which is tenure + burnout + QA).
    # Activation and line_add scenarios have higher consequence — bad info
    # on a device activation is more harmful than on a billing question.
    misinfo_scenario_mult = {
        "clean":               1.0,
        "unresolvable_clean":  0.8,   # rep knows they can't fix it — less room for bad advice
        "activation_clean":    1.3,   # bad advice here causes real device problems
        "activation_failed":   1.2,
        "line_add_legitimate": 1.2,
        "gamed_metric":        1.1,
    }.get(scenario, 1.0)

    p_misinfo = min(misinfo * misinfo_scenario_mult, 0.95)
    incorrect_info_given = bool(rng.random() < p_misinfo)

    # ── Base resolution probabilities ─────────────────────────────────────────
    p_proxy = PROXY_RESOLUTION_PROBS[scenario]
    p_true  = TRUE_RESOLUTION_PROBS[scenario]

    if scenario in {"clean", "activation_clean", "line_add_legitimate"}:
        p_true = min(p_true * (1.0 + skill * 0.30), 0.99)
    elif scenario in {"unresolvable_clean", "activation_failed"}:
        p_true = min(p_true * (1.0 + skill * 0.15), 0.99)

    # incorrect_info_given degrades true_resolution regardless of scenario
    # — customer acts on bad advice, issue doesn't stay resolved
    if incorrect_info_given:
        p_true = p_true * 0.55   # significant degradation — bad info kills resolution

    p_escalate  = min(ESCALATION_PROBS[scenario]    * (1.0 + burnout * 0.5) * fm, 0.99)
    p_repeat_30 = min(REPEAT_30D_PROBS[scenario]    * (1.0 + burnout * 0.3) * fm, 0.99)
    # incorrect_info elevates 31–60d repeat — customer realizes advice was wrong later
    p_repeat_31 = min(REPEAT_31_60D_PROBS[scenario] * (1.0 + burnout * 0.3) * fm, 0.99)
    if incorrect_info_given:
        p_repeat_31 = min(p_repeat_31 * 1.60, 0.99)

    # Governance signals
    dar_signal  = bool(rng.random() < DAR_SIGNAL_PROBS[scenario])
    dov_signal  = bool(rng.random() < DOV_SIGNAL_PROBS[scenario])

    base_delta  = TRUST_DELTA_EXPECTED[scenario]
    trust_delta = round(float(base_delta + rng.normal(0, 0.04)), 4)

    true_res = bool(rng.random() < p_true)

    # ── churned ───────────────────────────────────────────────────────────────
    # Tied to TRUE resolution outcome, not proxy.
    # Base churn probability by scenario reflects structural risk.
    # Unresolved calls and bad-info calls have elevated churn.
    # incorrect_info_given adds an independent churn tick.
    BASE_CHURN_PROB = {
        "clean":               0.04,
        "unresolvable_clean":  0.12,
        "activation_clean":    0.02,
        "activation_failed":   0.10,
        "line_add_legitimate": 0.02,
        "gamed_metric":        0.08,
    }
    p_churn = BASE_CHURN_PROB.get(scenario, 0.05)
    if not true_res:
        p_churn = min(p_churn * 2.2, 0.60)   # unresolved → much higher churn
    if incorrect_info_given:
        p_churn = min(p_churn + 0.06, 0.70)  # bad advice adds independent churn risk
    churned = bool(rng.random() < p_churn)

    return {
        "true_resolution":       true_res,
        "resolution_flag":       bool(rng.random() < p_proxy),
        "repeat_contact_30d":    bool(rng.random() < p_repeat_30),
        "repeat_contact_31_60d": bool(rng.random() < p_repeat_31),
        "escalation_flag":       bool(rng.random() < p_escalate),
        "incorrect_info_given":  incorrect_info_given,
        "churned":               churned,
        # Governance signals — NEW
        "dar_signal":            dar_signal,
        "dov_signal":            dov_signal,
        "trust_delta":           trust_delta,
    }


# ---------------------------------------------------------------------------
# AHT — governance-aligned
# ---------------------------------------------------------------------------

def get_aht(
    rng: np.random.Generator,
    scenario: str,
    base_secs: float,
    agent_aht_secs: float,
    friction_multiplier: float,
    rep_state: dict | None = None,
) -> int:
    """
    AHT for governance-aligned calls.

    KEY CHANGE: gaming_propensity was shortening AHT by up to 25%.
    In governance regime, reps don't rush calls to game throughput metrics.
    AHT reflects actual call complexity, not gaming pressure.
    """
    burnout = rep_state.get("burnout_level", 0.0) if rep_state else 0.0
    skill   = rep_state.get("policy_skill",  0.5) if rep_state else 0.5

    # No gaming shortening — state_mult only reflects burnout and skill
    state_mult  = 1.0
    state_mult *= 1.0 + burnout * 0.20
    if scenario in {"clean", "unresolvable_clean"}:
        state_mult *= max(0.7, 1.0 - skill * 0.15)

    aht   = agent_aht_secs * AHT_MULTIPLIERS[scenario] * friction_multiplier * state_mult
    noise = rng.uniform(0.80, 1.20)
    return max(60, int(aht * noise))


# ---------------------------------------------------------------------------
# Scenario assignment
# ---------------------------------------------------------------------------

def assign_scenario(rng: np.random.Generator, scenario_mix: dict,
                    rep_state: dict | None = None) -> str:
    """
    Assign a scenario to this call.

    For most calls uses the standard scenario_mix.
    If rep_state is provided and burnout_level exceeds the bleed threshold,
    there is a small burnout-proportional chance the call becomes a
    gamed_metric scenario — stress-induced corner cutting, not metric gaming.
    """
    if rep_state is not None:
        burnout = rep_state.get("burnout_level", 0.0)
        if burnout > BURNOUT_BLEED_THRESHOLD:
            bleed_range     = 1.0 - BURNOUT_BLEED_THRESHOLD
            bleed_intensity = (burnout - BURNOUT_BLEED_THRESHOLD) / bleed_range
            bleed_prob      = bleed_intensity * BURNOUT_BLEED_MAX_PROB
            if rng.random() < bleed_prob:
                return BURNOUT_BLEED_SCENARIO

    scenarios = list(scenario_mix.keys())
    weights   = np.array(list(scenario_mix.values()), dtype=float)
    weights  /= weights.sum()
    return rng.choice(scenarios, p=weights)

#!/usr/bin/env python3
"""
generate_employees_call_center_one_queue.py
============================================
NovaWireless-GoodhartLab — Representative Generator

Models how the call center workforce operates TODAY.
Reps are measured on proxy resolution rate (FCR).
Gaming behavior is present and compounds over time.

This is the PROBLEM lab. For the solution, see:
NovaWireless-GovernanceLab/src/generate_employees_governance.py

KEY PARAMETERS (as-is / today):
  base_strain            = 0.52   (elevated — understaffed, high pressure)
  base_training          = 6.5    (months — below industry standard)
  compliance_risk        = synthesized from burnout, QA, escalation
  gaming_propensity      = derived from compliance_risk
  experiment_condition   = "goodhart_baseline"

GAMING LOGIC:
  compliance_risk is a real signal here. Reps with high burnout,
  low QA, and high escalation proneness develop elevated compliance_risk,
  which seeds gaming_propensity in the call generator.

  gaming_propensity then compounds per call in generate_calls.py:
    +2% per gamed call
    +1% per bandaid credit applied

  This is what creates the 42-point Goodhart gap:
    proxy_resolution inflated by gaming_propensity
    true_resolution degraded by gaming_propensity

COUNTERFACTUAL:
  To see what happens when gaming is removed, see GovernanceLab.
  Same 250 reps, same data sources — gaming_propensity hardcoded to 0.0.

Run:
  python src/generate_employees_call_center_one_queue.py --n 250 --seed 1337 --site NovaWireless
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from utils import find_repo_root
from typing import Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Repo-root helpers
# ---------------------------------------------------------------------------



def pick_input_dir(repo_root: Path) -> Path:
    cand = repo_root / "data" / "employee_generation_inputs"
    if cand.exists():
        return cand
    sandbox = Path("/mnt/data")
    if sandbox.exists():
        return sandbox
    raise FileNotFoundError(
        "Could not find data/employee_generation_inputs/ (and no /mnt/data fallback)."
    )


def ensure_output_dir(repo_root: Path) -> Path:
    out = repo_root / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def stable_run_id(seed: int, files: List[Path]) -> str:
    h = hashlib.sha256()
    h.update(str(seed).encode("utf-8"))
    for p in sorted(files, key=lambda x: x.name.lower()):
        try:
            stat = p.stat()
            h.update(p.name.encode("utf-8"))
            h.update(str(stat.st_size).encode("utf-8"))
            h.update(str(int(stat.st_mtime)).encode("utf-8"))
        except Exception:
            continue
    return h.hexdigest()[:10]


def non_overwriting_path(out_dir: Path, base_name: str, ext: str) -> Path:
    p = out_dir / f"{base_name}.{ext}"
    if not p.exists():
        return p
    i = 2
    while True:
        p2 = out_dir / f"{base_name}__v{i}.{ext}"
        if not p2.exists():
            return p2
        i += 1


# ---------------------------------------------------------------------------
# Random utilities
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def z_noise(rng: random.Random, sigma: float = 0.15) -> float:
    u1 = max(1e-9, rng.random())
    u2 = rng.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return z * sigma


def weighted_choice(rng: random.Random, items: List[Tuple[str, float]]) -> str:
    total = sum(w for _, w in items)
    if total <= 0:
        return items[0][0]
    r = rng.random() * total
    acc = 0.0
    for v, w in items:
        acc += w
        if r <= acc:
            return v
    return items[-1][0]


# ---------------------------------------------------------------------------
# Name pools
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Aaliyah","Aaron","Abigail","Adam","Adrian","Aiden","Alana","Alejandro","Alex","Alexa","Alexander","Alexis",
    "Amelia","Amir","Amy","Ana","Andre","Andrea","Andrew","Angela","Anita","Anna","Anthony","Ari","Ariana",
    "Ashley","Ashton","Ava","Avery","Bailey","Barbara","Benjamin","Brianna","Brittany","Caleb","Cameron","Carlos",
    "Carmen","Caroline","Carter","Casey","Catherine","Charles","Charlotte","Chloe","Chris","Christian","Christina",
    "Claire","Clara","Cole","Connor","Courtney","Daisy","Dakota","Daniel","Danielle","David","Derek","Diana","Diego",
    "Dominic","Drew","Dylan","Eleanor","Elena","Eli","Elijah","Elizabeth","Ella","Elliot","Emily","Emma","Eric",
    "Ethan","Eva","Evelyn","Faith","Finn","Gabriel","Gabriella","Gavin","Genesis","George","Grace","Hailey","Hannah",
    "Harper","Hayden","Hazel","Henry","Isabella","Isaiah","Jace","Jack","Jackson","Jacob","Jada","Jaden","Jake",
    "James","Jamie","Jasmine","Jason","Jayden","Jennifer","Jeremiah","Jessica","John","Jonathan","Jordan","Jose",
    "Joseph","Joshua","Julia","Julian","Kaitlyn","Katherine","Kayla","Kevin","Kimberly","Kyle","Landon","Laura",
    "Lauren","Leah","Leo","Liam","Lily","Logan","Lucas","Lucy","Luis","Madison","Makayla","Maria","Mason","Mateo",
    "Matthew","Maya","Megan","Mia","Michael","Michelle","Mila","Naomi","Natalie","Nathan","Nicholas","Noah","Nora",
    "Oliver","Olivia","Owen","Parker","Paul","Penelope","Quinn","Riley","Robert","Samantha","Samuel","Sara","Sarah",
    "Sebastian","Sofia","Sophia","Taylor","Thomas","Tristan","Tyler","Victoria","William","Zoe"
]

LAST_NAMES = [
    "Adams","Allen","Alvarez","Anderson","Baker","Barnes","Bell","Bennett","Brooks","Brown","Butler","Campbell",
    "Carter","Castillo","Chang","Chen","Clark","Collins","Cook","Cooper","Cox","Cruz","Davis","Diaz","Edwards",
    "Evans","Flores","Foster","Garcia","Gomez","Gonzalez","Gray","Green","Gupta","Hall","Harris","Hernandez","Hill",
    "Howard","Hughes","Jackson","James","Jenkins","Johnson","Jones","Kaur","Kelley","Kelly","Khan","Kim","King",
    "Lee","Lewis","Lopez","Martin","Martinez","Miller","Mitchell","Moore","Morales","Morgan","Murphy","Nelson",
    "Nguyen","Ortiz","Parker","Patel","Perez","Peterson","Phillips","Powell","Price","Ramirez","Reed","Richardson",
    "Rivera","Roberts","Robinson","Rodriguez","Rogers","Ross","Ruiz","Sanchez","Sanders","Scott","Shah","Singh",
    "Smith","Stewart","Taylor","Thomas","Thompson","Torres","Turner","Walker","Ward","Watson","White","Williams",
    "Wilson","Wong","Wright","Young"
]


def make_unique_simple_name(
    rng: random.Random,
    used_pairs: set,
    max_tries: int = 20000
) -> Tuple[str, str]:
    for _ in range(max_tries):
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        key = (fn, ln)
        if key not in used_pairs:
            used_pairs.add(key)
            return fn, ln
    raise RuntimeError("Unable to generate a unique first/last pair.")


# ---------------------------------------------------------------------------
# Priors loading
# ---------------------------------------------------------------------------

@dataclass
class Priors:
    persona_priors: Optional[pd.DataFrame]
    fcc_specialization: Optional[pd.DataFrame]
    pressure_weekday: Optional[pd.DataFrame]
    telco_segment_pressure: Optional[pd.DataFrame]


def load_priors(input_dir: Path) -> Tuple[Priors, List[Path]]:
    used: List[Path] = []

    def first(patterns: List[str]) -> Optional[Path]:
        for pat in patterns:
            hits = sorted(input_dir.glob(pat))
            if hits:
                used.append(hits[0])
                return hits[0]
        return None

    persona_p  = first(["kaggle_employee_persona_priors*.csv"])
    fcc_spec_p = first(["fcc_cgb_consumer_complaints__rep_specialization_priors*.csv"])
    weekday_p  = first(["kaggle_call_center_weekday_pressure*.csv"])
    telco_p    = first(["ibm_telco_segment_pressure*.csv"])

    return Priors(
        persona_priors         = pd.read_csv(persona_p)  if persona_p  else None,
        fcc_specialization     = pd.read_csv(fcc_spec_p) if fcc_spec_p else None,
        pressure_weekday       = pd.read_csv(weekday_p)  if weekday_p  else None,
        telco_segment_pressure = pd.read_csv(telco_p)    if telco_p    else None,
    ), used


# ---------------------------------------------------------------------------
# Skill tag mapping
# ---------------------------------------------------------------------------

SKILL_LABELS = {
    "general_support":      "general_support",
    "billing_resolution":   "billing_support",
    "device_support":       "device_support",
    "network_service":      "tech_support",
    "porting_transfer":     "porting_support",
    "fraud_unwanted_calls": "fraud_unwanted_calls",
}


def lookup_persona(priors: Priors) -> Dict[str, float]:
    out = {
        "patience":             0.55,
        "empathy":              0.55,
        "escalation_proneness": 0.45,
        "burnout_risk":         0.45,
    }
    df = priors.persona_priors
    if df is None or df.empty:
        return out

    if "n" in df.columns:
        w     = pd.to_numeric(df["n"], errors="coerce").fillna(1.0).tolist()
        total = float(sum(w) or 1.0)
        r     = random.random() * total
        acc   = 0.0
        idx   = 0
        for i, wi in enumerate(w):
            acc += wi
            if r <= acc:
                idx = i
                break
        row = df.iloc[idx].to_dict()
    else:
        row = df.sample(1).iloc[0].to_dict()

    for k, col in [
        ("patience",             "patience_mean"),
        ("empathy",              "empathy_mean"),
        ("escalation_proneness", "escalation_proneness_mean"),
        ("burnout_risk",         "burnout_risk_mean"),
    ]:
        if col in row and pd.notna(row[col]):
            out[k] = clamp(float(row[col]))
    return out


def sample_skill_pair(priors: Priors, rng: random.Random) -> Tuple[str, str]:
    default = [
        ("general_support",      0.25),
        ("network_service",      0.20),
        ("device_support",       0.18),
        ("billing_resolution",   0.18),
        ("porting_transfer",     0.10),
        ("fraud_unwanted_calls", 0.09),
    ]
    df     = priors.fcc_specialization
    skills = default
    if df is not None and not df.empty and "skill_tag" in df.columns:
        tmp = df.copy()
        if "p" in tmp.columns:
            tmp["p"] = pd.to_numeric(tmp["p"], errors="coerce").fillna(0.0)
            skills   = [(str(r["skill_tag"]), float(r["p"]))
                        for _, r in tmp.iterrows() if float(r["p"]) > 0]
        else:
            tmp["count"] = pd.to_numeric(tmp.get("count", 1), errors="coerce").fillna(1.0)
            total        = float(tmp["count"].sum() or 1.0)
            skills       = [(str(r["skill_tag"]), float(r["count"]) / total)
                            for _, r in tmp.iterrows()]

    primary = weighted_choice(rng, skills)
    bias    = {k: w for k, w in skills}
    bias[primary] = bias.get(primary, 0.0) * 0.15
    secondary = weighted_choice(rng, list(bias.items()))
    if secondary == primary:
        secondary = "general_support" if primary != "general_support" else "device_support"
    return primary, secondary


def assign_strain_tier(x: float) -> str:
    if x < 0.35: return "low"
    if x < 0.55: return "medium"
    if x < 0.75: return "high"
    return "very_high"


# ---------------------------------------------------------------------------
# KPI synthesis — Goodhart baseline (gaming ON)
# ---------------------------------------------------------------------------

def synthesize_kpis(
    rng: random.Random,
    persona: Dict[str, float],
    base_strain: float,
    base_training: float,
    pressure: float,
    primary_skill: str,
) -> Dict[str, float]:
    """
    Goodhart baseline KPI model — gaming logic ACTIVE.

    KEY DIFFERENCES from GovernanceLab synthesize_kpis_governance():
    - base_strain   = 0.52 (elevated — understaffed scenario)
    - base_training = 6.5  (below industry standard)
    - compliance_risk is SYNTHESIZED from burnout, QA, escalation
    - gaming_propensity is DERIVED from compliance_risk

    compliance_risk formula:
        0.10 + 0.35*burnout + 0.25*(1-qa) + 0.12*escalation + noise

    This feeds gaming_propensity in generate_calls.py:
        gaming_propensity = clip(compliance_risk, 0.0, 1.0)

    Which then compounds per call:
        +0.02 per gamed call
        +0.01 per bandaid credit

    Result: proxy_resolution inflates, true_resolution degrades,
    the Goodhart gap widens over time. This is the 42pp gap.
    """
    # Core state — same formula, higher inputs produce higher burnout
    burnout = clamp(
        0.55 * persona["burnout_risk"]
        + 0.30 * base_strain
        + 0.15 * (pressure - 0.5)
        - 0.10 * persona["patience"]
        + z_noise(rng, 0.10)
    )
    resilience = clamp(
        1.0 - burnout * 0.65
        + (base_training / 12.0) * 0.20
        + z_noise(rng, 0.08)
    )
    volatility = clamp(0.30 + burnout * 0.60 + z_noise(rng, 0.12))

    # Quality signal — lower training suppresses QA
    qa = clamp(
        0.58
        + 0.12 * persona["patience"]
        + 0.10 * (base_training / 12.0)
        - 0.18 * burnout
        + z_noise(rng, 0.06)
    )

    skill_bonus = {
        "billing_resolution":   0.02,
        "network_service":      0.02,
        "device_support":       0.015,
        "porting_transfer":     0.01,
        "fraud_unwanted_calls": 0.01,
        "general_support":      0.00,
    }.get(primary_skill, 0.0)

    fcr = clamp(
        0.55
        + 0.18 * qa
        + 0.10 * persona["patience"]
        + skill_bonus
        - 0.18 * burnout
        - 0.08 * (pressure - 0.5)
        + z_noise(rng, 0.06),
        0.10, 0.95,
    )

    base_aht = 560.0
    aht = clamp(
        base_aht
        * (1.0 + 0.35 * burnout + 0.18 * (pressure - 0.5))
        * (1.0 - 0.08 * (base_training / 12.0))
        * (1.0 - 0.06 * qa)
        + (z_noise(rng, 0.20) * 120),
        240.0, 1600.0,
    )

    escalation = clamp(
        0.05
        + 0.18 * persona["escalation_proneness"]
        + 0.10 * burnout
        - 0.12 * qa
        + z_noise(rng, 0.04),
        0.01, 0.55,
    )
    transfer = clamp(
        0.03
        + 0.10 * (1.0 - qa)
        + 0.08 * burnout
        - 0.04 * persona["patience"]
        + z_noise(rng, 0.04),
        0.01, 0.45,
    )
    repeat = clamp(
        0.08
        + 0.65 * (1.0 - fcr)
        + 0.06 * (pressure - 0.5)
        + z_noise(rng, 0.04),
        0.02, 0.80,
    )
    csat = clamp(
        0.52
        + 0.24 * persona["empathy"]
        + 0.16 * qa
        - 0.18 * burnout
        - 0.08 * escalation
        + z_noise(rng, 0.05),
        0.10, 0.95,
    )

    aht_norm     = clamp((1600.0 - aht) / (1600.0 - 240.0))
    productivity = clamp(
        0.42 * fcr + 0.33 * qa + 0.25 * aht_norm
        - 0.15 * burnout
        + z_noise(rng, 0.04)
    )

    # -----------------------------------------------------------------------
    # GAMING LOGIC — active in GoodhartLab, absent in GovernanceLab
    # -----------------------------------------------------------------------

    # compliance_risk: synthesized from real workforce signals
    # High burnout + low QA + high escalation = high compliance risk
    # This is the rep characteristic that makes gaming more likely
    compliance_risk = clamp(
        0.10
        + 0.35 * burnout
        + 0.25 * (1.0 - qa)
        + 0.12 * escalation
        + z_noise(rng, 0.06),
        0.01, 0.95,
    )

    # gaming_propensity: seeded from compliance_risk at rep creation
    # Will compound further in generate_calls.py as calls are handled:
    #   +0.02 per gamed call (rep learns it's safe)
    #   +0.01 per bandaid credit (hush-money pattern reinforces gaming)
    gaming_propensity = clamp(compliance_risk + z_noise(rng, 0.04), 0.0, 1.0)

    return {
        # Standard KPIs
        "qa_score":             round(qa,           4),
        "fcr_30d":              round(fcr,          4),
        "repeat_contact_rate":  round(repeat,       4),
        "aht_secs":             round(aht,          2),
        "csat_proxy":           round(csat,         4),
        "transfer_rate":        round(transfer,     4),
        "escalation_rate":      round(escalation,   4),
        "productivity_index":   round(productivity, 4),
        "burnout_index":        round(clamp(0.15 + 0.85 * burnout), 4),
        "resilience_index":     round(resilience,   4),
        "volatility_index":     round(volatility,   4),
        # Gaming signals — ACTIVE
        "compliance_risk":      round(compliance_risk,   4),
        "gaming_propensity":    round(gaming_propensity, 4),
        # NOTE: misinformation_risk is synthesized in main() after months_on_job
        # is assigned, because it depends on tenure. Placeholder here is 0.0.
        "misinformation_risk":  0.0,
    }


# ---------------------------------------------------------------------------
# Tenure helpers
# ---------------------------------------------------------------------------

def assign_tenure_band(months: int) -> str:
    """
    Classify rep tenure into three experience bands.
    new    : 0–6 months  — still learning policy, high misinformation risk
    mid    : 7–18 months — competent but still developing
    senior : 19+ months  — experienced, low misinformation risk
    """
    if months <= 6:
        return "new"
    if months <= 18:
        return "mid"
    return "senior"


def synthesize_misinformation_risk(
    rng: random.Random,
    months_on_job: int,
    qa_score: float,
    burnout_index: float,
) -> float:
    """
    Probability a rep gives incorrect information on a given call.

    New reps have high baseline misinformation risk — they don't know
    policy well enough yet. This degrades true resolution on calls they
    handle and elevates 31–60d repeat contacts (customer calls back after
    acting on bad advice). Senior reps have very low risk.

    Burnout amplifies misinformation for all tenure bands — exhausted
    reps skip verification steps regardless of experience level.

    misinformation_risk formula:
        base (by tenure) + burnout amplifier + QA suppressor + noise

    This feeds incorrect_info_given in generate_calls.py, which in turn
    degrades true_resolution and increases repeat_contact_31_60d.
    """
    # Tenure base: inverse exponential decay
    # new=0.35, mid=0.15, senior=0.05 at mean burnout/QA
    if months_on_job <= 6:
        base = 0.35
    elif months_on_job <= 18:
        base = 0.15 + 0.20 * max(0.0, (18 - months_on_job) / 12.0)
    else:
        # Slow asymptotic decay toward 0.04 floor for very senior reps
        base = max(0.04, 0.13 * math.exp(-0.04 * (months_on_job - 18)))

    # Burnout amplifies risk — tired reps skip verification steps
    burnout_amp = 0.20 * burnout_index

    # QA suppresses risk — high QA means rep catches own errors
    qa_suppress = 0.10 * qa_score

    risk = clamp(base + burnout_amp - qa_suppress + z_noise(rng, 0.04))
    return round(risk, 4)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="NovaWireless-GoodhartLab — Employee Generator (single queue)")
    ap.add_argument("--n",          type=int, default=250)
    ap.add_argument("--seed",       type=int, default=1337)
    ap.add_argument("--site",       type=str, default="NovaWireless")
    ap.add_argument("--queue_name", type=str, default="General Support")
    args = ap.parse_args()

    repo_root = find_repo_root()
    input_dir = pick_input_dir(repo_root)
    out_dir   = ensure_output_dir(repo_root)

    priors, used_files = load_priors(input_dir)
    rng = random.Random(args.seed)

    # -----------------------------------------------------------------------
    # Goodhart baseline parameters — TODAY's call center
    # Compare to GovernanceLab: base_strain=0.35, base_training=9.0
    # -----------------------------------------------------------------------
    BASE_STRAIN   = 0.52   # elevated — understaffed, high structural pressure
    BASE_TRAINING = 6.5    # months — below industry standard

    pressure = 0.5
    if priors.pressure_weekday is not None and "pressure_index" in priors.pressure_weekday.columns:
        v = pd.to_numeric(priors.pressure_weekday["pressure_index"], errors="coerce").dropna()
        if not v.empty:
            pressure = float(v.mean())
    if priors.telco_segment_pressure is not None and "pressure_index" in priors.telco_segment_pressure.columns:
        v = pd.to_numeric(priors.telco_segment_pressure["pressure_index"], errors="coerce").dropna()
        if not v.empty:
            pressure = clamp(pressure + 0.05 * (float(v.mean()) - 0.5))

    department = "Call Center"
    job_role   = "Customer Service Representative"

    used_name_pairs: set = set()
    reps: List[dict] = []

    for i in range(args.n):
        rep_id     = f"REP{(i + 1):05d}"
        first_name, last_name = make_unique_simple_name(rng, used_name_pairs)
        rep_name   = f"{first_name} {last_name}"

        persona                        = lookup_persona(priors)
        primary_skill, secondary_skill = sample_skill_pair(priors, rng)

        kpis = synthesize_kpis(
            rng           = rng,
            persona       = persona,
            base_strain   = BASE_STRAIN,
            base_training = BASE_TRAINING,
            pressure      = pressure,
            primary_skill = primary_skill,
        )

        strain_score = clamp(0.6 * BASE_STRAIN + 0.4 * kpis["burnout_index"])
        strain_tier  = assign_strain_tier(strain_score)

        strengths  = [primary_skill, secondary_skill, "generalist"]
        weaknesses = []
        if kpis["burnout_index"]    >= 0.75: weaknesses.append("burnout_risk")
        if kpis["escalation_rate"]  >= 0.25: weaknesses.append("escalation_prone")
        if kpis["compliance_risk"]  >= 0.55: weaknesses.append("compliance_risk")
        if kpis["gaming_propensity"] >= 0.50: weaknesses.append("gaming_prone")

        # Tenure — skewed toward mid-range; new hires and veterans both present
        # Shape: right-skewed distribution centered ~24 months, bounded 1–180
        raw_tenure = int(clamp(
            24 + (z_noise(rng, 0.9) * 8) + (BASE_TRAINING * 1.2),
            1, 180
        ))
        # Seed some new hires (~15%) and long-tenure reps (~10%)
        tenure_roll = rng.random()
        if tenure_roll < 0.15:
            months_on_job = int(rng.uniform(1, 6))    # new hire
        elif tenure_roll > 0.90:
            months_on_job = int(rng.uniform(36, 180)) # veteran
        else:
            months_on_job = raw_tenure

        tenure_band = assign_tenure_band(months_on_job)

        # Recompute misinformation_risk now that we have actual months_on_job
        misinformation_risk = synthesize_misinformation_risk(
            rng           = rng,
            months_on_job = months_on_job,
            qa_score      = kpis["qa_score"],
            burnout_index = kpis["burnout_index"],
        )
        kpis["misinformation_risk"] = misinformation_risk

        # Append misinformation_risk to weaknesses if elevated
        if misinformation_risk >= 0.25:
            weaknesses.append("misinformation_risk")
        if not weaknesses:
            weaknesses.append("none_flagged")

        reps.append({
            "rep_id":                   rep_id,
            "first_name":               first_name,
            "last_name":                last_name,
            "rep_name":                 rep_name,
            "site":                     args.site,
            "queue_name":               args.queue_name,
            "department":               department,
            "job_role":                 job_role,
            "can_transfer_departments": False,
            "tenure_months":            months_on_job,
            "months_on_job":            months_on_job,
            "tenure_band":              tenure_band,
            "primary_skill_tag":        primary_skill,
            "secondary_skill_tag":      secondary_skill,
            "primary_skill_label":      SKILL_LABELS.get(primary_skill,   primary_skill),
            "secondary_skill_label":    SKILL_LABELS.get(secondary_skill, secondary_skill),
            "strengths":                "|".join(strengths),
            "weaknesses":               "|".join(weaknesses),
            "strain_tier":              strain_tier,
            "pressure_index_baseline":  round(pressure, 4),
            "experiment_condition":     "goodhart_baseline",
            **kpis,
        })

    df = pd.DataFrame(reps)

    # Integrity checks
    if df["rep_id"].duplicated().any():
        raise RuntimeError("Duplicate rep_id detected.")
    if df[["first_name", "last_name"]].duplicated().any():
        raise RuntimeError("Duplicate first+last detected.")

    run_id    = stable_run_id(args.seed, used_files)
    base_name = (
        f"employees__goodhart_baseline__{args.site.lower()}"
        f"__n{args.n}__seed{args.seed}__{run_id}"
    )

    out_csv  = non_overwriting_path(out_dir, base_name, "csv")
    out_json = non_overwriting_path(out_dir, base_name + "__metadata", "json")

    df.to_csv(out_csv, index=False)

    # Fixed-name output — required by generate_calls.py and employee_gen_run_all.py
    fixed_csv = out_dir / "novawireless_employee_database.csv"
    df.to_csv(fixed_csv, index=False)
    # Also write to data/ so call generator can find it there too
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(data_dir / "novawireless_employee_database.csv", index=False)

    meta = {
        "generated_at":    datetime.now().isoformat(timespec="seconds"),
        "experiment":      "NovaWireless-GoodhartLab",
        "condition":       "goodhart_baseline",
        "n":               args.n,
        "seed":            args.seed,
        "site":            args.site,
        "queue_name":      args.queue_name,
        "used_files":      [p.name for p in used_files],
        "goodhart_params": {
            "base_strain":       BASE_STRAIN,
            "base_training":     BASE_TRAINING,
            "compliance_risk":   "synthesized",
            "gaming_propensity": "derived from compliance_risk",
        },
        "vs_governance": {
            "base_strain":   {"goodhart": BASE_STRAIN, "governance": 0.35},
            "base_training": {"goodhart": BASE_TRAINING, "governance": 9.0},
            "gaming":        {"goodhart": "synthesized + compounds per call", "governance": "hardcoded 0.0"},
        },
        "rules": {
            "single_queue":          True,
            "single_department":     department,
            "single_role":           job_role,
            "no_transfers":          True,
            "skills_as_strengths":   True,
            "network_service_means": "tech_support",
            "gaming_active":         True,
        },
    }

    out_json.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Summary report
    print(f"\n{'='*60}")
    print(f"NovaWireless-GoodhartLab — Rep Generator")
    print(f"{'='*60}")
    print(f"  Reps generated:      {len(df):,}")
    print(f"  base_strain:         {BASE_STRAIN}  (governance: 0.35)")
    print(f"  base_training:       {BASE_TRAINING}  (governance: 9.0)")
    print(f"\n  KPI summary (mean):")
    print(f"    burnout_index:       {df['burnout_index'].mean():.4f}")
    print(f"    qa_score:            {df['qa_score'].mean():.4f}")
    print(f"    fcr_30d:             {df['fcr_30d'].mean():.4f}")
    print(f"    repeat_contact_rate: {df['repeat_contact_rate'].mean():.4f}")
    print(f"    escalation_rate:     {df['escalation_rate'].mean():.4f}")
    print(f"\n  Gaming signals (mean):")
    print(f"    compliance_risk:     {df['compliance_risk'].mean():.4f}")
    print(f"    gaming_propensity:   {df['gaming_propensity'].mean():.4f}")
    print(f"    misinformation_risk: {df['misinformation_risk'].mean():.4f}")
    print(f"\n  Tenure distribution:")
    for band, cnt in df["tenure_band"].value_counts().items():
        print(f"    {band:<10} {cnt:>4}  ({cnt/len(df)*100:.1f}%)")
    print(f"    mean months_on_job:  {df['months_on_job'].mean():.1f}")
    print(f"\n  Misinformation risk by tenure band:")
    for band in ["new", "mid", "senior"]:
        subset = df[df["tenure_band"] == band]["misinformation_risk"]
        if len(subset):
            print(f"    {band:<10}  mean={subset.mean():.4f}  max={subset.max():.4f}")
    print(f"\n  Strain tier distribution:")
    for tier, cnt in df["strain_tier"].value_counts().items():
        print(f"    {tier:<12} {cnt:>4}  ({cnt/len(df)*100:.1f}%)")
    print(f"\n  Gaming risk distribution:")
    high_gaming = (df["gaming_propensity"] >= 0.50).sum()
    print(f"    gaming_propensity >= 0.50:  {high_gaming} reps  ({high_gaming/len(df)*100:.1f}%)")
    print(f"\n  Output:   {out_csv.relative_to(repo_root)}")
    print(f"  Fixed:    output/novawireless_employee_database.csv  ← used by generate_calls.py")
    print(f"  Data:     data/novawireless_employee_database.csv    ← used by generate_calls.py")
    print(f"  Metadata: {out_json.relative_to(repo_root)}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

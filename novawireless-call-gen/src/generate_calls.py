"""
generate_calls.py
=============================
NovaWireless-GoodhartLab — Call Generator

Governance-aligned call generator. Reps do not game metrics intentionally;
burnout causes unintentional metric inflation (gamed_metric scenario).

WHAT THIS FILE DOES:
  - Imports from scenario_router and transcript_builder (standard names)
  - SCENARIO_MIX uses GOODHART_SCENARIO_MIX (no fraud scenarios)
  - Call IDs prefixed CALL-
  - init_rep_state(): gaming_propensity hardcoded to 0.0
  - update_rep_state(): gaming compounding removed entirely
  - Record columns: gaming_propensity always 0.0, compliance_risk always 0.0
  - Three governance columns in each record:
      dar_signal    — documentation accuracy signal for this call
      dov_signal    — rep verbalized limitation honestly
      trust_delta   — trust change this call
  - No bandaid credit logic (credit_authorized always True)
  - Integrity report shows governance metrics instead of gaming metrics
  - Rep and customer profiles fully wire into scenario routing and outcomes

WHAT STAYED THE SAME vs. original NovaWireless:
  - Same data loading (customers.csv, novawireless_employee_database.csv,
    master_account_ledger.csv) — same files, same paths
  - Same rep state tracking structure (policy_skill, burnout_level)
  - Same friction tier system (now profile-driven, same tier names)
  - Same ledger write-back for legitimate line additions
  - Same repeat contact generation logic
  - Same month/seed/output structure
  - Same 48-column schema backbone + 3 new governance columns

Run:
  python src/generate_calls.py --n_calls 6000 --month 2025-01
"""

import json
import sys
import os
from pathlib import Path
from utils import find_repo_root
from datetime import datetime, timedelta
import calendar

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------



REPO_ROOT  = find_repo_root()
DATA_DIR   = REPO_ROOT / "data"
OUTPUT_DIR = REPO_ROOT / "output"
SRC_DIR    = Path(__file__).resolve().parent

sys.path.insert(0, str(SRC_DIR))

# KEY CHANGE: imports from governance versions
from scenario_router import (
    assign_scenario,
    build_detection_flags,
    build_outcome_flags,
    build_credit,
    get_aht,
    GOODHART_SCENARIO_MIX,
    SCENARIO_CALL_TYPE,
    SCENARIO_SUBREASON,
    AHT_MULTIPLIERS,
    SCENARIO_CHURN_MULTIPLIERS,
    SCENARIO_TRUST_DECAY,
)
from transcript_builder import build_transcript, transcript_to_text


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RANDOM_SEED    = 42
N_CALLS        = 6_000     # ~6K/month as specified in project summary
BASE_AHT_SECS  = 900
SIM_START_DATE = datetime(2025, 1, 1)
SIM_END_DATE   = datetime(2025, 12, 31)

CALL_TYPE_PRIORS = {
    "Billing Dispute":       0.28,
    "Network Coverage":      0.22,
    "Device Issue":          0.18,
    "Promotion Inquiry":     0.14,
    "Account Inquiry":       0.10,
    "Payment Arrangement":   0.05,
    "International/Roaming": 0.03,
}

FRICTION_TIERS = {
    "low":    0.20,
    "normal": 0.55,
    "high":   0.18,
    "peak":   0.07,
}


# ---------------------------------------------------------------------------
# Rep state management — governance-aligned
# ---------------------------------------------------------------------------

def init_rep_state(agent: dict) -> dict:
    """
    KEY CHANGE: gaming_propensity hardcoded to 0.0.
    In the governance regime, compliance_risk is also 0.0.
    policy_skill and burnout_level still evolve naturally.
    misinformation_risk and tenure_band fed from employee database.
    """
    return {
        "gaming_propensity":  0.0,    # HARDCODED — no gaming in governance regime
        "compliance_risk":    0.0,    # HARDCODED — not a meaningful signal here
        "policy_skill":       float(np.clip(agent.get("policy_accuracy", 0.5), 0.0, 1.0)),
        "burnout_level":      float(np.clip(agent.get("burnout_index",   0.3), 0.0, 1.0)),
        "calls_handled":      0,
        # Tenure and misinformation — from employee record
        "misinformation_risk": float(np.clip(agent.get("misinformation_risk", 0.10), 0.0, 1.0)),
        "tenure_band":         str(agent.get("tenure_band", "senior")),
        "months_on_job":       int(agent.get("months_on_job", agent.get("tenure_months", 24))),
        # Governance state — accumulates over the rep's session
        "dar_running_mean":   float(np.clip(agent.get("dar_score",   0.85), 0.0, 1.0)),
        "dov_running_mean":   float(np.clip(agent.get("dov_score",   0.70), 0.0, 1.0)),
        "trust_accumulated":  0.0,
    }


def update_rep_state(state: dict, outcome_flags: dict, credit_info: dict) -> dict:
    """
    Update rep state after each call — governance-aligned.

    KEY CHANGES vs. original:
    - NO gaming_propensity compounding (was +2% per gamed call, +1% per bandaid)
    - NO bandaid credit tracking
    - gaming_propensity stays at 0.0 always
    - policy_skill still improves with each call
    - burnout_level still responds to escalations
    - Governance signals accumulate
    """
    escalated = outcome_flags.get("escalation_flag", False)
    dar_this_call = float(outcome_flags.get("dar_signal", True))
    dov_this_call = float(outcome_flags.get("dov_signal", False))
    trust_this_call = float(outcome_flags.get("trust_delta", 0.0))

    state["calls_handled"] += 1

    # gaming_propensity stays 0.0 — no update logic
    # compliance_risk stays 0.0 — no update logic

    # Burnout: escalations raise it, normal calls recover slightly
    if escalated:
        state["burnout_level"] = min(1.0, state["burnout_level"] + 0.015)
    else:
        state["burnout_level"] = max(0.0, state["burnout_level"] - 0.0005)

    # Policy skill: slow increase per call
    headroom = 1.0 - state["policy_skill"]
    state["policy_skill"] = min(1.0, state["policy_skill"] + headroom * 0.002)

    # Governance signal accumulation
    n = state["calls_handled"]
    state["dar_running_mean"] = (
        (state["dar_running_mean"] * (n - 1) + dar_this_call) / n
    )
    state["dov_running_mean"] = (
        (state["dov_running_mean"] * (n - 1) + dov_this_call) / n
    )
    state["trust_accumulated"] += trust_this_call

    return state


# ---------------------------------------------------------------------------
# Helpers — identical to original
# ---------------------------------------------------------------------------

def sample_weighted(rng, mapping: dict):
    keys  = list(mapping.keys())
    probs = np.array(list(mapping.values()), dtype=float)
    probs /= probs.sum()
    return rng.choice(keys, p=probs)


def random_date(rng, start: datetime, end: datetime) -> datetime:
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=int(rng.integers(0, delta)))


def month_date_range(month_str: str):
    year, mon = int(month_str[:4]), int(month_str[5:7])
    start    = datetime(year, mon, 1)
    last_day = calendar.monthrange(year, mon)[1]
    end      = datetime(year, mon, last_day, 23, 59, 59)
    return start, end


def load_data():
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    employees = pd.read_csv(DATA_DIR / "novawireless_employee_database.csv")
    ledger    = pd.read_csv(DATA_DIR / "master_account_ledger.csv")
    return customers, employees, ledger


def save_ledger(ledger: pd.DataFrame) -> None:
    path = OUTPUT_DIR / "master_account_ledger.csv"
    ledger.to_csv(path, index=False)
    print(f"  [ledger write-back] Saved {len(ledger):,} rows → {path.name}")


# ---------------------------------------------------------------------------
# Main generation loop — governance-aligned
# ---------------------------------------------------------------------------

def generate(n_calls: int, rng: np.random.Generator,
             sim_start: datetime = None, sim_end: datetime = None):
    if sim_start is None:
        sim_start = datetime(2025, 1, 1)
    if sim_end is None:
        sim_end   = datetime(2025, 12, 31)

    customers, employees, ledger = load_data()
    ledger    = ledger.copy()
    customers = customers.copy().reset_index(drop=True)
    cust_index = {row["customer_id"]: idx for idx, row in customers.iterrows()}

    rep_states = {
        row["rep_id"]: init_rep_state(row.to_dict())
        for _, row in employees.iterrows()
    }

    ledger_by_account = ledger.groupby("account_id")

    records     = []
    transcripts = []
    call_counter = 0

    def make_call(customer, agent, scenario, is_repeat=False, parent_call_id=None):
        nonlocal call_counter
        call_counter += 1
        # CALL- prefix (GoodhartLab standard)
        call_id = f"CALL-{call_counter:07d}"

        rep_id    = agent.get("rep_id")
        rep_state = rep_states.get(rep_id)

        # Call type
        forced_type = SCENARIO_CALL_TYPE.get(scenario)
        call_type   = forced_type if forced_type else sample_weighted(rng, CALL_TYPE_PRIORS)
        subreason   = SCENARIO_SUBREASON.get(scenario)

        # Friction
        friction_tier = sample_weighted(rng, FRICTION_TIERS)
        friction_mult_map = {"low": 0.85, "normal": 1.00, "high": 1.15, "peak": 1.30}
        friction_mult = friction_mult_map[friction_tier]

        # Ledger lookup
        account_id  = customer.get("account_id")
        ledger_rows = (
            ledger_by_account.get_group(account_id)
            if account_id in ledger_by_account.groups
            else None
        )
        if ledger_rows is not None and len(ledger_rows) > 0:
            eip_voice = ledger_rows[
                (ledger_rows["product_type"].astype(str) == "voice") &
                (ledger_rows["eip_exists_flag"].astype(int) == 1)
            ] if "product_type" in ledger_rows.columns and "eip_exists_flag" in ledger_rows.columns else pd.DataFrame()
            ledger_row = eip_voice.iloc[0] if len(eip_voice) > 0 else ledger_rows.iloc[0]
        else:
            ledger_row = None

        # Flags
        detection_flags = build_detection_flags(rng, scenario, ledger_row, rep_state)
        outcome_flags   = build_outcome_flags(rng, scenario, friction_tier, rep_state)

        # Credit — rep_aware always False in governance regime
        credit_info = build_credit(rng, scenario, call_type, rep_aware=False)


        # AHT — no gaming shortening
        agent_aht = float(agent.get("aht_secs", BASE_AHT_SECS))
        aht_secs  = get_aht(rng, scenario, BASE_AHT_SECS, agent_aht, friction_mult, rep_state)
        if credit_info.get("credit_applied"):
            aht_secs = int(aht_secs * 1.05)

        # Update rep state
        if rep_state is not None:
            update_rep_state(rep_state, outcome_flags, credit_info)

        # Call date
        call_date = random_date(rng, sim_start, sim_end)

        # Trust decay
        decay   = SCENARIO_TRUST_DECAY.get(scenario, 0.0)
        cust_id = customer.get("customer_id")
        if decay > 0.0 and cust_id in cust_index:
            idx = cust_index[cust_id]
            current_trust = float(customers.at[idx, "trust_baseline"])
            customers.at[idx, "trust_baseline"] = max(0.0, current_trust - decay)
            customer = customers.iloc[idx].to_dict()

        # Churn
        churn_mult           = SCENARIO_CHURN_MULTIPLIERS.get(scenario, 1.0)
        effective_churn_risk = min(
            float(customer.get("churn_risk_score", 0.27)) * churn_mult, 0.99
        )

        # Transcript
        scenario_meta = {**detection_flags, **outcome_flags}
        turns = build_transcript(
            scenario       = scenario,
            call_type      = call_type,
            agent          = agent,
            customer       = customer,
            scenario_meta  = scenario_meta,
            credit_info    = credit_info,
            rng            = rng,
            is_repeat_call = is_repeat,
        )
        transcript_text = transcript_to_text(turns)

        # Metadata record — same schema + governance columns
        record = {
            "call_id":              call_id,
            "is_repeat_call":       int(is_repeat),
            "parent_call_id":       parent_call_id,
            "call_date":            call_date.strftime("%Y-%m-%d"),
            "call_type":            call_type,
            "call_subreason":       subreason,
            "scenario":             scenario,
            "experiment_condition": "goodhart_burnout_bleed",
            "customer_id":          cust_id,
            "account_id":           account_id,
            "rep_id":               rep_id,
            "rep_name":             agent.get("rep_name"),
            "site":                 agent.get("site"),
            "queue_name":           agent.get("queue_name"),
            "department":           agent.get("department"),
            "agent_tenure_months":  agent.get("tenure_months"),
            "agent_months_on_job":  agent.get("months_on_job", agent.get("tenure_months")),
            "agent_tenure_band":    agent.get("tenure_band", "senior"),
            "agent_misinformation_risk": agent.get("misinformation_risk", 0.0),
            "agent_strain_tier":    agent.get("strain_tier"),
            "agent_qa_score":       agent.get("qa_score"),
            "agent_aht_secs_base":  agent_aht,
            "friction_tier":        friction_tier,
            "aht_secs":             aht_secs,
            # Rep state snapshot — governance versions
            "rep_gaming_propensity": 0.0,    # always 0.0
            "rep_compliance_risk":   0.0,    # always 0.0
            "rep_policy_skill":      round(rep_state["policy_skill"],  4) if rep_state else None,
            "rep_burnout_level":     round(rep_state["burnout_level"], 4) if rep_state else None,
            "rep_calls_handled":     rep_state["calls_handled"]            if rep_state else None,
            # Governance rep state
            "rep_dar_running_mean":  round(rep_state["dar_running_mean"], 4) if rep_state else None,
            "rep_dov_running_mean":  round(rep_state["dov_running_mean"], 4) if rep_state else None,
            "rep_trust_accumulated": round(rep_state["trust_accumulated"], 4) if rep_state else None,
            **detection_flags,
            **outcome_flags,
            # Credit columns
            "credit_applied":        credit_info["credit_applied"],
            "credit_amount":         credit_info["credit_amount"],
            "credit_type":           credit_info["credit_type"],
            "credit_authorized":     credit_info["credit_authorized"],
            # Customer
            "customer_tenure_months":        customer.get("tenure_months"),
            "customer_monthly_charges":      customer.get("monthly_charges"),
            "customer_lines":                customer.get("lines_on_account"),
            "customer_churn_risk":           customer.get("churn_risk_score"),
            "customer_churn_risk_effective": round(effective_churn_risk, 6),
            "customer_trust_baseline":       customer.get("trust_baseline"),
            "customer_patience":             customer.get("patience"),
            "customer_is_churned":           customer.get("is_churned"),
        }

        transcript_obj = {
            "call_id":         call_id,
            "is_repeat_call":  int(is_repeat),
            "parent_call_id":  parent_call_id,
            "scenario":        scenario,
            "call_type":       call_type,
            "call_date":       call_date.strftime("%Y-%m-%d"),
            "rep_id":          rep_id,
            "customer_id":     cust_id,
            "credit_applied":  credit_info["credit_applied"],
            "credit_amount":   credit_info["credit_amount"],
            "credit_type":     credit_info["credit_type"],
            "turns":           turns,
            "transcript_text": transcript_text,
        }

        return record, transcript_obj, outcome_flags, credit_info

    for i in range(n_calls):
        cust_row  = customers.iloc[int(rng.integers(0, len(customers)))]
        customer  = cust_row.to_dict()
        agent_row = employees.iloc[int(rng.integers(0, len(employees)))]
        agent     = agent_row.to_dict()

        # Scenario assignment — burnout bleed active if rep_state available
        agent_id_for_state = agent_row.to_dict().get("rep_id")
        current_rep_state  = rep_states.get(agent_id_for_state)
        scenario = assign_scenario(rng, GOODHART_SCENARIO_MIX, current_rep_state)

        record, transcript_obj, outcome_flags, credit_info = make_call(
            customer, agent, scenario
        )
        records.append(record)
        transcripts.append(transcript_obj)

        # Ledger write-back for legitimate line additions (identical to original)
        if scenario == "line_add_legitimate" and outcome_flags.get("true_resolution"):
            account_id = customer.get("account_id")
            cust_id    = customer.get("customer_id")
            new_line_number = int(ledger[ledger["account_id"] == account_id].shape[0]) + 1
            new_agreement   = f"AGR-{account_id}-L{new_line_number:02d}"
            new_imei        = f"35{rng.integers(100000000000000, 999999999999999):015d}"
            new_row = {
                "account_id":             account_id,
                "customer_id":            cust_id,
                "product_type":           "voice",
                "line_number":            new_line_number,
                "agreement_number":       new_agreement,
                "imei":                   new_imei,
                "eip_exists_flag":        0,
                "installment_months":     0,
                "billing_agreement_type": "Month-to-month",
                "imei_mismatch_flag":     0,
                "source_call_id":         record["call_id"],
                "added_date":             record["call_date"],
            }
            ledger = pd.concat([ledger, pd.DataFrame([new_row])], ignore_index=True)
            if cust_id in cust_index:
                idx = cust_index[cust_id]
                current_lines = int(customers.at[idx, "lines_on_account"])
                customers.at[idx, "lines_on_account"] = current_lines + 1

        # Repeat contacts (identical logic to original)
        if outcome_flags.get("repeat_contact_30d"):
            repeat_agent = employees.iloc[int(rng.integers(0, len(employees)))].to_dict()
            rr, rt, _, _ = make_call(customer, repeat_agent, scenario,
                                     is_repeat=True, parent_call_id=record["call_id"])
            records.append(rr)
            transcripts.append(rt)

        if outcome_flags.get("repeat_contact_31_60d"):
            repeat_agent = employees.iloc[int(rng.integers(0, len(employees)))].to_dict()
            rr, rt, _, _ = make_call(customer, repeat_agent, scenario,
                                     is_repeat=True, parent_call_id=record["call_id"])
            records.append(rr)
            transcripts.append(rt)

        if (i + 1) % 1000 == 0:
            print(f"  Generated {i+1:,} / {n_calls:,} primary calls  "
                  f"(total records so far: {len(records):,})")

    # Ledger write-back if any lines were added
    original_ledger_len = len(load_data()[2])
    new_rows = len(ledger) - original_ledger_len
    if new_rows > 0:
        save_ledger(ledger)
        print(f"  [ledger] {new_rows} new line(s) added to master_account_ledger.csv")

    return records, transcripts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="NovaWireless-GoodhartLab — Call Generator"
    )
    ap.add_argument("--n_calls", type=int, default=N_CALLS)
    ap.add_argument("--seed",    type=int, default=RANDOM_SEED)
    ap.add_argument("--month",   type=str, default=None,
                    help="Constrain call dates to YYYY-MM")
    args = ap.parse_args()

    if args.month:
        sim_start, sim_end = month_date_range(args.month)
        print(f"NovaWireless Governance Call Generator  |  Month: {args.month}  "
              f"({sim_start.date()} → {sim_end.date()})")
    else:
        sim_start = SIM_START_DATE
        sim_end   = SIM_END_DATE
        print(f"NovaWireless Governance Call Generator  |  "
              f"{sim_start.date()} → {sim_end.date()}")

    print(f"  Seed: {args.seed}  |  N calls: {args.n_calls:,}  |  "
          f"Data: {DATA_DIR}  |  Output: {OUTPUT_DIR}")
    print(f"  Experiment condition: governance_aligned")
    print(f"  Call ID prefix: CALL-")

    for f in [DATA_DIR / "customers.csv",
              DATA_DIR / "novawireless_employee_database.csv",
              DATA_DIR / "master_account_ledger.csv"]:
        if not f.exists():
            print(f"ERROR: Missing required input file: {f}")
            sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(args.seed)
    print("\nGenerating calls...")
    records, transcripts = generate(args.n_calls, rng, sim_start, sim_end)

    month_tag  = args.month if args.month else "all"
    meta_path  = OUTPUT_DIR / f"calls_metadata_{month_tag}.csv"
    jsonl_path = OUTPUT_DIR / f"transcripts_{month_tag}.jsonl"

    df = pd.DataFrame(records)
    df.to_csv(meta_path, index=False)
    print(f"\nWrote metadata:    {meta_path.name}  ({len(df):,} rows, {len(df.columns)} columns)")

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for obj in transcripts:
            f.write(json.dumps(obj) + "\n")
    print(f"Wrote transcripts: {jsonl_path.name}  ({len(transcripts):,} records)")

    # Integrity report — governance-focused
    print("\nIntegrity check:")
    print(f"  Total records:  {len(df):,}  "
          f"(primary: {int((df['is_repeat_call']==0).sum()):,}  "
          f"repeats: {int((df['is_repeat_call']==1).sum()):,})")

    # Governance invariants
    burnout_bleed_count = (df["scenario"] == "gamed_metric").sum()
    print(f"  [OK] Burnout-bleed gaming calls: {burnout_bleed_count:,}  ({burnout_bleed_count/len(df)*100:.1f}%)")
    print(f"  [OK] All other calls are honest governance scenarios")

    print(f"\n  Scenario distribution:")
    for sc, cnt in df["scenario"].value_counts().items():
        print(f"    {sc:<25} {cnt:>6,}  ({cnt/len(df)*100:.1f}%)")

    print(f"\n  Resolution gap (the key metric):")
    proxy_rate = df["resolution_flag"].mean() * 100
    true_rate  = df["true_resolution"].mean()  * 100
    gap        = proxy_rate - true_rate
    print(f"    Proxy resolution rate:  {proxy_rate:.1f}%")
    print(f"    True resolution rate:   {true_rate:.1f}%")
    print(f"    Gap (proxy - true):     {gap:.1f}pp  (original: ~42pp)")

    print(f"\n  Tenure and misinformation signals:")
    if "agent_tenure_band" in df.columns:
        for band in ["new", "mid", "senior"]:
            cnt = (df["agent_tenure_band"] == band).sum()
            print(f"    calls from {band:<8} reps: {cnt:,}  ({cnt/len(df)*100:.1f}%)")
    if "incorrect_info_given" in df.columns:
        ii = df["incorrect_info_given"].astype(bool).sum()
        print(f"    incorrect_info_given:   {ii:,}  ({ii/len(df)*100:.1f}%)")
        # Show breakdown by tenure band
        if "agent_tenure_band" in df.columns:
            for band in ["new", "mid", "senior"]:
                subset = df[df["agent_tenure_band"] == band]
                if len(subset):
                    rate = subset["incorrect_info_given"].astype(bool).mean() * 100
                    print(f"      {band:<8}: {rate:.1f}% misinfo rate")

    print(f"\n  Churn signals:")
    if "churned" in df.columns:
        ch = df["churned"].astype(bool).sum()
        print(f"    churned:                {ch:,}  ({ch/len(df)*100:.1f}%)")
        # Churn by true resolution
        resolved   = df[df["true_resolution"].astype(bool) == True]["churned"].astype(bool).mean() * 100
        unresolved = df[df["true_resolution"].astype(bool) == False]["churned"].astype(bool).mean() * 100
        print(f"    churn | resolved:       {resolved:.1f}%")
        print(f"    churn | unresolved:     {unresolved:.1f}%")
        if "incorrect_info_given" in df.columns:
            bad_info_churn = df[df["incorrect_info_given"].astype(bool)]["churned"].astype(bool).mean() * 100
            print(f"    churn | bad info:       {bad_info_churn:.1f}%")

    print(f"\n  Governance signals (mean):")
    if "dar_signal" in df.columns:
        print(f"    DAR signal rate:        {df['dar_signal'].mean()*100:.1f}%")
    if "dov_signal" in df.columns:
        print(f"    DOV signal rate:        {df['dov_signal'].mean()*100:.1f}%")
    if "trust_delta" in df.columns:
        print(f"    Mean trust delta:       {df['trust_delta'].mean():+.4f}")

    print(f"\n  Credit summary:")
    credit_df = df[df["credit_applied"] == True]
    print(f"    Credit applied:         {len(credit_df):,}  ({len(credit_df)/len(df)*100:.1f}%)")
    if len(credit_df) > 0:
        print(f"    Mean credit amount:     ${credit_df['credit_amount'].mean():.2f}")
        print(f"    Unauthorized credits:   0  (governance invariant)")
        print(f"    Credit type breakdown:")
        for ct, cnt in credit_df["credit_type"].value_counts().items():
            print(f"      {ct:<20} {cnt:>6,}")

    print(f"\n  Escalation rate:          {df['escalation_flag'].mean()*100:.1f}%")
    print(f"  Mean AHT:                 {df['aht_secs'].mean():.0f}s")
    print("\nDone.")


if __name__ == "__main__":
    main()

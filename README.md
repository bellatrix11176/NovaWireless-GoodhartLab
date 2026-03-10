# NovaWireless-GoodhartLab

**Synthetic data generation pipeline for Goodhart's Law research in wireless retail operations.**  
Companion code to Aulabaugh (2026), *"The Hidden Cost of Measurement: Why Call Centers Must Move Beyond Proxy Metrics."*

---

## What This Is

NovaWireless-GoodhartLab is a multi-sub-project synthetic data pipeline that simulates a wireless carrier call center and retail store environment to demonstrate how optimizing for measurable proxy metrics distorts outcomes — and to generate realistic data for governance framework design.

The pipeline is modeled on T-Mobile-style operations and produces 12 months of call center interactions and retail store visits across a shared customer population, with full rep persona traits, Goodhart degradation scenarios, and audit-ready sanitized outputs.

---

## The Problem It Models

> "When a measure becomes a target, it ceases to be a good measure." — Goodhart's Law

In a call center measured on First Contact Resolution (FCR):
- Reps learn to mark calls resolved that are not resolved
- Proxy FCR inflates while true resolution degrades
- The gap between what the system reports and what customers experience widens over time
- Under governance metrics (DAR, DOV, trust delta), this gaming drops to zero — even under maximum pressure

This pipeline generates the synthetic data to prove that experimentally.

---

## Project Structure

```
NovaWireless-GoodhartLab\
├── .labroot                          ← repo root marker
├── run_all.py                        ← full pipeline orchestrator
├── README.md
├── requirements.txt
├── LICENSE
│
├── data\                             ← shared inputs (generated)
│   ├── customers.csv                 ← 2,000 customer profiles
│   ├── novawireless_employee_database.csv
│   ├── master_account_ledger.csv
│   └── novawireless_store_rep_database.csv
│
├── output\
│   ├── call-gen\
│   │   ├── metadata\                 ← raw call records
│   │   ├── transcripts\             ← JSONL call transcripts
│   │   └── sanitized\               ← analysis-ready call files  USE THESE
│   ├── store-gen\
│   │   ├── store_visits_YYYY-MM.csv ← raw store visits
│   │   └── sanitized\               ← analysis-ready store files  USE THESE
│   ├── rep-gen\                      ← rep persona outputs
│   ├── ledger\                       ← account ledger outputs
│   └── experiments\                  ← Goodhart pressure experiment outputs
│
├── novawireless-customer-gen\        ← Step 1
├── novawireless-rep-gen\             ← Step 2
├── novawireless-store-gen\           ← Step 3
└── novawireless-call-gen\            ← Step 4
```

---

## Pipeline Steps

| Step | Sub-project | Output |
|---|---|---|
| 1 | novawireless-customer-gen | 2,000 customer profiles + account ledger |
| 2 | novawireless-rep-gen | 250 call center rep personas |
| 3 | novawireless-store-gen | 12 store locations, ~120 retail reps, 12 months of visits |
| 4 | novawireless-call-gen | 12 months of call center interactions + sanitization |

---

## Quick Start

```bash
pip install -r requirements.txt

# Full pipeline — 12 months, all sub-projects
python run_all.py

# Skip store generation (call center only)
python run_all.py --skip_store

# Skip call generation (store only)
python run_all.py --skip_calls

# Single month
python run_all.py --months 1
```

---

## Key Design Decisions

**Separate workforces.** Call center reps and store reps are entirely separate populations with different trait profiles. They share the same customer pool, connected via customer_id.

**Store memo system.** Every store visit generates a structured memo documenting reason for visit, rep advice, customer decision, account changes, and a disclosure reference. Missing memos are the strongest audit signal — an account change with no documentation of what the customer was told.

**Cross-channel linkage.** A customer who visits a store and then calls the call center within 30 days can be traced via customer_id. This linkage does not exist in current T-Mobile systems. It is a novel audit capability.

**Goodhart degradation — not fraud.** Gaming behavior in this model is driven by burnout and metric pressure, not intentional fraud. Reps under high strain begin marking unresolved calls as resolved because the system rewards the proxy, not the outcome.

**Governance metrics eliminate gaming.** When reps are measured on DAR (documentation accuracy), DOV (honest disclosure), and trust delta instead of FCR, gaming drops to zero — even under maximum pressure. Pressure causes burnout and strain but not manipulation.

---

## Audit Scenarios

### Call center (6 scenarios)

| Scenario | Description |
|---|---|
| clean | Genuine resolution attempt |
| unresolvable_clean | Honest handling of structurally unresolvable call |
| activation_clean | Successful device activation |
| activation_failed | Failed activation with honest disclosure |
| line_add_legitimate | Legitimate line addition |
| gamed_metric | Burnout-driven metric inflation — not intentional fraud |

### Store visits (3 scenarios)

| Scenario | Description |
|---|---|
| Clean | Memo filed, disclosure ref matches account change |
| Disclosure mismatch | Memo exists but ref does not cover what was sold |
| Missing memo | Account change made, no memo filed — strongest audit signal |

---

## Rep Traits

**Call center reps:** qa_score, fcr_30d, burnout_index, compliance_risk, gaming_propensity, months_on_job, tenure_band (new/mid/senior), misinformation_risk, strain_tier. New reps have elevated misinformation_risk — they do not know policy well enough yet. This degrades true_resolution and elevates 31-60d repeat contacts independent of scenario.

**Store reps:** product_knowledge, disclosure_diligence, ownership_bias, upsell_pressure, memo_thoroughness, burnout_index, compliance_risk, gaming_propensity.

---

## The Key Finding

Under governance metrics, the resolution gap collapses. Proxy FCR and true FCR converge because there is nothing inflating the proxy. The 42-point gap that exists under FCR-only measurement disappears.

The measure was the problem. Replace the measure, fix the behavior.

---

## Downstream Projects

| Project | Consumes | Purpose |
|---|---|---|
| NovaWireless-AnalysisLab | sanitized outputs | EDA and governance metric calibration |
| novawireless-governance-pipeline | calls_sanitized_*.csv | DAR, DRL, DOV, POR, TER, SII signal computation |
| NovaWireless_KPI_Drift_Observatory | governance_report.json | System-level veto signal dashboard |

---

## Citation

Aulabaugh, G. (2026). *The hidden cost of measurement: Why call centers must move beyond proxy metrics.* NovaWireless Research Division.

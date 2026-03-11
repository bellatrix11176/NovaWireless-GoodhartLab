# novawireless-call-gen

**Pipeline Step 4 — Call Center Interaction Generation**

Generates ~6,000 call center interactions per month across 12 months, with full transcript text, rep state tracking, governance signal columns, and sanitized analysis outputs.

---

## What It Produces

| Output | Location | Description |
|---|---|---|
| `calls_metadata_YYYY-MM.csv` | `output/call-gen/metadata/` | Raw call records |
| `transcripts_YYYY-MM.jsonl` | `output/call-gen/transcripts/` | Full call transcripts in JSONL format |
| `calls_sanitized_YYYY-MM.csv` | `output/call-gen/sanitized/` | Analysis-ready calls with rebuilt scores — USE THESE |

---

## Scenario Architecture

| Scenario | Mix | True Resolution | Description |
|---|---|---|---|
| `clean` | 58% | 84% | Genuine resolution attempt |
| `unresolvable_clean` | 17% | 10% | Structurally unresolvable — honest handling |
| `activation_clean` | 10% | 95% | Successful device activation |
| `activation_failed` | 7% | 8% | Failed activation with honest disclosure |
| `line_add_legitimate` | 8% | 93% | Legitimate line addition |
| `gamed_metric` | Burnout-driven | 20% | Burnout bleed — not intentional fraud |

Gaming activates only when rep burnout exceeds 0.75. It is stress-induced corner cutting, not deliberate deception.

---

## Key Output Columns

| Column | Description |
|---|---|
| `resolution_flag` | Proxy metric — what the rep marked |
| `true_resolution` | Ground truth outcome |
| `churned` | Customer churned — tied to true resolution, NOT proxy |
| `incorrect_info_given` | Rep gave wrong information (tenure-driven misinformation risk) |
| `dar_signal` | Documentation accuracy signal |
| `dov_signal` | Rep verbalized limitation honestly |
| `trust_delta` | Customer trust change this call |
| `repeat_contact_30d` | Called back within 30 days |
| `repeat_contact_31_60d` | Called back 31–60 days — DAR signal window |
| `agent_tenure_band` | new / mid / senior |
| `agent_misinformation_risk` | Rep's misinformation risk score |
| `audit_flag` | Any governance signal triggered |
| `audit_flag_reason` | Human-readable explanation |
| `transcript_text` | Full call transcript for NLP |

---

## The Goodhart Gap

Under the baseline condition (FCR measurement):
- Proxy resolution rate: **89.4%**
- True resolution rate: **47.3%**
- Gap: **42.1 percentage points**

Under governance metrics (DAR, DOV, trust delta):
- Gaming call share: **0.000%** even at maximum pressure
- Proxy and true resolution converge

---

## Rep State Tracking

Each rep's state is tracked across calls within a month:
- `burnout_level` — rises with escalations, recovers slowly
- `policy_skill` — improves incrementally with each call
- `gaming_propensity` — 0.0 in governance regime; compounds in baseline
- `misinformation_risk` — static per rep, drawn from tenure and QA at generation

---

## Run

```bash
python src/generate_calls.py --n_calls 6000 --month 2025-01
python src/02_sanitize_calls.py --month 2025-01
```

Or via the sub-project orchestrator:
```bash
python src/call_gen__run_all.py
```

Or via the root orchestrator:
```bash
python run_all.py
```

---

## Source Files

```
src/
├── generate_calls.py              ← core call generation
├── scenario_router.py             ← scenario assignment and outcome probability tables
├── transcript_builder.py          ← call transcript generation
├── 02_sanitize_calls.py           ← sanitization and score rebuilding
├── pressure_experiment.py         ← Goodhart pressure experiment runner
├── call_gen__run_all.py           ← sub-project orchestrator
└── utils.py                       ← shared utilities
```

---

## Notes

- Requires `data/customers.csv`, `data/novawireless_employee_database.csv`, and `data/master_account_ledger.csv` from Steps 1 and 2.
- Sanitized files rebuild all outcome scores with rep-state-aware logic for full causal coherence.
- `transcript_text` column in sanitized files is suitable for NLP and linguistic marker analysis.
- All data is fully synthetic. See `LICENSE.md` at the repo root.

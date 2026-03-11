# novawireless-rep-gen

**Pipeline Step 2 — Call Center Representative Generation**

Generates 250 call center representative personas with synthesized KPI traits, burnout profiles, gaming propensity, tenure bands, and misinformation risk. These personas are the workforce that handles all call center interactions in Step 4.

---

## What It Produces

| Output | Location | Description |
|---|---|---|
| `novawireless_employee_database.csv` | `data/` and `output/rep-gen/` | 250 rep personas — primary input for call generator |
| `rep_persona_profiles__v1.csv` | `output/rep-gen/` | Compiled persona profiles |
| `employees__goodhart_baseline__*.csv` | `output/rep-gen/` | Versioned snapshot with run metadata |
| `employees__goodhart_baseline__*__metadata.json` | `output/rep-gen/` | Generation metadata and parameter record |

---

## Rep Trait Model

Traits are synthesized from four parameters: base workforce strain (0.52), base training duration (6.5 months), individual persona draws from workforce priors, and a pressure index from external data sources.

| Trait | Description |
|---|---|
| `burnout_index` | 0–1 burnout level — drives gaming propensity and compliance risk |
| `qa_score` | Quality assurance score |
| `compliance_risk` | Synthesized from burnout, QA, and escalation rate |
| `gaming_propensity` | Seeded from compliance risk — compounds per call in generator |
| `months_on_job` | Actual tenure with realistic new hire and veteran seeding |
| `tenure_band` | new (0–6 mo) / mid (7–18 mo) / senior (19+ mo) |
| `misinformation_risk` | Inverse-exponential decay by tenure — new reps give wrong info more often |
| `strain_tier` | low / medium / high / very_high |

### Two Distinct Failure Modes

**Experience error** — new reps give incorrect information because they don't know policy well enough yet. Surfaces as elevated 31–60 day repeat contacts and churn independent of scenario type.

**Intentional gaming** — senior reps under burnout pressure mark unresolved calls resolved. Surfaces as proxy FCR inflation with true resolution degradation.

These are separate signals in the data and require different governance interventions.

---

## Run

```bash
python src/employee_gen__run_all.py
python src/employee_gen__run_all.py --n 250 --seed 1337
```

Or via the root orchestrator:
```bash
python run_all.py
```

---

## Source Files

```
src/
├── generate_employees_call_center_one_queue.py  ← core rep generation
├── 04_rep_persona_compiler.py                   ← persona profile compilation
└── employee_gen__run_all.py                     ← sub-project orchestrator
```

---

## Notes

- Requires `data/employee_generation_inputs/` prior files. Falls back to hardcoded defaults if missing.
- Must run before `novawireless-call-gen`.
- The `novawireless_employee_database.csv` fixed-name output is what the call generator loads at runtime.
- All data is fully synthetic. See `LICENSE.md` at the repo root.

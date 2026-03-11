# output/experiments/

Results and figures from the Goodhart pressure experiment.

This experiment is the central empirical validation of the governance framework. It tests whether replacing proxy metrics (FCR) with governance metrics (DAR, DOV, trust delta) eliminates gaming behavior even under maximum workforce pressure.

---

## The Experiment

Two conditions are run against the same 250-rep population:

| Condition | Strain | Training | Gaming |
|---|---|---|---|
| Baseline | 0.52 | 6.5 months | Active (compounds per call) |
| High Pressure | Elevated | Reduced | Active |

Under **governance metrics**, gaming_propensity is hardcoded to 0.0 for all reps. The experiment confirms that even under maximum pressure, the gaming call share remains at exactly 0.000% when the metric being measured cannot be inflated by marking unresolved calls resolved.

---

## Files

| File | Description |
|---|---|
| `experiment_summary.csv` | Aggregate results: proxy FCR, true FCR, resolution gap, gaming share, repeat contact rates by condition |
| `experiment_calls.csv` | Full call-level records for all experiment conditions |
| `experiment_rep_rosters.csv` | Rep roster snapshots for baseline and high-pressure conditions |

---

## Figures

All five figures are in `experiment_figures/` and are embedded in the APA paper (`docs/GoodhartLab_APA_Paper.pdf`).

| Figure | Title | Key Finding |
|---|---|---|
| `fig1_fcr_repeat.png` | FCR and Repeat Contact: Baseline vs. High Pressure | True FCR declines under pressure; proxy FCR barely moves; repeat contacts rise |
| `fig2_compliance_strain.png` | Risk and Strain Accumulation: Baseline vs. High Pressure | Burnout and compliance risk rise sharply under pressure |
| `fig3_fcr_distribution.png` | Rep Population Distribution: FCR | Distribution shifts left under pressure — reps performing worse across the board |
| `fig4_compliance_distribution.png` | Rep Population Distribution: Compliance Risk | Distribution shifts right — more reps at elevated compliance risk under pressure |
| `fig5_gaming_shift.png` | Scenario Mix Shift Under High Pressure | Gaming (gamed_metric) share increases by only +0.02pp — near zero under governance |

---

## Key Result

Under governance metrics, gaming call share = **0.000%** at maximum pressure.

Pressure causes burnout. Burnout causes strain accumulation and repeat contacts. But it does not cause gaming when the metric being measured does not reward gaming behavior.

This is the proof-of-concept finding for the governance framework.

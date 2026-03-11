# output/

Generated outputs from all four NovaWireless-GoodhartLab pipeline sub-projects.

For analysis, always use the **sanitized** files. Raw files are intermediate outputs retained for reproducibility.

---

## Folder Structure

```
output/
├── call-gen/
│   ├── metadata/         ← raw call records (calls_metadata_YYYY-MM.csv)
│   ├── sanitized/        ← USE THESE for analysis (calls_sanitized_YYYY-MM.csv)
│   └── transcripts/      ← JSONL call transcripts (transcripts_YYYY-MM.jsonl)
├── store-gen/
│   ├── store_visits_YYYY-MM.csv   ← raw store visit records
│   └── sanitized/        ← USE THESE for analysis (store_visits_sanitized_YYYY-MM.csv)
├── rep-gen/              ← call center rep persona outputs
├── customer-gen/         ← customer profile outputs
├── ledger/               ← account ledger and anomaly outputs
└── experiments/          ← Goodhart pressure experiment outputs and figures
```

---

## Which Files to Use for Analysis

| Analysis Type | File |
|---|---|
| Call center outcomes, resolution gap, churn, governance signals | `call-gen/sanitized/calls_sanitized_YYYY-MM.csv` |
| Store visit audit flags, memo quality, disclosure compliance | `store-gen/sanitized/store_visits_sanitized_YYYY-MM.csv` |
| Cross-channel store-to-call linkage | Join both on `customer_id` |
| Rep persona traits and burnout profiles | `rep-gen/novawireless_employee_database.csv` |
| Customer profiles and churn risk | `customer-gen/customers.csv` |
| Goodhart pressure experiment | `experiments/experiment_summary.csv` |

---

## Key Columns — Sanitized Call Data

| Column | Description |
|---|---|
| `resolution_flag` | Proxy metric — what the rep marked |
| `true_resolution` | Ground truth outcome |
| `churned` | Customer churned — tied to true resolution, NOT proxy |
| `incorrect_info_given` | Rep gave wrong information (tenure-driven) |
| `dar_signal` | Documentation accuracy signal |
| `dov_signal` | Rep verbalized limitation honestly |
| `trust_delta` | Customer trust change this call |
| `repeat_contact_30d` | Called back within 30 days |
| `repeat_contact_31_60d` | Called back 31–60 days |
| `audit_flag` | Any governance signal triggered |
| `audit_flag_reason` | Human-readable explanation |
| `transcript_text` | Full call transcript for NLP |

## Key Columns — Sanitized Store Data

| Column | Description |
|---|---|
| `memo_filed` | False = no memo filed at all |
| `memo_mismatch` | Memo says different thing than account change |
| `disclosure_ref_missing` | Required disclosure ref not filed |
| `memo_quality_score` | 0–1 quality score |
| `audit_flag` | Any audit condition triggered |
| `audit_flag_reason` | MISSING_MEMO / MEMO_MISMATCH / MISSING_DISCLOSURE_REF / clean |
| `memo_text` | Full structured memo text for NLP |

---

## Notes

- All output files are synthetic. See `LICENSE.md` at the repo root.
- Downstream projects (AnalysisLab, governance-pipeline) should point to the `sanitized/` folders.
- Raw store visit files (`store_visits_YYYY-MM.csv`) are retained but the sanitized versions include derived audit columns not present in the raw files.

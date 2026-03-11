# novawireless-customer-gen

**Pipeline Step 1 — Customer and Account Generation**

Generates the shared customer pool used by all downstream sub-projects. Every call center interaction and store visit in the pipeline traces back to a customer record created here.

---

## What It Produces

| Output | Location | Description |
|---|---|---|
| `customers.csv` | `data/` and `output/customer-gen/` | 2,000 synthetic customer profiles |
| `master_account_ledger.csv` | `data/` | Account and line records for all customers |
| `master_account_ledger__anomalies.csv` | `data/` | IMEI anomaly records for fraud detection modeling |
| `devices.csv` | `data/` | Synthetic device inventory |
| `eip_agreements.csv` | `data/` | Equipment installment plan records |
| `lines.csv` | `data/` | Line records per account |
| `line_device_usage.csv` | `data/` | Line-to-device usage mapping |

---

## Customer Profile Fields

Each customer record includes: `customer_id`, `account_id`, `tenure_months`, `monthly_charges`, `lines_on_account`, `churn_risk_score`, `trust_baseline`, `patience`, `is_churned`, and account type attributes.

Monthly charges and churn risk are calibrated to IBM Telco dataset priors. Trust baseline seeds the trust decay modeling in the call generator.

---

## Run

```bash
python src/customer_gen__run_all.py
```

Or via the root orchestrator:
```bash
python run_all.py
```

---

## Source Files

```
src/
├── generate_customers.py              ← core customer generation
├── 02_build_master_account_ledger.py  ← account and line record generation
├── 03_inject_imei_anomalies.py        ← IMEI anomaly injection for fraud modeling
└── customer_gen__run_all.py           ← sub-project orchestrator
```

---

## Notes

- Must run before all other sub-projects — downstream generators depend on `customers.csv` and `master_account_ledger.csv`.
- The account ledger is large (~75MB) because it contains full line and agreement records across all 2,000 customers.
- All data is fully synthetic. See `LICENSE.md` at the repo root.

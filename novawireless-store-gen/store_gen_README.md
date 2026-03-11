# novawireless-store-gen

**Pipeline Step 3 — Retail Store Representative and Visit Generation**

Generates ~120 retail store representative personas across 12 simulated store locations and produces 12 months of structured store visit records with full memo text and audit flags.

Store reps and call center reps are **entirely separate workforces** with different trait profiles. They share the same customer pool, connected via `customer_id`.

---

## What It Produces

| Output | Location | Description |
|---|---|---|
| `novawireless_store_rep_database.csv` | `data/` | ~120 store rep personas |
| `store_visits_YYYY-MM.csv` | `output/store-gen/` | Raw visit records with full memo text |
| `store_visits_sanitized_YYYY-MM.csv` | `output/store-gen/sanitized/` | Analysis-ready visits with audit flags — USE THESE |

---

## Store Rep Traits

| Trait | Description |
|---|---|
| `product_knowledge` | How well the rep knows the product catalog |
| `disclosure_diligence` | Likelihood of filing complete disclosure references |
| `ownership_bias` | Tendency to push specific products regardless of fit |
| `upsell_pressure` | Pressure to upsell above customer need |
| `memo_thoroughness` | Quality of memo documentation |
| `burnout_index` | Drives missing memo probability |
| `gaming_propensity` | Drives disclosure mismatch probability |

---

## Visit Types

Store reps can complete: `new_activation`, `device_upgrade`, `plan_change`, `promo_add`, `billing_question`, `trade_in`, `port_in`

Store reps can assist only (cannot complete): `port_out_pin`, `cancel_assist` — these redirect to the app or care line.

---

## The Memo System

Every store visit generates a structured four-section memo:

1. **Reason for Visit** — why the customer came in
2. **Rep Advised** — what the rep told the customer
3. **Customer Decision** — what the customer decided
4. **Account Changes Made + Disclosure Reference** — what changed and confirmation that correct pricing and product were disclosed

The disclosure reference is a compliance record confirming the right product was sold and the customer was shown correct terms. It is not an authorization reference.

### Audit Scenarios

| Scenario | Description | Audit Signal |
|---|---|---|
| Clean | Memo filed, disclosure ref matches account change | None |
| Disclosure mismatch | Memo exists but ref doesn't cover what was sold | `MEMO_MISMATCH` or `MISSING_DISCLOSURE_REF` |
| Missing memo | Account change made, no memo filed at all | `MISSING_MEMO` — strongest signal |

Missing memos are the strongest audit signal because the absence of a record means there is no accountability for what the customer was told.

---

## Cross-Channel Audit Capability

Store visit records link to call center records via `customer_id`. A customer who visits a store and calls the call center within 30 days on a related issue is a signal that something went wrong at the store interaction. This cross-channel linkage does not exist in current wireless carrier systems.

---

## Run

```bash
python src/store_gen__run_all.py
python src/store_gen__run_all.py --months 12 --n_stores 12
python src/store_gen__run_all.py --month 2025-06  # single month
python src/store_gen__run_all.py --skip_reps       # reps already generated
```

Or via the root orchestrator:
```bash
python run_all.py
```

---

## Source Files

```
src/
├── generate_store_reps.py         ← store rep persona generation
├── store_memo_builder.py          ← memo text construction
├── generate_store_visits.py       ← visit record generation
├── 02_sanitize_store_visits.py    ← sanitization and audit flag derivation
└── store_gen__run_all.py          ← sub-project orchestrator
```

---

## Notes

- Requires `data/customers.csv` from Step 1.
- Must run before analysis projects that use store data.
- Sanitized files include derived `audit_flag` and `audit_flag_reason` columns not present in raw files.
- All data is fully synthetic. See `LICENSE.md` at the repo root.

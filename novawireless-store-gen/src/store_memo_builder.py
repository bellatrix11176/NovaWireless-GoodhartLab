"""
store_memo_builder.py
=============================
NovaWireless-GoodhartLab — Store Interaction Memo Builder

Builds structured store interaction memos. Each memo documents:

  1. reason_for_visit     — why the customer came in
  2. rep_advised          — what the rep told / showed the customer
  3. customer_decision    — what the customer chose to do
  4. account_changes      — what was actually changed on the account
  5. disclosure_ref       — the disclosure document reference shown
                            to confirm correct advice was given
  6. memo_filed           — whether a memo was filed at all

Each record includes a memo_text field containing the full formatted
memo as it would appear on the account — readable by both humans and
NLP audit tools.

MEMO QUALITY DEGRADATION (Goodhart)
------------------------------------
Memos degrade under burnout pressure in three ways:
  1. Missing memo       — no memo filed at all (high burnout + traffic)
  2. Missing disclosure — memo filed but disclosure_ref is blank
  3. Memo mismatch      — memo describes different product/plan than
                          what was actually changed on the account

These are NOT intentional fraud. They are documentation failures
driven by cognitive depletion under pressure.

VISIT TYPES AND STORE RESTRICTIONS
------------------------------------
The store CAN complete:
  new_activation, device_upgrade, plan_change, promo_add,
  billing_question, trade_in, port_in

The store CAN ASSIST BUT NOT COMPLETE:
  port_out_pin    — help customer get PIN via app; no account change
  cancel_assist   — direct to app/call center; no account change in store

A memo showing a completed cancellation or port-out is a red flag.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime

# ── Visit type definitions ────────────────────────────────────────────────────

VISIT_TYPES = {
    "new_activation": {
        "label":               "New Line / Activation",
        "can_complete":        True,
        "requires_disclosure": True,
        "account_change":      "new_line_added",
    },
    "device_upgrade": {
        "label":               "Device Upgrade",
        "can_complete":        True,
        "requires_disclosure": True,
        "account_change":      "device_upgraded",
    },
    "plan_change": {
        "label":               "Plan Change",
        "can_complete":        True,
        "requires_disclosure": True,
        "account_change":      "plan_changed",
    },
    "promo_add": {
        "label":               "Promotion Added",
        "can_complete":        True,
        "requires_disclosure": True,
        "account_change":      "promo_applied",
    },
    "billing_question": {
        "label":               "Billing Question",
        "can_complete":        True,
        "requires_disclosure": False,
        "account_change":      "none",
    },
    "trade_in": {
        "label":               "Trade-In",
        "can_complete":        True,
        "requires_disclosure": True,
        "account_change":      "trade_in_processed",
    },
    "port_in": {
        "label":               "Port-In from Another Carrier",
        "can_complete":        True,
        "requires_disclosure": True,
        "account_change":      "port_in_completed",
    },
    "port_out_pin": {
        "label":               "Port-Out PIN Assistance",
        "can_complete":        False,
        "requires_disclosure": False,
        "account_change":      "none",
    },
    "cancel_assist": {
        "label":               "Cancellation Assistance",
        "can_complete":        False,
        "requires_disclosure": False,
        "account_change":      "none",
    },
}

# Visit type base weights (realistic foot traffic distribution)
VISIT_WEIGHTS = {
    "new_activation":   0.18,
    "device_upgrade":   0.22,
    "plan_change":      0.14,
    "promo_add":        0.12,
    "billing_question": 0.14,
    "trade_in":         0.10,
    "port_in":          0.06,
    "port_out_pin":     0.02,
    "cancel_assist":    0.02,
}

# ── Disclosure reference templates ────────────────────────────────────────────
DISCLOSURE_REFS = {
    "new_activation":   ["DISC-ACT-2025-{n}", "DISC-EIP-2025-{n}", "DISC-NEW-2025-{n}"],
    "device_upgrade":   ["DISC-UPG-2025-{n}", "DISC-EIP-2025-{n}"],
    "plan_change":      ["DISC-PLAN-2025-{n}", "DISC-RC-2025-{n}"],
    "promo_add":        ["DISC-PROMO-2025-{n}", "DISC-TERMS-2025-{n}"],
    "trade_in":         ["DISC-TRADE-2025-{n}", "DISC-EIP-2025-{n}"],
    "port_in":          ["DISC-PORT-2025-{n}", "DISC-ACT-2025-{n}"],
    "billing_question": ["N/A"],
    "port_out_pin":     ["N/A"],
    "cancel_assist":    ["N/A"],
}

# ── Memo text templates ───────────────────────────────────────────────────────
ADVISED_TEMPLATES = {
    "new_activation": [
        "Advised customer on available plans and device options. Reviewed EIP terms and monthly rate card.",
        "Presented new activation options including Essentials, Go5G, and Go5G Plus. Customer reviewed pricing sheet.",
        "Walked customer through activation process. Explained plan features, device payment terms, and port-in timeline.",
    ],
    "device_upgrade": [
        "Reviewed available upgrade options and current device trade-in value. Presented EIP terms for new device.",
        "Advised customer on eligible upgrade devices. Reviewed 24-month EIP agreement and residual trade-in credit.",
        "Presented upgrade path. Customer reviewed device pricing, EIP schedule, and plan compatibility.",
    ],
    "plan_change": [
        "Reviewed current plan and presented available plan options. Explained feature differences and pricing impact.",
        "Advised customer on plan change options. Reviewed rate differences and feature comparison sheet.",
        "Presented plan change options. Customer reviewed current vs. new plan pricing and feature details.",
    ],
    "promo_add": [
        "Advised customer on available promotions. Reviewed promotional terms, duration, and eligibility requirements.",
        "Presented active promotions. Customer reviewed promo terms sheet including auto-pay requirements.",
        "Reviewed promotional offer details with customer including discount duration and qualifying conditions.",
    ],
    "billing_question": [
        "Reviewed account charges with customer. Explained billing cycle, recent charges, and payment history.",
        "Assisted customer in reviewing recent bill. Clarified charge itemization and payment options.",
        "Reviewed billing statement with customer. Explained current balance, due date, and available payment methods.",
    ],
    "trade_in": [
        "Assessed trade-in device condition. Presented trade-in value and applicable device credit toward upgrade.",
        "Reviewed trade-in eligibility and current device value. Customer reviewed trade-in terms and credit application.",
        "Processed trade-in assessment. Advised customer on device condition grading and applicable credit amount.",
    ],
    "port_in": [
        "Assisted customer with port-in from previous carrier. Reviewed number transfer timeline and account setup.",
        "Guided customer through port-in process. Reviewed required account information and expected transfer window.",
        "Processed port-in request. Explained port timeline, temporary number provision, and service activation.",
    ],
    "port_out_pin": [
        "Assisted customer in locating port-out PIN via app. Directed customer to complete port process with new carrier.",
        "Helped customer retrieve account number and port-out PIN through app. Advised on port-out process.",
    ],
    "cancel_assist": [
        "Reviewed account status with customer. Directed customer to contact care line or use app for cancellation.",
        "Assisted customer in understanding cancellation process. Directed to customer care for account closure.",
    ],
}

DECISION_TEMPLATES = {
    "new_activation": [
        "Customer proceeded with new activation on Go5G Plus plan.",
        "Customer activated new line on Essentials plan.",
        "Customer chose Go5G plan and completed new activation.",
    ],
    "device_upgrade": [
        "Customer proceeded with device upgrade.",
        "Customer accepted upgrade offer and signed EIP agreement.",
        "Customer chose new device and completed upgrade transaction.",
    ],
    "plan_change": [
        "Customer chose to change plan as discussed.",
        "Customer selected new plan tier.",
        "Customer opted to upgrade plan.",
    ],
    "promo_add": [
        "Customer accepted promotional offer.",
        "Customer opted in to promotion as presented.",
        "Customer chose to apply available promotion.",
    ],
    "billing_question": [
        "Customer reviewed account charges. No changes requested.",
        "Customer satisfied with billing explanation. No action taken.",
        "Customer reviewed statement. Issue resolved through explanation.",
    ],
    "trade_in": [
        "Customer accepted trade-in value and proceeded with upgrade.",
        "Customer completed trade-in transaction.",
        "Customer agreed to trade-in terms and processed device.",
    ],
    "port_in": [
        "Customer completed port-in. Number transfer initiated.",
        "Customer proceeded with port-in activation.",
        "Customer ported number in from previous carrier.",
    ],
    "port_out_pin": [
        "Customer retrieved port-out PIN via app. Directed to new carrier to complete transfer.",
        "Customer located account PIN. Will complete port with new carrier.",
    ],
    "cancel_assist": [
        "Customer directed to customer care line to complete cancellation.",
        "Customer advised to use app or call care to process cancellation. No account changes made in store.",
    ],
}


# ── Memo text formatter ───────────────────────────────────────────────────────

def format_memo_text(
    visit_id:       str,
    store_id:       str,
    store_name:     str,
    rep_id:         str,
    customer_id:    str,
    month:          str,
    visit_label:    str,
    advised_text:   str,
    decision_text:  str,
    actual_change:  str,
    memo_change:    str,
    disc_ref:       str,
    disc_missing:   bool,
    requires_disc:  bool,
) -> str:
    """
    Format the full structured memo text as it appears on the account.
    This is the field NLP audit tools read to verify memo accuracy.
    """
    disc_line = ""
    if requires_disc:
        if disc_missing or disc_ref in ("", None):
            disc_line = "  Disclosure Reference : *** MISSING — NOT FILED ***"
        else:
            disc_line = f"  Disclosure Reference : {disc_ref}"
    else:
        disc_line = "  Disclosure Reference : N/A (not required for this visit type)"

    lines = [
        f"STORE INTERACTION MEMO",
        f"{'─' * 52}",
        f"  Visit ID     : {visit_id}",
        f"  Store        : {store_id} — {store_name}",
        f"  Rep ID       : {rep_id}",
        f"  Customer ID  : {customer_id}",
        f"  Month        : {month}",
        f"{'─' * 52}",
        f"",
        f"  REASON FOR VISIT",
        f"  {visit_label}",
        f"",
        f"  REP ADVISED",
        f"  {advised_text}",
        f"",
        f"  CUSTOMER DECISION",
        f"  {decision_text}",
        f"",
        f"  ACCOUNT CHANGES MADE",
        f"  {memo_change}",
        f"",
        disc_line,
        f"{'─' * 52}",
    ]
    return "\n".join(lines)


def format_missing_memo_text(
    visit_id:    str,
    store_id:    str,
    store_name:  str,
    rep_id:      str,
    customer_id: str,
    month:       str,
    visit_label: str,
    actual_change: str,
) -> str:
    """
    Placeholder memo text when no memo was filed.
    The account change exists but no documentation was created.
    This is the strongest audit red flag.
    """
    lines = [
        f"STORE INTERACTION MEMO",
        f"{'─' * 52}",
        f"  Visit ID     : {visit_id}",
        f"  Store        : {store_id} — {store_name}",
        f"  Rep ID       : {rep_id}",
        f"  Customer ID  : {customer_id}",
        f"  Month        : {month}",
        f"{'─' * 52}",
        f"",
        f"  *** MEMO NOT FILED ***",
        f"",
        f"  Account change recorded : {actual_change}",
        f"  No documentation was submitted by the rep.",
        f"  Reason for visit, advice given, customer decision,",
        f"  and disclosure reference are all unknown.",
        f"{'─' * 52}",
    ]
    return "\n".join(lines)


# ── Core memo builder ─────────────────────────────────────────────────────────

def build_memo(
    visit_type: str,
    rep:        dict,
    customer:   dict,
    rng:        random.Random,
    month:      str = "2025-01",
) -> dict:
    """
    Build a store interaction memo for one visit.

    Returns a dict with all memo fields including memo_text —
    the full formatted memo as it appears on the account.

    memo_filed=False means no memo was created — the account change
    happened but nothing was documented. This is the strongest audit
    red flag.
    """
    vt         = VISIT_TYPES[visit_type]
    burnout    = rep.get("burnout_index",        0.40)
    gaming_p   = rep.get("gaming_propensity",    0.20)
    upsell_p   = rep.get("upsell_pressure",      0.40)
    memo_thor  = rep.get("memo_thoroughness",    0.65)
    disc_dilig = rep.get("disclosure_diligence", 0.65)
    store_name = rep.get("store_name",           "Unknown Store")

    visit_id    = f"VISIT-{uuid.uuid4().hex[:10].upper()}"
    store_id    = rep.get("store_id",    "")
    rep_id      = rep.get("rep_id",      "")
    customer_id = customer.get("customer_id", "")

    # ── Missing memo ──────────────────────────────────────────────────────────
    missing_memo_prob = clamp(burnout * 0.25 + gaming_p * 0.15)
    if rng.random() < missing_memo_prob:
        memo_text = format_missing_memo_text(
            visit_id, store_id, store_name, rep_id,
            customer_id, month, vt["label"], vt["account_change"]
        )
        return _missing_memo_record(
            visit_type, vt, rep, customer, month, visit_id, memo_text
        )

    # ── Memo content ──────────────────────────────────────────────────────────
    advised_text  = rng.choice(ADVISED_TEMPLATES.get(visit_type, ["Advised customer on account options."]))
    decision_text = rng.choice(DECISION_TEMPLATES.get(visit_type, ["Customer made a decision."]))
    actual_change = vt["account_change"]

    # Memo mismatch
    mismatch_prob = clamp(upsell_p * 0.20 + gaming_p * 0.25 - memo_thor * 0.15)
    memo_mismatch = False
    memo_change   = actual_change
    if vt["can_complete"] and vt["account_change"] != "none":
        if rng.random() < mismatch_prob:
            memo_mismatch = True
            memo_change   = _mismatch_change(visit_type, rng)

    # Disclosure reference
    disc_ref     = "N/A"
    disc_missing = False
    if vt["requires_disclosure"]:
        missing_disc_prob = clamp(gaming_p * 0.30 + burnout * 0.20 - disc_dilig * 0.25)
        if rng.random() < missing_disc_prob:
            disc_ref     = ""
            disc_missing = True
        else:
            template = rng.choice(DISCLOSURE_REFS.get(visit_type, ["DISC-GEN-2025-{n}"]))
            disc_ref = template.format(n=rng.randint(1000, 9999))

    # Format full memo text
    memo_text = format_memo_text(
        visit_id      = visit_id,
        store_id      = store_id,
        store_name    = store_name,
        rep_id        = rep_id,
        customer_id   = customer_id,
        month         = month,
        visit_label   = vt["label"],
        advised_text  = advised_text,
        decision_text = decision_text,
        actual_change = actual_change,
        memo_change   = memo_change,
        disc_ref      = disc_ref,
        disc_missing  = disc_missing,
        requires_disc = vt["requires_disclosure"],
    )

    return {
        "visit_id":                    visit_id,
        "month":                       month,
        "store_id":                    store_id,
        "store_name":                  store_name,
        "rep_id":                      rep_id,
        "customer_id":                 customer_id,
        "memo_filed":                  True,
        "visit_type":                  visit_type,
        "visit_label":                 vt["label"],
        "can_complete":                vt["can_complete"],
        "reason_for_visit":            vt["label"],
        "rep_advised":                 advised_text,
        "customer_decision":           decision_text,
        "account_change_actual":       actual_change,
        "account_change_in_memo":      memo_change,
        "memo_mismatch":               memo_mismatch,
        "disclosure_ref":              disc_ref,
        "disclosure_ref_missing":      disc_missing,
        "requires_disclosure":         vt["requires_disclosure"],
        "system_restriction_violation":False,
        "memo_quality_score":          _memo_quality(disc_missing, memo_mismatch, memo_thor, rng),
        "memo_text":                   memo_text,
    }


def _missing_memo_record(visit_type, vt, rep, customer, month, visit_id, memo_text) -> dict:
    return {
        "visit_id":                    visit_id,
        "month":                       month,
        "store_id":                    rep.get("store_id",    ""),
        "store_name":                  rep.get("store_name",  ""),
        "rep_id":                      rep.get("rep_id",      ""),
        "customer_id":                 customer.get("customer_id", ""),
        "memo_filed":                  False,
        "visit_type":                  visit_type,
        "visit_label":                 vt["label"],
        "can_complete":                vt["can_complete"],
        "reason_for_visit":            "N/A",
        "rep_advised":                 "N/A",
        "customer_decision":           "N/A",
        "account_change_actual":       vt["account_change"],
        "account_change_in_memo":      "N/A",
        "memo_mismatch":               False,
        "disclosure_ref":              "N/A",
        "disclosure_ref_missing":      vt["requires_disclosure"],
        "requires_disclosure":         vt["requires_disclosure"],
        "system_restriction_violation":False,
        "memo_quality_score":          0.0,
        "memo_text":                   memo_text,
    }


def _mismatch_change(visit_type: str, rng: random.Random) -> str:
    all_changes = [v["account_change"] for v in VISIT_TYPES.values()
                   if v["account_change"] != "none"]
    actual  = VISIT_TYPES[visit_type]["account_change"]
    options = [c for c in all_changes if c != actual]
    return rng.choice(options) if options else actual


def _memo_quality(disc_missing: bool, mismatch: bool, thoroughness: float,
                  rng: random.Random) -> float:
    score = thoroughness
    if disc_missing: score -= 0.25
    if mismatch:     score -= 0.35
    score += (rng.random() - 0.5) * 0.10
    return round(max(0.0, min(1.0, score)), 4)


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def sample_visit_type(rng: random.Random) -> str:
    keys  = list(VISIT_WEIGHTS.keys())
    probs = [VISIT_WEIGHTS[k] for k in keys]
    total = sum(probs)
    probs = [p / total for p in probs]
    r     = rng.random()
    cumul = 0.0
    for k, p in zip(keys, probs):
        cumul += p
        if r < cumul:
            return k
    return keys[-1]

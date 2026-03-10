#!/usr/bin/env python3
"""
03_build_analysis_dataset.py
============================
NovaWireless-GoodhartLab — Analysis Dataset Builder

Reads transcripts.jsonl + calls_metadata.csv and produces calls_full.csv —
one analysis-ready row per call with both structured metadata and NLP features
extracted from the transcript text.

DAR / DOV columns are derived here from transcript signals and structured
metadata so the GoodhartLab output schema matches the GovernanceLab schema
for side-by-side gap analysis.

    dar_signal  — Documentation Accuracy Rate proxy (0/1 per call)
                  1 if: no hedge language + no commitment failure + proxy==true
                  0 otherwise
    dov_signal  — Discomfort-Owning Verbalization proxy (0/1 per call)
                  1 if: rep used honest limitation language on an unresolvable call
                  0 otherwise (or if rep deflected / gamed instead)
    trust_delta — Estimated trust change this call
                  derived from scenario trust decay + customer sentiment trend

These are PROXY signals in GoodhartLab (inferred from transcripts).
In GovernanceLab they are DIRECT signals (set by the measurement regime).
The gap between proxy and direct is part of what the experiment measures.

Run:
    python src/03_build_analysis_dataset.py

Inputs (output/ folder):
    transcripts_*.jsonl  (or transcripts.jsonl for single-month runs)
    calls_metadata_*.csv (or calls_metadata.csv)

Output:
    output/calls_full.csv
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def find_repo_root(start=None) -> Path:
    cur = Path(start or __file__).resolve()
    if cur.is_file():
        cur = cur.parent
    labroot_paths = []
    node = cur
    while True:
        if (node / ".labroot").exists():
            labroot_paths.append(node)
        if node.parent == node:
            break
        node = node.parent
    if labroot_paths:
        return labroot_paths[-1]
    node = cur
    while True:
        if (node / "src").is_dir() and (node / "data").is_dir():
            return node
        if node.parent == node:
            break
        node = node.parent
    return Path.cwd().resolve()


REPO_ROOT  = find_repo_root()
OUTPUT_DIR = REPO_ROOT / "output"

# Support both single-file and multi-month output layouts
def find_latest_or_combined(pattern_multi: str, fallback: str) -> Path:
    """Return combined multi-month files or fall back to single file."""
    hits = sorted(OUTPUT_DIR.glob(pattern_multi))
    if hits:
        return hits  # caller handles list
    fb = OUTPUT_DIR / fallback
    return [fb] if fb.exists() else []

TRANSCRIPTS_PATH = OUTPUT_DIR / "transcripts.jsonl"
METADATA_PATH    = OUTPUT_DIR / "calls_metadata.csv"
OUTPUT_PATH      = OUTPUT_DIR / "calls_full.csv"


# ---------------------------------------------------------------------------
# Lexicons — what we scan for in the text
# ---------------------------------------------------------------------------

# Rep hedging / uncertainty language (signals lack of confidence or stalling)
HEDGE_PHRASES = [
    "let me check", "let me look", "one moment", "give me a second",
    "i believe", "i think", "should be", "might be", "typically",
    "i'm not sure", "i'm not certain", "i'll have to", "let me see",
    "i need to verify", "i want to make sure", "let me verify",
]

# Apology language
APOLOGY_PHRASES = [
    "i'm sorry", "i apologize", "i understand your frustration",
    "i'm so sorry", "i completely understand", "i hear you",
    "your frustration is", "i'm truly sorry",
]

# Escalation language — rep moving the call up or out
ESCALATION_PHRASES = [
    "escalate", "escalation", "supervisor", "manager", "dispute team",
    "store relations", "store accountability", "network engineering",
    "port dispute", "override team", "promotions team", "research ticket",
    "investigation", "unauthorized", "flagged",
]

# Customer frustration signals
FRUSTRATION_PHRASES = [
    "this is ridiculous", "i can't believe", "this is unacceptable",
    "i'm going to cancel", "i want to cancel", "i'm filing a complaint",
    "i'm not happy", "i've been waiting", "nobody told me",
    "the store lied", "every time i call", "nothing happens",
    "i just hope", "i'm frustrated", "fine, whatever", "fine.",
]

# Resolution commitment language — rep promising a fix
COMMITMENT_PHRASES = [
    "i've gone ahead and", "i'm going to apply", "i've applied",
    "i'm waiving", "i've waived", "i'm crediting", "i've credited",
    "i'm escalating", "i've escalated", "i've documented",
    "will be honored", "will be resolved", "case number",
    "i've noted", "i'm flagging",
]

# Price / billing language
BILLING_PHRASES = [
    "credit", "charge", "bill", "billing", "payment", "fee",
    "discount", "promotion", "promo", "refund", "waive",
    "installment", "eip", "monthly", "balance",
]

# Cancellation threat language
CANCEL_PHRASES = [
    "cancel", "cancelling", "canceling", "leaving", "switching",
    "i'm done", "close my account", "port my number out",
]

# ---------------------------------------------------------------------------
# DAR / DOV lexicons
# ---------------------------------------------------------------------------

# Honest limitation language — rep verbally owns what they can't fix
# High presence on unresolvable calls = DOV signal
HONEST_LIMITATION_PHRASES = [
    "i'm not able to", "i cannot", "i can't override",
    "i want to be honest", "i wish i could fix",
    "there's a process we have to go through",
    "i don't have the tools", "that requires", "i have to escalate",
    "i can't resolve this from my system",
    "this is a system-level", "i'm not able to reverse",
]

# False closure language — rep pretends issue is resolved when it isn't
# High presence = DAR signal degraded (documentation inaccuracy)
FALSE_CLOSURE_PHRASES = [
    "that's all taken care of", "you're all set",
    "that's been resolved", "i've resolved that",
    "everything is fixed", "that won't happen again",
    "i've taken care of everything",
]

# Bandaid language — unauthorized hush-money credit pattern
BANDAID_PHRASES = [
    "soften the impact", "to make up for",
    "help with that this cycle", "as a one-time gesture",
    "i understand that's not the same",
]


# ---------------------------------------------------------------------------
# Feature extraction — per call
# ---------------------------------------------------------------------------

def count_phrases(text: str, phrases: list[str]) -> int:
    """Count how many times any phrase in the list appears in lowercased text."""
    text_lower = text.lower()
    return sum(text_lower.count(p) for p in phrases)


def extract_turn_features(turns: list[dict]) -> dict:
    """
    Extract NLP features from a list of turn dicts.
    Each turn: {"speaker": "Agent"|"Customer", "text": str}
    """
    agent_turns    = [t for t in turns if t.get("speaker") == "Agent"]
    customer_turns = [t for t in turns if t.get("speaker") == "Customer"]

    agent_text    = " ".join(t.get("text", "") for t in agent_turns)
    customer_text = " ".join(t.get("text", "") for t in customer_turns)
    full_text     = " ".join(t.get("text", "") for t in turns)

    agent_words    = len(agent_text.split())
    customer_words = len(customer_text.split())
    total_words    = agent_words + customer_words

    n_turns         = len(turns)
    n_agent_turns   = len(agent_turns)
    n_customer_turns = len(customer_turns)

    # Talk ratio — how much of the conversation the agent dominates
    agent_talk_ratio = round(agent_words / total_words, 4) if total_words > 0 else 0.5

    # Turn-level sentiment proxy — simple positive/negative word ratio
    # Using a minimal lexicon so there's no external dependency
    positive_words = [
        "great", "perfect", "wonderful", "happy", "appreciate", "thank",
        "absolutely", "resolved", "fixed", "better", "good", "glad",
        "excellent", "helpful", "understand", "honored", "waived", "credited",
    ]
    negative_words = [
        "frustrated", "angry", "ridiculous", "unacceptable", "upset",
        "problem", "issue", "wrong", "error", "mistake", "complaint",
        "cancel", "stuck", "lied", "confused", "never", "nothing",
        "worse", "bad", "terrible", "horrible", "disappointed",
    ]

    full_lower = full_text.lower()
    pos_count  = sum(full_lower.count(w) for w in positive_words)
    neg_count  = sum(full_lower.count(w) for w in negative_words)
    total_sentiment_words = pos_count + neg_count

    sentiment_score = round(
        (pos_count - neg_count) / total_sentiment_words, 4
    ) if total_sentiment_words > 0 else 0.0

    # Sentiment trend — compare first half vs second half of transcript
    mid = len(turns) // 2
    first_half = " ".join(t.get("text", "") for t in turns[:mid]).lower()
    second_half = " ".join(t.get("text", "") for t in turns[mid:]).lower()

    def sentiment(text: str) -> float:
        p = sum(text.count(w) for w in positive_words)
        n = sum(text.count(w) for w in negative_words)
        return (p - n) / (p + n) if (p + n) > 0 else 0.0

    sentiment_trend = round(sentiment(second_half) - sentiment(first_half), 4)

    # Customer sentiment specifically
    cust_lower = customer_text.lower()
    cust_pos   = sum(cust_lower.count(w) for w in positive_words)
    cust_neg   = sum(cust_lower.count(w) for w in negative_words)
    customer_sentiment = round(
        (cust_pos - cust_neg) / (cust_pos + cust_neg), 4
    ) if (cust_pos + cust_neg) > 0 else 0.0

    # Phrase-level features
    hedge_count       = count_phrases(agent_text, HEDGE_PHRASES)
    apology_count     = count_phrases(agent_text, APOLOGY_PHRASES)
    escalation_count  = count_phrases(full_text,  ESCALATION_PHRASES)
    commitment_count  = count_phrases(agent_text, COMMITMENT_PHRASES)
    billing_count     = count_phrases(full_text,  BILLING_PHRASES)

    customer_frustration_count = count_phrases(customer_text, FRUSTRATION_PHRASES)
    customer_cancel_threat     = int(count_phrases(customer_text, CANCEL_PHRASES) > 0)

    contains_apology           = int(apology_count > 0)
    contains_escalation_lang   = int(escalation_count > 0)
    contains_commitment        = int(commitment_count > 0)
    contains_billing_lang      = int(billing_count > 0)
    contains_frustration       = int(customer_frustration_count > 0)

    # ---------------------------------------------------------------------------
    # DAR / DOV proxy signals (GoodhartLab — inferred from transcript text)
    # In GovernanceLab these are set directly by the measurement regime.
    # Here they are derived, so they are noisier — that noise is part of the gap.
    # ---------------------------------------------------------------------------

    honest_limitation_count = count_phrases(agent_text, HONEST_LIMITATION_PHRASES)
    false_closure_count     = count_phrases(agent_text, FALSE_CLOSURE_PHRASES)
    bandaid_count           = count_phrases(agent_text, BANDAID_PHRASES)

    # DOV (Discomfort-Owning Verbalization):
    # Rep explicitly verbalized a limitation rather than deflecting or gaming.
    # Requires honest limitation language AND no false closure AND no bandaid.
    dov_signal = int(
        honest_limitation_count >= 1
        and false_closure_count == 0
        and bandaid_count == 0
    )

    # DAR (Documentation Accuracy Rate proxy):
    # Documentation is likely accurate when:
    #   - No excessive hedging (rep knew what they were doing)
    #   - No false closure (didn't mark resolved when it wasn't)
    #   - No bandaid credit language (no hush-money pattern)
    #   - Commitment count >= 1 (rep made a concrete documented promise)
    dar_signal = int(
        hedge_count <= 2
        and false_closure_count == 0
        and bandaid_count == 0
        and commitment_count >= 1
    )

    # trust_delta proxy: estimated trust change this call
    # Positive = customer left more trusting, negative = less trusting
    # Derived from: sentiment trend + dov_signal + bandaid presence
    trust_delta = round(
        sentiment_trend * 0.04          # sentiment improvement/degradation
        + dov_signal    * 0.02          # honest limitation language builds trust
        - bandaid_count * 0.03          # bandaid signals false resolution
        - false_closure_count * 0.04    # false closure actively degrades trust
        - customer_cancel_threat * 0.05,# cancel threat = strong trust signal
        4
    )

    # Rep wrap speed proxy — how long is the closer relative to body?
    # Short closer relative to body suggests rep rushed the end of the call
    closer_turns = turns[-3:] if len(turns) >= 3 else turns
    opener_turns = turns[:5]  if len(turns) >= 5 else turns
    body_turns   = turns[5:-3] if len(turns) > 8 else turns

    closer_words = sum(len(t.get("text", "").split()) for t in closer_turns)
    body_words   = sum(len(t.get("text", "").split()) for t in body_turns)
    wrap_ratio   = round(closer_words / body_words, 4) if body_words > 0 else 0.0

    # Question count — customer asking questions signals unresolved confusion
    customer_question_count = sum(
        t.get("text", "").count("?") for t in customer_turns
    )
    agent_question_count = sum(
        t.get("text", "").count("?") for t in agent_turns
    )

    return {
        # Turn structure
        "n_turns":                  n_turns,
        "n_agent_turns":            n_agent_turns,
        "n_customer_turns":         n_customer_turns,
        "agent_word_count":         agent_words,
        "customer_word_count":      customer_words,
        "total_word_count":         total_words,
        "agent_talk_ratio":         agent_talk_ratio,

        # Sentiment
        "sentiment_score":          sentiment_score,       # overall: -1 (neg) to +1 (pos)
        "sentiment_trend":          sentiment_trend,       # + means call improved, - means degraded
        "customer_sentiment":       customer_sentiment,    # customer-only sentiment

        # Rep behavior signals
        "rep_hedge_count":          hedge_count,           # uncertainty / stalling language
        "rep_apology_count":        apology_count,
        "rep_commitment_count":     commitment_count,      # promises made
        "rep_escalation_count":     escalation_count,
        "rep_wrap_ratio":           wrap_ratio,            # low = rushed close

        # Customer behavior signals
        "customer_frustration_count": customer_frustration_count,
        "customer_question_count":    customer_question_count,
        "agent_question_count":       agent_question_count,

        # Binary flags
        "contains_apology":           contains_apology,
        "contains_escalation_lang":   contains_escalation_lang,
        "contains_commitment":        contains_commitment,
        "contains_billing_lang":      contains_billing_lang,
        "contains_frustration":       contains_frustration,
        "customer_cancel_threat":     customer_cancel_threat,
        # DAR / DOV governance signal proxies
        "dar_signal":                 dar_signal,
        "dov_signal":                 dov_signal,
        "trust_delta":                trust_delta,
        "honest_limitation_count":    honest_limitation_count,
        "false_closure_count":        false_closure_count,
        "bandaid_count":              bandaid_count,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_transcripts(path: Path) -> dict[str, dict]:
    """Load JSONL into a dict keyed by call_id."""
    records = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records[obj["call_id"]] = obj
    return records


def main() -> int:
    print("build_analysis_dataset.py")
    print(f"  Transcripts: {TRANSCRIPTS_PATH}")
    print(f"  Metadata:    {METADATA_PATH}")
    print(f"  Output:      {OUTPUT_PATH}")
    print()

    # --- Validate inputs ---
    for p in [TRANSCRIPTS_PATH, METADATA_PATH]:
        if not p.exists():
            print(f"[ERROR] Missing required file: {p}")
            print("  Run generate_calls.py first.")
            sys.exit(1)

    # --- Load ---
    print("Loading metadata...")
    metadata = pd.read_csv(METADATA_PATH, low_memory=False)
    print(f"  {len(metadata):,} call records loaded.")

    print("Loading transcripts...")
    transcripts = load_transcripts(TRANSCRIPTS_PATH)
    print(f"  {len(transcripts):,} transcripts loaded.")

    # --- Extract features ---
    print("Extracting transcript features...")
    feature_rows = []
    missing = 0

    for call_id, obj in transcripts.items():
        turns = obj.get("turns", [])
        if not turns:
            missing += 1
            continue
        feats = extract_turn_features(turns)
        feats["call_id"] = call_id
        feature_rows.append(feats)

    if missing > 0:
        print(f"  Warning: {missing} transcripts had no turns and were skipped.")

    features_df = pd.DataFrame(feature_rows)
    print(f"  Features extracted for {len(features_df):,} calls.")

    # --- Join ---
    print("Joining to metadata...")
    calls_full = metadata.merge(features_df, on="call_id", how="left")

    # --- Integrity check ---
    n_matched   = calls_full["n_turns"].notna().sum()
    n_unmatched = calls_full["n_turns"].isna().sum()
    print(f"  Matched:   {n_matched:,}")
    print(f"  Unmatched: {n_unmatched:,}")
    if n_unmatched > 0:
        print(f"  Warning: {n_unmatched} metadata rows had no matching transcript.")

    # --- Summary stats ---
    print()
    print("Feature summary:")
    summary_cols = [
        "n_turns", "agent_word_count", "customer_word_count",
        "sentiment_score", "sentiment_trend", "customer_sentiment",
        "rep_hedge_count", "rep_commitment_count",
        "customer_frustration_count", "customer_cancel_threat",
        "contains_apology", "contains_escalation_lang",
        # DAR / DOV governance proxies
        "dar_signal", "dov_signal", "trust_delta",
        "honest_limitation_count", "false_closure_count", "bandaid_count",
    ]
    for col in summary_cols:
        if col in calls_full.columns:
            mean = calls_full[col].mean()
            print(f"  {col:<35} mean={mean:.3f}")

    # --- Write ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    calls_full.to_csv(OUTPUT_PATH, index=False)
    print()
    print(f"[OK] Wrote {len(calls_full):,} rows → {OUTPUT_PATH}")
    print(f"     Columns: {len(calls_full.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

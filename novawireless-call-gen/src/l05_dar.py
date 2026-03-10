"""
l05_dar.py — NovaWireless-AnalysisLab New Lab
DAR: Deferred Action Rate (SII context) + Documentation Accuracy Rate (Behavioral context)

SII context — System Integrity Audit:
  DAR = calls flagged FCR=1 that generated a repeat contact in the 31–60 day window.
  Catches latent failures that fall outside the standard 30-day FCR measurement period.
  The exact mechanic that makes bandaid credits invisible to the legacy model.

Behavioral context — Governance Lens:
  DAR = Documentation Accuracy Rate: resolution_flag matches true_resolution.
  Resistant to gaming because documentation is checked against system records.
  Legacy world average: ~66.1%. Governance-led average: ~91.5%.

Produces 4 figures: l05a, l05b, l05c, l05d
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec

from utils import clean_ax, save_fig, assign_teams
from utils import C_RED, C_GREEN, C_BLUE, C_ORANGE, C_PURPLE, C_DARK, C_GREY, C_TEAL, C_DARK2


def _compute_dar_sii(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deferred Action Rate (SII):
    Among calls where resolution_flag == 1 (system says 'resolved'),
    what fraction generated a repeat_contact_31_60d == 1?
    These are the latent failures — resolved on paper, failed in reality,
    but timed out of the standard 30-day FCR audit window.
    """
    resolved = df[df["resolution_flag"] == 1].copy()
    monthly = resolved.groupby("month").agg(
        dar_sii      = ("repeat_contact_31_60d", "mean"),
        n_resolved   = ("call_id", "count"),
    ).reset_index()
    return monthly


def _compute_dar_behavioral(df: pd.DataFrame) -> pd.DataFrame:
    """
    Documentation Accuracy Rate (Behavioral):
    Reads dar_signal column directly — this is the governance generator's
    per-call documentation accuracy signal, set by DAR_SIGNAL_PROBS in
    scenario_router.py.

    IMPORTANT: do NOT recompute from resolution_flag == true_resolution.
    Both of those columns are overwritten by 02_sanitize_calls.py using its
    own probability tables. Only dar_signal passes through the sanitizer
    untouched and reflects the governance generator's intent.
    """
    df = df.copy()
    if "dar_signal" in df.columns:
        df["dar_match"] = df["dar_signal"].astype(int)
    else:
        # Fallback for legacy CSVs without dar_signal column
        df["dar_match"] = (df["resolution_flag"].astype(int) == df["true_resolution"].astype(int)).astype(int)
    monthly = df.groupby("month").agg(
        dar_behavioral = ("dar_match", "mean"),
        n              = ("call_id", "count"),
    ).reset_index()
    return monthly


def run(df: pd.DataFrame) -> dict:
    print("\n[L05] DAR — Deferred Action Rate + Documentation Accuracy Rate")

    df = assign_teams(df)
    df["call_date"] = pd.to_datetime(df["call_date"])
    df["month"]     = df["call_date"].dt.to_period("M").astype(str)
    months          = sorted(df["month"].unique())
    month_labels    = [m[5:] for m in months]
    x               = list(range(len(months)))
    year_label      = months[0][:4] if months else "2025"

    dar_sii  = _compute_dar_sii(df)
    dar_beh  = _compute_dar_behavioral(df)

    # Align month ordering
    dar_sii  = dar_sii.set_index("month").reindex(months).reset_index()
    dar_beh  = dar_beh.set_index("month").reindex(months).reset_index()

    # Overall scalars
    overall_dar_sii = dar_sii["dar_sii"].mean()
    overall_dar_beh = dar_beh["dar_behavioral"].mean()
    overall_fcr     = df["resolution_flag"].mean()

    # ── L05a: DAR-SII monthly — latent failure rate ───────────────────────────
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(x, dar_sii["dar_sii"].tolist(), "o-", color=C_RED, linewidth=2.2,
            markersize=5, label="DAR-SII: Deferred Action Rate (31–60 day window)")
    ax.fill_between(x, 0, dar_sii["dar_sii"].tolist(), alpha=0.12, color=C_RED)
    ax.axhline(overall_dar_sii, color=C_DARK, linestyle="--", linewidth=1.2,
               label=f"Annual avg: {overall_dar_sii:.1%}")
    ax.set_xticks(x)
    ax.set_xticklabels(month_labels)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_xlabel(f"Month ({year_label})")
    ax.set_ylabel("Rate")
    ax.set_title(
        "DAR — Deferred Action Rate (SII Context) — Monthly\n"
        "Calls recorded as FCR=1 that generated a repeat contact in the 31–60 day window.\n"
        "These are latent failures invisible to the standard 30-day FCR audit.",
        fontweight="bold"
    )
    ax.legend(loc="upper right")
    clean_ax(ax)
    plt.tight_layout()
    save_fig(fig, "l05a_dar_sii_monthly.png")

    # ── L05b: DAR-Behavioral monthly — documentation accuracy ─────────────────
    # Also overlay FCR for direct comparison
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(x, dar_beh["dar_behavioral"].tolist(), "o-", color=C_TEAL, linewidth=2.2,
            markersize=5, label="DAR-Behavioral: Documentation Accuracy Rate")
    ax.plot(x, df.groupby("month")["resolution_flag"].mean().reindex(months).tolist(),
            "s--", color=C_BLUE, linewidth=1.8, markersize=4, alpha=0.75,
            label="FCR (system-recorded, legacy)")
    ax.fill_between(x, dar_beh["dar_behavioral"].tolist(),
                    df.groupby("month")["resolution_flag"].mean().reindex(months).tolist(),
                    alpha=0.10, color=C_RED, label="Gap (FCR overclaim)")
    ax.set_xticks(x)
    ax.set_xticklabels(month_labels)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_xlabel(f"Month ({year_label})")
    ax.set_ylabel("Rate")
    ax.set_title(
        "DAR — Documentation Accuracy Rate (Behavioral Context) vs Legacy FCR\n"
        "Shaded area = calls where rep recorded FCR=1 but true_resolution=0.\n"
        f"Legacy FCR avg: {overall_fcr:.1%}  |  DAR-Behavioral avg: {overall_dar_beh:.1%}",
        fontweight="bold"
    )
    ax.legend(loc="lower left")
    clean_ax(ax)
    plt.tight_layout()
    save_fig(fig, "l05b_dar_behavioral_vs_fcr.png")

    # ── L05c: DAR-SII by call type — where latent failures concentrate ─────────
    resolved_df = df[df["resolution_flag"] == 1].copy()
    dar_by_type = resolved_df.groupby("call_type").agg(
        dar_sii = ("repeat_contact_31_60d", "mean"),
        n       = ("call_id", "count"),
    ).reset_index().sort_values("dar_sii", ascending=False)

    top_types = dar_by_type.head(10)
    colors = [C_RED if r > overall_dar_sii * 1.25
              else C_ORANGE if r > overall_dar_sii
              else C_GREEN
              for r in top_types["dar_sii"]]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(top_types["call_type"].tolist(), top_types["dar_sii"].tolist(),
            color=colors, edgecolor="white", height=0.6)
    ax.axvline(overall_dar_sii, color=C_DARK, linestyle="--", linewidth=1.2,
               label=f"Avg DAR-SII: {overall_dar_sii:.1%}")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax.set_xlabel("Deferred Action Rate (31–60 day repeat among resolved calls)")
    ax.set_title(
        "DAR-SII by Call Type\n"
        "Call types where system-resolved calls most frequently produce delayed repeat contacts.\n"
        "Red = >25% above avg. These are the high-gaming-risk categories.",
        fontweight="bold"
    )
    ax.legend(fontsize=9)
    clean_ax(ax)
    plt.tight_layout()
    save_fig(fig, "l05c_dar_sii_by_call_type.png")

    # ── L05d: DAR-Behavioral by team — documentation accuracy per team ─────────
    team_dar = df.groupby("team").agg(
        dar_behavioral = ("dar_match" if "dar_match" in df.columns
                          else lambda x: x,  # fallback
                          "mean") if "dar_match" in df.columns else ("resolution_flag", "mean"),
        fcr            = ("resolution_flag", "mean"),
        n              = ("call_id", "count"),
    ).reset_index()

    # Compute dar_match using dar_signal directly (passes through sanitizer untouched)
    if "dar_signal" in df.columns:
        df["dar_match"] = df["dar_signal"].astype(int)
    else:
        df["dar_match"] = (df["resolution_flag"].astype(int) == df["true_resolution"].astype(int)).astype(int)
    team_dar = df.groupby("team").agg(
        dar_behavioral = ("dar_match", "mean"),
        fcr            = ("resolution_flag", "mean"),
        n              = ("call_id", "count"),
    ).reset_index().sort_values("dar_behavioral", ascending=True)

    team_dar["gap"] = team_dar["fcr"] - team_dar["dar_behavioral"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    dar_colors = [C_RED if r < overall_dar_beh * 0.97
                  else C_ORANGE if r < overall_dar_beh
                  else C_GREEN
                  for r in team_dar["dar_behavioral"]]
    ax1.barh(team_dar["team"].tolist(), team_dar["dar_behavioral"].tolist(),
             color=dar_colors, edgecolor="white", height=0.6)
    ax1.axvline(overall_dar_beh, color=C_DARK, linestyle="--", linewidth=1.2,
                label=f"Avg DAR: {overall_dar_beh:.1%}")
    ax1.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax1.set_title("DAR-Behavioral by Team\n(documentation accuracy: flag matches true outcome)",
                  fontweight="bold")
    ax1.legend(fontsize=9)
    clean_ax(ax1)

    gap_colors = [C_RED if g > 0.05 else C_ORANGE if g > 0.02 else C_GREEN
                  for g in team_dar["gap"]]
    ax2.barh(team_dar["team"].tolist(), team_dar["gap"].tolist(),
             color=gap_colors, edgecolor="white", height=0.6)
    ax2.axvline(0, color=C_DARK, linewidth=1.0)
    ax2.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1))
    ax2.set_xlabel("FCR overclaim gap (FCR − DAR-Behavioral)")
    ax2.set_title("FCR Overclaim Gap by Team\n"
                  "(how much higher FCR is vs documented accuracy — the gaming delta)",
                  fontweight="bold")
    clean_ax(ax2)

    plt.suptitle("Documentation Accuracy Rate by Team — Behavioral Governance Lens",
                 fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    save_fig(fig, "l05d_dar_behavioral_by_team.png", bbox="tight")

    # ── Summary stats ──────────────────────────────────────────────────────────
    # True FCR: ground truth resolution rate
    true_fcr = df["true_resolution"].mean()

    # Gaming delta: DAR-Behavioral minus FCR.
    # In governance world DAR-Behavioral > FCR = documentation is MORE honest
    # than the proxy suggests — reps are accurately recording both successes
    # and failures. Positive = doc accuracy premium.
    gaming_delta = overall_dar_beh - overall_fcr

    # Trust delta: mean per-call trust change
    trust_delta_mean = df["trust_delta"].mean() if "trust_delta" in df.columns else None

    # Burnout: rep_burnout_level is a per-call SNAPSHOT that accumulates
    # across the year — averaging all 121k rows overweights December.
    # Correct measure: take the LAST snapshot per rep (end-of-year state),
    # then average across the workforce. This gives the annual workforce mean.
    if "rep_burnout_level" in df.columns and "rep_id" in df.columns:
        burnout_mean = (
            df.sort_values("call_date")
              .groupby("rep_id")["rep_burnout_level"]
              .last()
              .mean()
        )
    else:
        burnout_mean = None

    latent_failures_pct = overall_dar_sii

    print(f"  DAR-SII (latent failure rate):      {latent_failures_pct:.1%}")
    print(f"  DAR-Behavioral (doc accuracy):       {overall_dar_beh:.1%}")
    print(f"  Legacy FCR:                          {overall_fcr:.1%}")
    print(f"  True FCR (ground truth):             {true_fcr:.1%}")
    if trust_delta_mean is not None:
        print(f"  Avg Trust Delta:                     {trust_delta_mean:+.4f}")
    if burnout_mean is not None:
        print(f"  Avg Rep Burnout (workforce year-end):{burnout_mean:.3f}")
    print(f"  Doc accuracy premium (DAR − FCR):    {gaming_delta:+.1%}")
    print(f"  Implied gamed calls/year (est):      {int((overall_fcr - overall_dar_beh) * len(df)):,}")
    print("  Figures saved: l05a, l05b, l05c, l05d")

    return {
        "dar_sii":          latent_failures_pct,
        "dar_behavioral":   overall_dar_beh,
        "fcr_legacy":       overall_fcr,
        "true_fcr":         true_fcr,
        "gaming_delta":     gaming_delta,       # positive = DAR > FCR = doc accuracy premium
        "trust_delta_mean": trust_delta_mean,
        "burnout_mean":     burnout_mean,
        "dar_sii_monthly":  dar_sii,
        "dar_beh_monthly":  dar_beh,
        "team_dar":         team_dar,
    }

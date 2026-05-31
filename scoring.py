"""
================================  YOUR KNOB  ================================
Turns a catalyst (+ optional cheapness) into a 0-100 rank that decides what
hits your phone. The deep-research found NO verified practitioner recipe, so
these weights are a SENSIBLE DEFAULT to BACKTEST, not gospel. Tune freely —
this single file shapes the whole app's behavior.

  - Bigger insider clusters / officer (CEO/CFO) buys  -> higher
  - Bigger contracts                                  -> higher
  - Congress is weak/experimental                     -> low base
  - CHEAPNESS_WEIGHT controls how hard the "undervalued" gate pulls the score
    (only active when an FMP_API_KEY is set; that's what makes it "Both").
============================================================================
"""
import math

import config
import fmp_value

# ---- weights (edit me) ----
W_INSIDER_BASE = 50          # an insider cluster is the strongest signal
W_PER_EXTRA_INSIDER = 12     # each insider beyond the first
W_OFFICER_BONUS = 10         # a CEO/CFO buy outranks a director buy
W_CONTRACT_BASE = 35         # a fresh federal award
W_CONTRACT_PER_100M = 5      # scale with award size (per $100M)
CHEAPNESS_WEIGHT = 0.5       # 0 = ignore valuation, 1 = valuation dominates


def score_insider_cluster(n_insiders, total_value, has_officer):
    s = W_INSIDER_BASE + (n_insiders - 1) * W_PER_EXTRA_INSIDER
    if has_officer:
        s += W_OFFICER_BONUS
    return float(min(s, 100))


def score_contract(amount_usd):
    # log scale so a $48B award doesn't trivially tie with a $1B one; caps BELOW the insider max (100)
    if amount_usd <= 0:
        return float(W_CONTRACT_BASE)
    s = W_CONTRACT_BASE + math.log10(max(amount_usd, 1e6) / 1e6) * 12
    return float(min(s, 85))


def apply_cheapness(base, ticker):
    """Multiply by a 0..1 value grade (cheap=1). Returns (final_score, grade_or_None)."""
    grade = fmp_value.cheapness_0_1(ticker)        # None when no FMP key / lookup fails
    if grade is None:
        return base, None
    factor = (1 - CHEAPNESS_WEIGHT) + CHEAPNESS_WEIGHT * grade
    return round(base * factor, 1), grade


# ---- "learn while trading" notes (edit the wording to teach yourself) ----
def why_insider(c, sector, cheap):
    note = (f"{c['n']} insiders put personal cash into {c['ticker']} ({sector}). "
            f"Clustered open-market buys are the strongest documented edge — "
            f"insiders sell for many reasons but buy for only one.")
    if cheap is not None:
        tag = "cheap" if cheap > 0.6 else "fair" if cheap > 0.4 else "rich"
        note += f" Valuation gate: {tag} ({cheap:.2f})."
    return note


def why_contract(a, sector, cheap):
    return (f"${a['amount']/1e6:.0f}M is the award's LIFETIME total to {a['recipient'][:40]} ({sector}) "
            f"— USAspending lists award vehicles, not just fresh signings, so VERIFY recency before acting. "
            f"(v2 will use SEC 8-K 'material agreement' filings for true fresh-deal catalysts.)")

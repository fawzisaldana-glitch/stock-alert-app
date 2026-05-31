"""
Config for the AI Hedge Fund layer — everything tunable lives here so the whole thing is
white-labelable / sellable: swap the watchlist, personas, weights, cadence, or LLM endpoint
without touching engine code.

ORG CHART (see committee.py):
  CEO (schedules + sets directive from regime + lessons)
    -> 5 investor agents (deterministic persona scores; optional free-LLM narration)
      -> CIO (deterministic, regime-weighted aggregation) -> Top 5 Day + Top 5 Month
        -> QA gate (sanity check before publish)
          -> Learning agent (tracks outcomes -> lessons.json -> back to CEO)
"""

# ---- cadence (CEO governs which sections run on which trigger) ----
# Ship at 1x/day; flip RUNS_PER_DAY to 2 later. Per-section flags let the CEO refresh
# fast-moving sections twice while leaving slow ones (13F, monthly board) once.
CADENCE = {
    "runs_per_day": 1,
    "sections": {
        "macro":        {"per_day": 2},   # regime can shift intraday
        "alerts":       {"per_day": 2},   # insider/contract filings land through the day
        "valuations":   {"per_day": 1},
        "billionaires": {"per_day": 1},   # 13F is quarterly — daily is already generous
        "politicians":  {"per_day": 1},
        "committee":    {"per_day": 1},   # the board convenes once; 2nd pass optional later
        "top_month":    {"per_day": 1},
    },
}

# ---- the investment committee: 5 famous investors, each a documented STYLE ----
# weights are over the candidate FEATURE VECTOR (all features normalized 0..1):
#   catalyst  = alert score / 100        (fresh smart-money catalyst strength)
#   cheap     = valuation cheapness 0..1  (1 = cheap)
#   mos       = margin of safety, mapped 0..1 (0.5 = fair)
#   insider   = 1 if insider-cluster signal
#   contract  = 1 if gov-contract signal
# weights per persona sum to ~1.0; the CIO then regime-weights ACROSS personas.
FEATURES = ["catalyst", "cheap", "mos", "insider", "contract"]

PERSONAS = {
    "Buffett": {
        "full": "Warren Buffett",
        "style": "Quality businesses at fair prices, long horizon, margin of safety.",
        "weights": {"catalyst": 0.05, "cheap": 0.40, "mos": 0.35, "insider": 0.15, "contract": 0.05},
    },
    "Munger": {
        "full": "Charlie Munger",
        "style": "Concentrated, high-quality, patient. A few great bets over many mediocre ones.",
        "weights": {"catalyst": 0.05, "cheap": 0.45, "mos": 0.30, "insider": 0.15, "contract": 0.05},
    },
    "Ackman": {
        "full": "Bill Ackman",
        "style": "Concentrated, catalyst-driven value; activist conviction.",
        "weights": {"catalyst": 0.30, "cheap": 0.25, "mos": 0.20, "insider": 0.15, "contract": 0.10},
    },
    "Cohen": {
        "full": "Steve Cohen",
        "style": "Information edge + momentum; trades the catalyst and the insiders.",
        "weights": {"catalyst": 0.35, "cheap": 0.05, "mos": 0.05, "insider": 0.40, "contract": 0.15},
    },
    "Dalio": {
        "full": "Ray Dalio",
        "style": "Macro regime + diversification; balance risk across signals.",
        "weights": {"catalyst": 0.20, "cheap": 0.20, "mos": 0.20, "insider": 0.20, "contract": 0.20},
    },
}

# CIO regime weighting ACROSS personas. The CEO picks a posture from the macro reds count;
# defensive lifts value/quality + Dalio, trims Cohen's momentum.
REGIME_WEIGHTS = {
    # posture: per-persona multiplier
    "defensive":    {"Buffett": 1.3, "Munger": 1.3, "Ackman": 1.0, "Cohen": 0.5, "Dalio": 1.2},
    "neutral":      {"Buffett": 1.0, "Munger": 1.0, "Ackman": 1.0, "Cohen": 1.0, "Dalio": 1.0},
    "constructive": {"Buffett": 0.9, "Munger": 0.9, "Ackman": 1.1, "Cohen": 1.3, "Dalio": 0.9},
}

# CEO maps macro -> posture
def posture_for(reds):
    if reds is None:
        return "neutral"
    return "defensive" if reds >= 2 else "constructive" if reds == 0 else "neutral"

TOP_N = 5                      # Top 5 of the day / month
MONTH_WINDOW_DAYS = 30         # rolling window for "of the month"

# QA gate thresholds
QA = {
    "min_day_picks": 1,        # must produce at least this many day picks (else hold)
    "require_reasoning": True, # every pick needs a non-empty 'why'
    "score_range": (0.0, 100.0),
}

# ---- free LLM narration (optional; deterministic scores stand alone if this is down) ----
FCC = {
    "enabled": True,
    "base_url": "http://localhost:8082/v1",   # FCC proxy (free: Nemotron/Gemini)
    "model": "claude-3-5-sonnet-20241022",     # FCC maps this to a free backend
    "timeout": 30,
}

# ---- paths (state for the learning loop) ----
PICKS_JSON = "app/picks.json"
BACKTEST_JSON = "app/backtest.json"
PICKS_HISTORY = "fund_state/picks_history.jsonl"   # every pick logged with as-of date + entry px
LESSONS_JSON = "fund_state/lessons.json"           # learning agent output, read by the CEO

BENCHMARK = "SPY"              # what the backtest compares against

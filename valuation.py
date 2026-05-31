"""
Unified valuation engine — three-factor cheapness + lite DCF.

DATA SOURCE (rewritten): yfinance is PRIMARY for all numbers — it covers nearly every
ticker for free with no symbol gating, unlike FMP's free tier (which 402s on everything
but a sample mega-cap set). FMP is used ONLY for the peer LIST (its /stock-peers endpoint
is free for all symbols); yfinance has no peer-list API. With no FMP key the comps factor
simply degrades — value + DCF still work. So the cheapness gate now works key-free.

Returns per ticker:
  cheapness          0..1 (1=cheap; same contract scoring.py uses)
  factors            dict of (name -> 0..1) — what made up the cheapness
  intrinsic_value    DCF per-share estimate (None if model failed)
  market_price       current
  margin_of_safety   (intrinsic - market) / market, or None
  peer_pct           dict of multiple -> percentile vs peers (lower=cheaper)
  confidence         "low" | "medium" | "high" — based on how many factors fired
  source             "yfinance" | "cache"
  notes              list of human-readable caveats

THREE INDEPENDENT FACTORS (each can fail without taking the others down; the final
cheapness re-weights over whichever returned):
  * value_score      — absolute valuation from P/E + P/B vs reasonable large-cap bands.
                       Sector-agnostic bands, so treat as a coarse lens (comps is the
                       sector-relative one). Replaces the old FMP ratings-snapshot factor.
  * comps_percentile — peer-relative ranking of P/E, EV/EBITDA, EV/Rev (peers' multiples
                       also from yfinance). 1 = cheaper than all peers.
  * dcf_margin       — normalized (intrinsic - price)/price from a lite 5y DCF.

MODEL: WACC = CAPM (10y Treasury risk-free + 5% ERP × beta), 70/30 equity/debt cap
structure, after-tax cost of debt = (rf + 2% spread)(1 - 21%). Terminal g = 2.5%.
File cache (cache/valuation_<TICKER>_<DATE>.json) keeps reruns same-day free.
"""
import datetime
import json
import os
import socket
import time

import config

# yfinance is already a project dependency (used by politicians.py). Import lazily-safe.
try:
    import yfinance as yf
except Exception:
    yf = None

# FMP only for the peer list (free for all symbols). Optional.
import fetch

_CACHE_DIR = "cache"
_INFO_MEMO = {}          # module-level memo of yfinance .info within a single run
_RISK_FREE_MEMO = {}     # cache the 10y treasury once per process

# --- Model assumptions (tune freely; documented in output JSON) ---
DCF_HORIZON_YEARS = 5
TERMINAL_GROWTH = 0.025          # long-run US GDP
EQUITY_RISK_PREMIUM = 0.05       # Damodaran-style conservative US ERP
CREDIT_SPREAD = 0.02             # over risk-free for cost of debt
TAX_RATE = 0.21                  # US federal
EQUITY_WEIGHT = 0.70             # assumed cap structure (equity/debt)
FCF_GROWTH_CLIP = (-0.05, 0.12)  # year-1 growth cap. Trailing FCF growth is noisy/cyclical;
                                 # a high ceiling compounded 5y explodes intrinsic. Faded toward
                                 # terminal-g over the horizon (two-stage DCF) — see _factor_dcf.
MARGIN_SAFETY_CLIP = 0.50        # clip ±50% for normalization
DCF_PLAUSIBLE_MARGIN = 1.5       # if |intrinsic-price|/price exceeds this, the lite DCF is
                                 # unreliable (small/illiquid/cyclical FCF) — suppress the shown
                                 # intrinsic AND drop the factor, so the name leans on value_score
DEFAULT_RISK_FREE = 0.043        # fallback if ^TNX lookup fails (~current 10y)
BETA_FLOOR, BETA_CEIL = 0.7, 2.5 # clamp suspicious betas. Floor 0.7 (not 0.3) so a defensive/odd
                                 # Yahoo beta can't drive WACC implausibly low (NOC came back -0.11)

# value_score bands (large-cap defaults; sector-agnostic — coarse on purpose)
PE_CHEAP, PE_RICH = 15.0, 35.0
PB_CHEAP, PB_RICH = 1.5, 6.0

VALUE_WEIGHT = 0.20
COMPS_WEIGHT = 0.40
DCF_WEIGHT = 0.40
MAX_PEERS = 6                    # cap peer .info fetches (yfinance is slow/rate-limited)


def _num(x):
    """Coerce to float or None (yfinance sometimes returns 'Infinity'/None/NaN)."""
    try:
        f = float(x)
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _yf_info(ticker):
    """Memoized yfinance .info dict (empty on failure)."""
    if ticker in _INFO_MEMO:
        return _INFO_MEMO[ticker]
    info = {}
    if yf is not None:
        try:
            socket.setdefaulttimeout(30)
            info = yf.Ticker(ticker).info or {}
        except Exception:
            info = {}
    _INFO_MEMO[ticker] = info
    return info


def _yf_fcf_history(ticker):
    """Most-recent-first list of annual Free Cash Flow values (floats). Empty on failure."""
    if yf is None:
        return []
    try:
        cf = yf.Ticker(ticker).cashflow
        if cf is None or not hasattr(cf, "index"):
            return []
        rows = [r for r in cf.index if "Free Cash Flow" in str(r)]
        if not rows:
            return []
        vals = [_num(x) for x in cf.loc[rows[0]].values]
        return [v for v in vals if v is not None]
    except Exception:
        return []


def _risk_free_10y():
    """10y Treasury yield as a decimal, from ^TNX. Cached; defaults on failure."""
    if "rf" in _RISK_FREE_MEMO:
        return _RISK_FREE_MEMO["rf"]
    rf = DEFAULT_RISK_FREE
    if yf is not None:
        try:
            socket.setdefaulttimeout(20)
            fi = yf.Ticker("^TNX").fast_info
            last = _num(getattr(fi, "last_price", None)) or _num(fi.get("lastPrice") if hasattr(fi, "get") else None)
            if last:
                # ^TNX is quoted in percent (e.g. 4.25 = 4.25%); some feeds use x10 (42.5).
                cand = last / 100.0 if last > 1 else last
                if cand > 0.2:            # got the x10 form
                    cand = cand / 10.0
                if 0.005 <= cand <= 0.10:  # sanity band
                    rf = cand
        except Exception:
            pass
    _RISK_FREE_MEMO["rf"] = rf
    return rf


def _cache_path(ticker):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"valuation_{ticker.upper()}_{datetime.date.today().isoformat()}.json")


def _load_cache(ticker):
    p = _cache_path(ticker)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            d["source"] = "cache"
            return d
        except Exception:
            return None
    return None


def _save_cache(ticker, payload):
    try:
        with open(_cache_path(ticker), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def _multiples(info):
    """Pull the three comps multiples from a yfinance .info dict."""
    return dict(
        pe=_num(info.get("trailingPE")),
        ev_ebitda=_num(info.get("enterpriseToEbitda")),
        ev_rev=_num(info.get("enterpriseToRevenue")),
    )


# --------------------- factor 1: absolute value (P/E + P/B bands) ---------------------
def _factor_value(info):
    pe = _num(info.get("trailingPE"))
    pb = _num(info.get("priceToBook"))
    scores = []
    if pe is not None and pe > 0:
        scores.append(max(0.0, min(1.0, (PE_RICH - pe) / (PE_RICH - PE_CHEAP))))
    if pb is not None and pb > 0:
        scores.append(max(0.0, min(1.0, (PB_RICH - pb) / (PB_RICH - PB_CHEAP))))
    if not scores:
        return None
    return sum(scores) / len(scores)


# --------------------- factor 2: comps (peer percentile ranking) ---------------------
def _peer_list(ticker):
    """Peer symbols from FMP /stock-peers, cached daily to disk so a transient FMP 429
    (or daily-cap) doesn't kill comps, and so we stop re-hammering FMP across a run."""
    cache_p = os.path.join(_CACHE_DIR, f"peerlist_{ticker.upper()}_{datetime.date.today().isoformat()}.json")
    if os.path.exists(cache_p):
        try:
            with open(cache_p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    peers = []
    if config.FMP_API_KEY:
        try:
            d = fetch.get_json(f"https://financialmodelingprep.com/stable/stock-peers?symbol={ticker}&apikey={config.FMP_API_KEY}")
            if isinstance(d, list):
                peers = [p.get("symbol") for p in d if p.get("symbol") and p.get("symbol") != ticker]
        except Exception:
            peers = []
    if peers:                              # only cache a real hit (don't cache the 429 empty)
        os.makedirs(_CACHE_DIR, exist_ok=True)
        try:
            with open(cache_p, "w", encoding="utf-8") as f:
                json.dump(peers, f)
        except Exception:
            pass
    return peers


def _factor_comps(ticker, my_metrics):
    """FMP gives the peer LIST (free, cached daily); yfinance gives each peer's multiples."""
    peers = _peer_list(ticker)[:MAX_PEERS]
    if len(peers) < 3:
        return None, None

    peer_metrics = []
    for pt in peers:
        info = _yf_info(pt)
        if info:
            peer_metrics.append(_multiples(info))
    if len(peer_metrics) < 3:
        return None, None

    def percentile(mine, peer_vals):
        vals = [v for v in peer_vals if isinstance(v, (int, float)) and v > 0]
        if mine is None or mine <= 0 or len(vals) < 3:
            return None
        return sum(1 for v in vals if v < mine) / len(vals)   # 0=cheaper than all peers

    pct = dict(
        pe=percentile(my_metrics.get("pe"), [p["pe"] for p in peer_metrics]),
        ev_ebitda=percentile(my_metrics.get("ev_ebitda"), [p["ev_ebitda"] for p in peer_metrics]),
        ev_rev=percentile(my_metrics.get("ev_rev"), [p["ev_rev"] for p in peer_metrics]),
    )
    valid = [v for v in pct.values() if v is not None]
    if not valid:
        return None, pct
    return 1 - (sum(valid) / len(valid)), pct


# --------------------- factor 3: lite DCF ---------------------
def _factor_dcf(info, fcf_hist, risk_free):
    """5y FCF projection, CAPM-WACC, Gordon terminal, equity bridge. Returns
    (intrinsic_per_share, margin_norm_0_1, notes)."""
    notes = []
    if len(fcf_hist) < 3:
        return None, None, ["dcf-skipped: <3y FCF history"]
    if fcf_hist[0] <= 0:
        return None, None, ["dcf-skipped: latest FCF not positive (lite DCF can't price money-losers)"]

    # Growth from trailing YoY (most-recent-first → reverse the ratio), clipped
    samples = [fcf_hist[i] / fcf_hist[i + 1] - 1 for i in range(len(fcf_hist) - 1) if fcf_hist[i + 1] > 0]
    if samples:
        g = max(FCF_GROWTH_CLIP[0], min(FCF_GROWTH_CLIP[1], sum(samples) / len(samples)))
    else:
        g = 0.0
        notes.append("dcf-growth: no clean YoY samples, used 0%")

    beta = _num(info.get("beta"))
    if beta is None or not (BETA_FLOOR <= beta <= BETA_CEIL):
        notes.append(f"dcf-beta: raw beta={beta} out of [{BETA_FLOOR},{BETA_CEIL}] → clamped/defaulted")
        beta = 1.0 if beta is None else max(BETA_FLOOR, min(BETA_CEIL, beta))
    cost_equity = risk_free + beta * EQUITY_RISK_PREMIUM
    cost_debt = (risk_free + CREDIT_SPREAD) * (1 - TAX_RATE)
    wacc = EQUITY_WEIGHT * cost_equity + (1 - EQUITY_WEIGHT) * cost_debt
    if wacc <= TERMINAL_GROWTH:
        wacc = TERMINAL_GROWTH + 0.02
        notes.append("dcf-wacc: clamped above terminal-g for stability")

    # Two-stage fade: year-1 growth = g0, decaying linearly to terminal-g by the final year.
    # Mature/cyclical firms don't sustain peak trailing growth — fading prevents the
    # compounding blow-up that made every defense name look 2-5x undervalued.
    pv_sum, last = 0.0, fcf_hist[0]
    for yr in range(1, DCF_HORIZON_YEARS + 1):
        g_t = g + (TERMINAL_GROWTH - g) * (yr - 1) / (DCF_HORIZON_YEARS - 1)
        last *= (1 + g_t)
        pv_sum += last / (1 + wacc) ** yr
    tv = last * (1 + TERMINAL_GROWTH) / (wacc - TERMINAL_GROWTH)
    enterprise_value = pv_sum + tv / (1 + wacc) ** DCF_HORIZON_YEARS

    shares = _num(info.get("sharesOutstanding"))
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    if not shares or not price:
        return None, None, notes + ["dcf-skipped: missing shares/price for equity bridge"]
    total_debt = _num(info.get("totalDebt")) or 0.0
    cash = _num(info.get("totalCash")) or 0.0
    net_debt = total_debt - cash
    intrinsic = (enterprise_value - net_debt) / shares
    margin = (intrinsic - price) / price
    if abs(margin) > DCF_PLAUSIBLE_MARGIN:
        notes.append(f"dcf-unreliable: |margin|={margin:+.0%} implausible (likely small/illiquid/cyclical "
                     f"FCF) → intrinsic suppressed & factor dropped; name leans on value_score")
        return None, None, notes
    margin_norm = (max(-MARGIN_SAFETY_CLIP, min(MARGIN_SAFETY_CLIP, margin)) + MARGIN_SAFETY_CLIP) / (2 * MARGIN_SAFETY_CLIP)
    notes.append(f"dcf: wacc={wacc:.2%}, g0={g:.2%}→termg, terminal_g={TERMINAL_GROWTH:.2%}, beta={beta:.2f}, "
                 f"net_debt=${net_debt/1e9:.1f}B")
    return round(intrinsic, 2), round(margin_norm, 3), notes


# --------------------- public entry point ---------------------
def valuation_for_ticker(ticker):
    """Full valuation dict for a ticker, or None only if yfinance is unavailable."""
    if not ticker or yf is None:
        return None
    ticker = ticker.upper().strip()

    cached = _load_cache(ticker)
    if cached:
        return cached

    notes = []
    out = dict(ticker=ticker, computed_at=time.time(), source="yfinance",
               cheapness=None, factors={}, intrinsic_value=None, market_price=None,
               margin_of_safety=None, peer_pct={}, confidence="low", notes=notes,
               assumptions=dict(horizon_yrs=DCF_HORIZON_YEARS, terminal_g=TERMINAL_GROWTH,
                                erp=EQUITY_RISK_PREMIUM, tax_rate=TAX_RATE, equity_weight=EQUITY_WEIGHT))

    info = _yf_info(ticker)
    if not info:
        notes.append("yfinance .info empty (delisted, bad ticker, or Yahoo throttle)")
        _save_cache(ticker, out)
        return out

    out["market_price"] = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    my_metrics = _multiples(info)

    f_value = _factor_value(info)
    if f_value is not None:
        out["factors"]["value_score"] = round(f_value, 3)

    f_comps, comps_pct = _factor_comps(ticker, my_metrics)
    if comps_pct:
        out["peer_pct"] = {k: (round(v, 3) if v is not None else None) for k, v in comps_pct.items()}
    if f_comps is not None:
        out["factors"]["comps_percentile"] = round(f_comps, 3)

    intrinsic, dcf_grade, dcf_notes = _factor_dcf(info, _yf_fcf_history(ticker), _risk_free_10y())
    notes.extend(dcf_notes or [])
    out["intrinsic_value"] = intrinsic
    if intrinsic is not None and out["market_price"]:
        out["margin_of_safety"] = round((intrinsic - out["market_price"]) / out["market_price"], 3)
    if dcf_grade is not None:
        out["factors"]["dcf_margin"] = round(dcf_grade, 3)

    weights = dict(value_score=VALUE_WEIGHT, comps_percentile=COMPS_WEIGHT, dcf_margin=DCF_WEIGHT)
    avail = {n: (v, weights[n]) for n, v in out["factors"].items()}
    if avail:
        wsum = sum(w for _, w in avail.values())
        out["cheapness"] = round(sum(v * w for v, w in avail.values()) / wsum, 3)
        out["confidence"] = ["low", "medium", "high"][min(2, len(avail) - 1)]

    out["my_metrics"] = {k: (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in my_metrics.items()}
    _save_cache(ticker, out)
    return out


# --------------------- backward-compat shim ---------------------
def cheapness_0_1(ticker):
    """Old API kept for scoring.py — returns just the 0..1 grade."""
    v = valuation_for_ticker(ticker)
    return v["cheapness"] if v else None


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tk = sys.argv[1] if len(sys.argv) > 1 else "NOC"
    print(json.dumps(valuation_for_ticker(tk), indent=2, default=str))

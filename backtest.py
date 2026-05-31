#!/usr/bin/env python3
"""
Blind-ish backtest for the signal/pick quality — the video's idea, done honestly.

TWO separate measures (never conflated):
  1. FORWARD (the real blind test): read fund_state/picks_history.jsonl, and for picks old
     enough to judge, measure their return from the LOCKED pick date to now vs SPY over the
     same window. No lookahead — picks were committed before the future existed. Cold start now,
     matures as history accumulates.
  2. RETROSPECTIVE (labeled, selection-biased): for the CURRENT alert tickers, trailing-90d
     return vs SPY. Gives an immediate read but is NOT a forward test (we're looking at names
     flagged today and grading their past) — surfaced with that caveat so it can't mislead.

Output: app/backtest.json
"""
import datetime
import json
import os
import sys

import fund_config as cfg

LOOKBACK_DAYS = 90
MIN_AGE_DAYS = 14          # a forward pick must be this old before we grade it


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _series(tk, start):
    import yfinance as yf
    try:
        h = yf.download(tk, start=start, auto_adjust=True, progress=False)
        if hasattr(h.columns, "get_level_values"):
            h.columns = h.columns.get_level_values(0)
        s = h["Close"].dropna() if "Close" in h.columns else None
        return s if (s is not None and len(s)) else None
    except Exception:
        return None


def _ret(s, on_or_after):
    """Return from first close on/after a date to the last close."""
    if s is None or not len(s):
        return None
    after = s[[d.date() >= on_or_after for d in s.index]]
    if not len(after) or float(after.iloc[0]) <= 0:
        return None
    return float(s.iloc[-1]) / float(after.iloc[0]) - 1


def forward_test():
    hist = []
    try:
        with open(cfg.PICKS_HISTORY, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    hist.append(json.loads(line))
    except Exception:
        hist = []
    cutoff = (datetime.date.today() - datetime.timedelta(days=MIN_AGE_DAYS)).isoformat()
    aged = [h for h in hist if h.get("date", "9999") <= cutoff and h.get("entry_price")]
    if not aged:
        return dict(n=0, note=f"Cold start — picks need {MIN_AGE_DAYS}+ days to grade. "
                              f"{len(hist)} pick(s) logged so far; the forward test fills in over the coming weeks.")
    oldest = min(h["date"] for h in aged)
    spy = _series(cfg.BENCHMARK, oldest)
    rows, beats = [], 0
    for h in aged:
        s = _series(h["ticker"], h["date"])
        d = datetime.date.fromisoformat(h["date"])
        r = _ret(s, d)
        spy_r = _ret(spy, d)
        if r is None or spy_r is None:
            continue
        beat = r > spy_r
        beats += beat
        rows.append(dict(ticker=h["ticker"], date=h["date"], ret=round(r * 100, 1),
                         spy=round(spy_r * 100, 1), beat=beat))
    if not rows:
        return dict(n=0, note="Aged picks found but price history unavailable to grade them yet.")
    avg = sum(x["ret"] for x in rows) / len(rows)
    avg_spy = sum(x["spy"] for x in rows) / len(rows)
    return dict(n=len(rows), avg_return=round(avg, 1), spy_return=round(avg_spy, 1),
                excess=round(avg - avg_spy, 1), hit_rate=round(beats / len(rows) * 100),
                beat_spy=avg > avg_spy, picks=rows,
                note="Forward test: picks graded from their LOCKED date to now vs SPY. No lookahead.")


def retrospective():
    alerts = _load("app/alerts.json", {}).get("alerts", [])
    tickers = sorted({a.get("ticker") for a in alerts if a.get("ticker")})
    if not tickers:
        return dict(n=0, note="no current signals")
    start = (datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS + 5)).isoformat()
    anchor = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
    spy = _series(cfg.BENCHMARK, start)
    spy_r = _ret(spy, anchor)
    rets = []
    for tk in tickers:
        r = _ret(_series(tk, start), anchor)
        if r is not None:
            rets.append(r)
    if not rets:
        return dict(n=0, note="price history unavailable")
    avg = sum(rets) / len(rets)
    return dict(window_days=LOOKBACK_DAYS, n=len(rets), avg_return=round(avg * 100, 1),
                spy_return=round((spy_r or 0) * 100, 1),
                excess=round((avg - (spy_r or 0)) * 100, 1),
                note="RETROSPECTIVE & selection-biased: trailing return of names flagged TODAY vs SPY. "
                     "Not a forward test — use only as a rough signal-quality smell test.")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import time
    fwd = forward_test()
    retro = retrospective()
    payload = dict(updated=time.time(), benchmark=cfg.BENCHMARK, forward=fwd, retrospective=retro)
    os.makedirs("app", exist_ok=True)
    with open(cfg.BACKTEST_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("FORWARD:", fwd.get("note", ""))
    if fwd.get("n"):
        print(f"  picks avg {fwd['avg_return']:+.1f}% vs SPY {fwd['spy_return']:+.1f}% "
              f"(excess {fwd['excess']:+.1f}, hit {fwd['hit_rate']}%, n={fwd['n']})")
    print("RETROSPECTIVE:", f"n={retro.get('n')}, avg {retro.get('avg_return')}% vs SPY {retro.get('spy_return')}% "
          f"(excess {retro.get('excess')})")
    print(f"saved {cfg.BACKTEST_JSON}")


if __name__ == "__main__":
    main()

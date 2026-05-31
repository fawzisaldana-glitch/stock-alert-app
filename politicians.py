#!/usr/bin/env python3
"""
Politician (Congress) trades — INFORMATIONAL ONLY. NOT a buy signal.
Data source order: (1) Capitol Trades public feed (no key); (2) FMP REST if FMP_API_KEY set.
Computes an APPROXIMATE per-politician win-rate + avg return from the disclosed
TRANSACTION date to today (yfinance free price data).

HONEST CAVEATS (shown in-app): disclosed amounts are RANGES; returns are from the trade
date (public disclosure lags weeks-to-months); samples are small; ignores sells/timing/
sizing. "Fun to know what politicians own", not an edge (research ranked congress weak).
"""
import datetime
import json
import os
import sys
import time
from collections import defaultdict

import config
import fetch

LOOKBACK_DAYS = 365
MAX_TRADES = 150


def from_capitol_trades(pages=3):
    out = []
    for p in range(1, pages + 1):
        try:
            d = fetch.get_json(f"https://bff.capitoltrades.com/trades?per_page=100&page={p}&sortBy=-txDate")
        except Exception as e:
            print("  [capitoltrades] failed:", type(e).__name__)
            break
        rows = d.get("data") or []
        if not rows:
            break
        for r in rows:
            pol = r.get("politician") or {}
            iss = r.get("issuer") or {}
            tk = (iss.get("issuerTicker") or "").split(":")[0].strip().upper()
            name = f"{pol.get('firstName', '')} {pol.get('lastName', '')}".strip() or "Unknown"
            out.append(dict(ticker=tk, name=name, type=(r.get("txType") or "").lower(),
                            date=r.get("txDate") or "", chamber=pol.get("chamber") or "",
                            amount=r.get("value") or r.get("size") or ""))
    return out


def from_fmp():
    # NOTE: FMP's free/Starter tier 402's at limit>25 AND page>0 on these endpoints.
    # Both dims are gated independently — so 25 records/chamber is the ceiling, no pagination escape.
    # 25+25=50 trades is enough since the UI caps at 40 recent + 15 leaders.
    if not config.FMP_API_KEY:
        return []
    out = []
    for ep in ("senate-latest", "house-latest"):
        try:
            d = fetch.get_json(f"https://financialmodelingprep.com/stable/{ep}?page=0&limit=25&apikey={config.FMP_API_KEY}")
        except Exception as e:
            print(f"  [fmp {ep}] failed: {type(e).__name__} {str(e)[:120]}")
            continue
        for r in (d if isinstance(d, list) else []):
            out.append(dict(ticker=(r.get("symbol") or "").upper().strip(),
                            name=f"{r.get('firstName','')} {r.get('lastName','')}".strip() or r.get("office", "?"),
                            type=(r.get("type") or "").lower(), date=r.get("transactionDate") or "",
                            chamber="Senate" if "senate" in ep else "House", amount=r.get("amount") or ""))
    return out


def parse_date(s):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime((s or "")[:10].strip(), fmt).date()
        except ValueError:
            continue
    return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    raw = from_capitol_trades()
    src = "Capitol Trades"
    if not raw:
        raw = from_fmp()
        src = "FMP"
    raw = [r for r in raw if r["ticker"] and r["ticker"] not in ("--", "N/A")]
    print(f"loaded {len(raw)} trades from {src}")
    if not raw:
        print("no source returned data — set FMP_API_KEY in .env (free tier covers congress) to enable this tab")
        return

    cutoff = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
    buys = []
    for r in raw:
        d = parse_date(r["date"])
        if d and d >= cutoff and r["type"].startswith(("buy", "purchase")):
            r["d"] = d
            buys.append(r)
    buys.sort(key=lambda x: x["d"], reverse=True)
    buys = buys[:MAX_TRADES]
    print(f"{len(buys)} purchases in last {LOOKBACK_DAYS}d")
    if not buys:
        return

    import yfinance as yf
    px = {}
    for tk in sorted(set(b["ticker"] for b in buys)):
        try:
            h = yf.download(tk, start=str(cutoff), auto_adjust=True, progress=False)
            if hasattr(h.columns, "get_level_values"):
                h.columns = h.columns.get_level_values(0)
            px[tk] = h["Close"].dropna() if "Close" in h.columns and len(h) else None
        except Exception:
            px[tk] = None

    for b in buys:
        b["ret"] = None
        s = px.get(b["ticker"])
        if s is not None and len(s):
            after = s[[dt.date() >= b["d"] for dt in s.index]]
            if len(after) and float(after.iloc[0]) > 0:
                b["ret"] = round((float(s.iloc[-1]) / float(after.iloc[0]) - 1) * 100, 1)

    byp = defaultdict(list)
    for b in buys:
        if b["ret"] is not None:
            byp[b["name"]].append(b["ret"])
    stats = sorted([dict(name=n, trades=len(rs),
                         win_rate=round(sum(1 for r in rs if r > 0) / len(rs) * 100),
                         avg_return=round(sum(rs) / len(rs), 1)) for n, rs in byp.items()],
                   key=lambda x: -x["trades"])

    print("\nMOST ACTIVE (approx win-rate / avg return since trade date — INFORMATIONAL):")
    for s in stats[:10]:
        print(f"  {s['name'][:26]:26s} {s['trades']:2d} buys | win {s['win_rate']:3d}% | avg {s['avg_return']:+6.1f}%")

    payload = dict(updated=time.time(), source=src,
                   disclaimer="Informational only - NOT a buy signal. Returns approximate (from trade "
                              "date), amounts are ranges, congress is a weak/lagged signal.",
                   leaders=stats[:15],
                   recent=[dict(name=b["name"], ticker=b["ticker"], date=str(b["d"]),
                                chamber=b["chamber"], ret=b["ret"]) for b in buys[:40]])
    os.makedirs("app", exist_ok=True)
    with open("app/politicians.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\nsaved app/politicians.json")


if __name__ == "__main__":
    main()

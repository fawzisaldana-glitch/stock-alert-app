#!/usr/bin/env python3
"""
Politician (Congress) trades — INFORMATIONAL ONLY. NOT a buy signal.

DATA SOURCE NOTE (2026): every free, no-auth, *current* comprehensive feed has died —
House Stock Watcher S3 is 403, Senate Stock Watcher's GitHub data froze at Dec 2020,
Capitol Trades' API 503s. The only working free source is FMP's senate-latest / house-latest
(~25 each = ~50 recent trades, ~20-30 politicians). So this is RECENT disclosures, not the
full 100+ roster. The UI is built to accept a richer feed later — swap `fetch_trades()` only.

Output (app/politicians.json), aggregated PER POLITICIAN so the UI can drill in:
  politicians: [ {name, chamber, trades, buys, last_date, avg_return, win_rate,
                  items:[{ticker, company, type, date, amount, ret, link}]} ]
Returns are approximate (disclosed TRANSACTION date → today, yfinance), for buys only.
"""
import datetime
import json
import os
import sys
import time
from collections import defaultdict

import config
import fetch

LOOKBACK_DAYS = 540          # how far back a buy can be and still get a return computed
MAX_ITEMS_PER_POL = 25       # cap a politician's trade list in the payload
FMP_LIMIT = 25               # free-tier ceiling per congress endpoint (page>0 also 402s)


def _clean_company(s):
    s = (s or "").strip()
    # drop trailing footnote markers like " (1)" the disclosures attach
    while s.endswith(")") and "(" in s[-5:]:
        s = s[: s.rfind("(")].strip()
    return s


# ---- DATA SOURCE (the only part to swap for a richer feed) ----
def fetch_trades():
    """Returns a flat list of normalized trades from FMP. Each: name, chamber, ticker,
    company, type, date(YYYY-MM-DD), amount, link."""
    if not config.FMP_API_KEY:
        print("no FMP_API_KEY — set it in .env to populate this tab")
        return []
    out = []
    for ep, chamber in (("senate-latest", "Senate"), ("house-latest", "House")):
        try:
            d = fetch.get_json(f"https://financialmodelingprep.com/stable/{ep}"
                               f"?page=0&limit={FMP_LIMIT}&apikey={config.FMP_API_KEY}")
        except Exception as e:
            print(f"  [fmp {ep}] failed: {type(e).__name__} {str(e)[:90]}")
            continue
        for r in (d if isinstance(d, list) else []):
            name = f"{r.get('firstName', '')} {r.get('lastName', '')}".strip() or r.get("office") or "Unknown"
            out.append(dict(
                name=name, chamber=chamber,
                ticker=(r.get("symbol") or "").upper().strip(),
                company=_clean_company(r.get("assetDescription")),
                type=(r.get("type") or "").strip(),
                date=(r.get("transactionDate") or "")[:10],
                amount=(r.get("amount") or "").strip(),
                link=r.get("link") or "",
            ))
    return out


def parse_date(s):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.datetime.strptime((s or "")[:10].strip(), fmt).date()
        except ValueError:
            continue
    return None


def is_buy(t):
    return (t.get("type") or "").lower().startswith(("purchase", "buy"))


def compute_returns(trades):
    """Attach approximate % return (trade date → today) to each BUY with a valid recent date.
    Downloads each unique ticker once. Returns the same list with t['ret'] set (or None)."""
    cutoff = datetime.date.today() - datetime.timedelta(days=LOOKBACK_DAYS)
    buys = [t for t in trades if t["ticker"] and is_buy(t)]
    for t in buys:
        t["_d"] = parse_date(t["date"])
    tickers = sorted({t["ticker"] for t in buys if t.get("_d") and t["_d"] >= cutoff})
    if not tickers:
        return
    try:
        import yfinance as yf
    except Exception:
        return
    px = {}
    for tk in tickers:
        try:
            h = yf.download(tk, start=str(cutoff), auto_adjust=True, progress=False)
            if hasattr(h.columns, "get_level_values"):
                h.columns = h.columns.get_level_values(0)
            px[tk] = h["Close"].dropna() if "Close" in h.columns and len(h) else None
        except Exception:
            px[tk] = None
    for t in buys:
        d, s = t.get("_d"), px.get(t["ticker"])
        if d and s is not None and len(s):
            after = s[[dt.date() >= d for dt in s.index]]
            if len(after) and float(after.iloc[0]) > 0:
                t["ret"] = round((float(s.iloc[-1]) / float(after.iloc[0]) - 1) * 100, 1)


def aggregate(trades):
    """Group trades by politician, newest first, with summary stats."""
    byp = defaultdict(list)
    for t in trades:
        byp[(t["name"], t["chamber"])].append(t)
    pols = []
    for (name, chamber), items in byp.items():
        items.sort(key=lambda x: (parse_date(x["date"]) or datetime.date.min), reverse=True)
        buy_rets = [t["ret"] for t in items if is_buy(t) and t.get("ret") is not None]
        last = items[0]["date"] if items else ""
        pols.append(dict(
            name=name, chamber=chamber,
            trades=len(items),
            buys=sum(1 for t in items if is_buy(t)),
            last_date=last,
            avg_return=round(sum(buy_rets) / len(buy_rets), 1) if buy_rets else None,
            win_rate=round(sum(1 for r in buy_rets if r > 0) / len(buy_rets) * 100) if buy_rets else None,
            items=[dict(ticker=t["ticker"], company=t["company"], type=t["type"],
                        date=t["date"], amount=t["amount"], ret=t.get("ret"), link=t["link"])
                   for t in items[:MAX_ITEMS_PER_POL]],
        ))
    pols.sort(key=lambda p: (-p["trades"], p["name"]))   # default: most active
    return pols


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    trades = fetch_trades()
    print(f"loaded {len(trades)} trades from FMP (senate + house latest)")
    if not trades:
        return
    compute_returns(trades)
    pols = aggregate(trades)
    print(f"{len(pols)} unique politicians; {sum(p['buys'] for p in pols)} buys")
    print("\nMOST ACTIVE:")
    for p in pols[:12]:
        ar = f"{p['avg_return']:+.1f}%" if p["avg_return"] is not None else "  n/a"
        print(f"  {p['name'][:24]:24s} {p['chamber']:6s} {p['trades']:2d} trades | avg {ar}")

    payload = dict(
        updated=time.time(), source="FMP (senate-latest + house-latest)",
        disclaimer="Informational only — NOT a buy signal. Recent disclosures from the free data "
                   "feed (~20-30 members), not the full roster. Returns are approximate (from the "
                   "disclosed trade date, which lags the actual trade by weeks-to-months).",
        politicians=pols,
    )
    os.makedirs("app", exist_ok=True)
    with open("app/politicians.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\nsaved app/politicians.json")


if __name__ == "__main__":
    main()

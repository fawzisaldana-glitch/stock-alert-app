#!/usr/bin/env python3
"""
Live macro de-risk dashboard from FREE FRED CSVs (no API key) + Shiller CAPE.
Writes app/macro.json so the app's dashboard auto-refreshes instead of going stale.
De-risk gauges are TIMING signals; CAPE is shown as CONTEXT (return-predictor, NOT a timer).
"""
import csv
import io
import math
import re
import sys
import time

import config  # noqa: F401  (loads .env / SEC UA used by fetch)
import fetch


def fred_latest(series):
    try:
        raw = fetch.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}").decode("utf-8", "ignore")
    except Exception:
        return None, None
    rows = list(csv.reader(io.StringIO(raw)))
    for r in reversed(rows[1:]):
        if len(r) >= 2 and r[1] not in (".", ""):
            try:
                return r[0], float(r[1])
            except ValueError:
                continue
    return None, None


def _phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def recession_prob(spread_3m10y):          # NY Fed Estrella-Mishkin probit
    return _phi(-0.5333 - 0.6629 * spread_3m10y) * 100


def cape():
    try:
        html = fetch.get("https://www.multpl.com/shiller-pe").decode("utf-8", "ignore")
        m = re.search(r"Current Shiller PE Ratio[^0-9]{0,40}([0-9]{1,3}\.[0-9]{1,2})", html)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    g = {}
    d, v = fred_latest("T10Y2Y")
    g["2s10s (curve)"] = dict(value=v, date=d, unit="pp",
                              red=(v is not None and v < 0),
                              warn=(v is not None and 0 <= v < 0.30),   # nearing inversion
                              trigger="re-inverts < 0")
    d, s310 = fred_latest("T10Y3M")
    g["3m10y (curve)"] = dict(value=s310, date=d, unit="pp",
                              red=(s310 is not None and s310 < 0),
                              warn=(s310 is not None and 0 <= s310 < 0.30),  # nearing inversion
                              trigger="re-inverts < 0")
    rp = round(recession_prob(s310), 1) if s310 is not None else None
    g["NY Fed recession prob"] = dict(value=rp, unit="%",
                                      red=(rp is not None and rp > 30),
                                      warn=(rp is not None and rp > 20),   # approaching danger zone
                                      trigger="> 30%")
    d, v = fred_latest("BAMLH0A0HYM2")
    g["HY credit spread"] = dict(value=v, date=d, unit="%", red=(v is not None and v > 6),
                                 warn=(v is not None and v > 5), trigger="> 6%")
    d, v = fred_latest("SAHMREALTIME")
    g["Sahm rule (jobs)"] = dict(value=v, date=d, unit="",
                                 red=(v is not None and v >= 0.5),
                                 warn=(v is not None and v >= 0.3),   # nearing trigger
                                 trigger=">= 0.50")

    reds = sum(1 for x in g.values() if x.get("red"))
    overall = "RED" if reds >= 2 else ("CAUTION" if reds == 1 else "GREEN")

    cp = cape()
    context = dict(cape=dict(value=cp, unit="x", stretched=(cp is not None and cp > 35),
                             note="valuation = LOW future returns, NOT a crash timer"))

    out = dict(updated=time.time(), overall=overall, reds=reds, gauges=g, context=context)
    import json
    import os
    os.makedirs("app", exist_ok=True)
    with open("app/macro.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"MACRO DE-RISK DASHBOARD: {overall}  ({reds} red of {len(g)})\n")
    for k, x in g.items():
        flag = "RED" if x.get("red") else ("warn" if x.get("warn") else "ok")
        print(f"  {k:24s} {str(x['value']):>7} {x['unit']:2s}  [{flag}]  trigger {x['trigger']}")
    print(f"\n  CONTEXT  Shiller CAPE {cp} x  (stretched; return-predictor, not a timer)")
    print("\nsaved app/macro.json")


if __name__ == "__main__":
    main()

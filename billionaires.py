#!/usr/bin/env python3
"""
SIGNAL: what famous investors are buying — from SEC 13F-HR filings (FREE, via EDGAR).
HONEST LIMITS (this project's own research ranked 13F the WEAKEST smart-money signal):
  - filed ~45 days AFTER quarter-end (stale)
  - LONG US-equity holdings only (no shorts, cash, bonds, or foreign)
  - reveals WHAT, not WHY
So: idea-generation / "what are the greats positioned in", NOT a timing trigger.
"""
import re
import sys
import urllib.parse

import defusedxml.ElementTree as ET

import config
import fetch

# Famous investors -> resolved by name to their fund's SEC CIK at runtime.
FUNDS = [
    "Berkshire Hathaway",            # Warren Buffett
    "Scion Asset Management",        # Michael Burry
    "Pershing Square Capital Management",  # Bill Ackman
    "Appaloosa LP",                  # David Tepper
    "Duquesne Family Office",        # Stanley Druckenmiller
    "Third Point LLC",               # Dan Loeb
]


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def resolve_cik(name):
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company="
           + urllib.parse.quote(name) + "&type=13F-HR&dateb=&owner=include&count=10&output=atom")
    try:
        raw = fetch.get(url, accept="application/atom+xml").decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r"CIK=(\d{10})", raw) or re.search(r"<cik>(\d+)</cik>", raw)
    return int(m.group(1)) if m else None


def latest_13f(cik, n=2):
    try:
        j = fetch.get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    except Exception:
        return "", []
    name = j.get("name", "")
    recent = j.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    dates = recent.get("reportDate", [])
    out = []
    for i, f in enumerate(forms):
        if f == "13F-HR":
            out.append((accns[i], dates[i] if i < len(dates) else ""))
            if len(out) >= n:
                break
    return name, out


def infotable(cik, accession):
    acc = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
    try:
        idx = fetch.get_json(base + "index.json")
    except Exception:
        return []
    xmls = [it["name"] for it in idx.get("directory", {}).get("item", [])
            if it.get("name", "").lower().endswith(".xml")]
    for nm in xmls:
        try:
            raw = fetch.get(base + nm)
            if len(raw) > 12_000_000:
                continue
            root = ET.fromstring(raw)
        except Exception:
            continue
        if _local(root.tag) != "informationTable":
            continue
        holdings = []
        for it in root:
            if _local(it.tag) != "infoTable":
                continue
            d = {"issuer": "", "cusip": "", "value": 0.0, "shares": 0.0, "putCall": ""}
            for ch in it.iter():
                ln = _local(ch.tag)
                if ln == "nameOfIssuer":
                    d["issuer"] = (ch.text or "").strip()
                elif ln == "cusip":
                    d["cusip"] = (ch.text or "").strip()
                elif ln == "putCall":
                    d["putCall"] = (ch.text or "").strip()
                elif ln == "value":
                    try:
                        d["value"] = float((ch.text or "0").replace(",", ""))
                    except ValueError:
                        pass
                elif ln == "sshPrnamt":
                    try:
                        d["shares"] = float((ch.text or "0").replace(",", ""))
                    except ValueError:
                        pass
            if d["cusip"]:
                holdings.append(d)
        return holdings
    return []


def _aggregate(holdings):
    agg = {}
    for h in holdings:
        a = agg.setdefault(h["cusip"], {"issuer": h["issuer"], "value": 0.0, "shares": 0.0})
        a["value"] += h["value"]
        a["shares"] += h["shares"]
    return agg


def analyze(name_query):
    cik = resolve_cik(name_query)
    if not cik:
        return None
    entity, filings = latest_13f(cik, 2)
    if not filings:
        return None
    cur = _aggregate(infotable(cik, filings[0][0]))
    prev = _aggregate(infotable(cik, filings[1][0])) if len(filings) > 1 else {}
    # 13F value is in dollars (post-2023) or thousands (older) — auto-scale by portfolio magnitude
    tot = sum(a["value"] for a in cur.values())
    if 0 < tot < 1e9:
        for a in cur.values():
            a["value"] *= 1000
    new_buys = sorted([(c, a) for c, a in cur.items() if c not in prev],
                      key=lambda x: -x[1]["value"])
    adds = sorted([(c, a) for c, a in cur.items()
                   if c in prev and a["shares"] > prev[c]["shares"] * 1.05],
                  key=lambda x: -x[1]["value"])
    top = sorted(cur.items(), key=lambda x: -x[1]["value"])
    return dict(entity=entity, cik=cik, report=filings[0][1],
                portfolio=sum(a["value"] for a in cur.values()), holdings=len(cur),
                new_buys=new_buys[:5], adds=adds[:3], top=top[:5])


def consensus(results):
    from collections import defaultdict
    holders = defaultdict(set)
    for r in results:
        for c, a in r["top"] + r["new_buys"]:
            holders[a["issuer"].upper()].add(r["entity"].split()[0].title())
    multi = [(n, sorted(fs)) for n, fs in holders.items() if len(fs) >= 2]
    multi.sort(key=lambda x: -len(x[1]))
    return multi


def main():
    import json
    import os
    import time
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("Billionaire 13F tracker (SEC EDGAR) — holdings as of last quarter-end (~45-day lag)\n")
    results = []
    seen = set()
    for q in FUNDS:
        r = analyze(q)
        if not r or r["cik"] in seen:
            print(f"  {q[:34]:34s} -> unresolved / no 13F")
            continue
        seen.add(r["cik"])
        results.append(r)
        print(f"\n{r['entity'][:48]} (as of {r['report']}) ${r['portfolio']/1e9:.1f}B / {r['holdings']} pos")
        for label, key in (("NEW BUYS", "new_buys"), ("ADDED TO", "adds"), ("TOP HOLDINGS", "top")):
            if r[key]:
                print(f"  {label}:")
                for c, a in r[key]:
                    print(f"      {a['issuer'][:32]:32s} ${a['value']/1e6:9.0f}M")
    con = consensus(results)
    if con:
        print("\nCONSENSUS (held/bought by 2+ of these funds):")
        for name, fs in con[:8]:
            print(f"  {name[:26]:26s} <- {', '.join(fs)}")

    payload = dict(updated=time.time(), funds=[
        dict(entity=r["entity"], report=r["report"], portfolio=r["portfolio"], holdings=r["holdings"],
             new_buys=[dict(issuer=a["issuer"], value=a["value"]) for c, a in r["new_buys"]],
             adds=[dict(issuer=a["issuer"], value=a["value"]) for c, a in r["adds"]],
             top=[dict(issuer=a["issuer"], value=a["value"]) for c, a in r["top"]])
        for r in results], consensus=[dict(name=n, funds=fs) for n, fs in con[:12]])
    os.makedirs("app", exist_ok=True)
    with open("app/billionaires.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\nsaved app/billionaires.json")


if __name__ == "__main__":
    main()

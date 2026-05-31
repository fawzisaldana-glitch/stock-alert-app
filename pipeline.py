"""End-to-end: pull signals -> persist -> detect clusters -> enrich -> score -> alerts.json (+ Telegram)."""
import json
import os
import time

import config
import contracts
import notify as notifier
import research
import scoring
import sec_insiders
import sectors
import storage
import valuation


def _fmt(al):
    return (f"*{al['ticker']}*  ·  score {al['score']}\n"
            f"🏷️ {al['sector']}  ·  {al['type'].replace('_', ' ')}\n"
            f"{al['headline']}\n_{al['why']}_\n{al['link']}")


def run(notify=False):
    storage.init()
    t0 = time.time()

    # 1) INSIDER open-market buys -> persist (cluster memory builds across runs)
    urls = sec_insiders.recent_form4_txt_urls(config.INSIDER_FEED_COUNT)
    new_buys = scanned = 0
    for u in urls:
        scanned += 1
        acc, purchases = sec_insiders.parse_purchases(u)
        if not purchases:
            continue
        p0 = purchases[0]
        rec = dict(accession=acc, ticker=p0["ticker"], issuer=p0["issuer"], owner=p0["owner"],
                   title=p0["title"], is_officer=p0["is_officer"],
                   shares=sum(p["shares"] for p in purchases), price=p0["price"],
                   value=sum(p["value"] for p in purchases), txn_date=p0["txn_date"])
        if storage.upsert_insider(rec):
            new_buys += 1
    clusters = storage.recent_clusters(config.CLUSTER_LOOKBACK_DAYS, config.MIN_CLUSTER_INSIDERS)

    # 2) CONTRACT catalysts -> persist
    new_awards = 0
    for a in contracts.recent_large_awards(config.CONTRACT_LOOKBACK_DAYS, config.MIN_CONTRACT_USD):
        if storage.upsert_contract(a):
            new_awards += 1

    # 3) BUILD ALERTS
    alerts = []
    for c in clusters:
        sector = sectors.sector_for(c["ticker"])
        base = scoring.score_insider_cluster(c["n"], c["val"] or 0, bool(c["off"]))
        final, cheap = scoring.apply_cheapness(base, c["ticker"])
        alerts.append(dict(
            ticker=c["ticker"], type="insider_cluster", score=final, sector=sector,
            headline=f"{c['n']} insiders bought {c['ticker']} (${(c['val'] or 0)/1e6:.1f}M)",
            why=scoring.why_insider(c, sector, cheap),
            details=dict(insiders=c["n"], total_value=round(c["val"] or 0),
                         owners=c["owners"], issuer=c["issuer"], officer=bool(c["off"]),
                         cheapness=cheap),
            link=(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                  f"&company={c['ticker']}&type=4&owner=only&output=atom"),
            created_at=time.time()))

    dropped_unmatched = 0
    for a in storage.recent_contracts(config.CONTRACT_LOOKBACK_DAYS, config.MIN_CONTRACT_USD):
        ticker = a["ticker"] or ""
        if not ticker:                      # only public-ticker contracts are actionable for a trader
            dropped_unmatched += 1
            continue
        sector = sectors.sector_for(ticker)
        base = scoring.score_contract(a["amount"])
        final, cheap = scoring.apply_cheapness(base, ticker)
        alerts.append(dict(
            ticker=ticker, type="contract", score=final, sector=sector,
            headline=f"${a['amount']/1e6:.0f}M contract — {a['recipient'][:40]}",
            why=scoring.why_contract(a, sector, cheap),
            details=dict(amount=a["amount"], agency=a["agency"], action_date=a["action_date"],
                         recipient=a["recipient"], matched_ticker=bool(ticker), cheapness=cheap),
            link="https://www.usaspending.gov/search",
            created_at=time.time()))

    alerts.sort(key=lambda x: -x["score"])
    for al in alerts:
        storage.add_alert(al)

    # Enrich top alerts with full valuation (DCF + comps). Capped to top 25 unique
    # tickers per run to stay polite on the 250 calls/day FMP free tier — each call
    # is cached in cache/valuation_<TKR>_<DATE>.json so reruns same day are free.
    val_map = {}
    valuated = 0
    seen = set()
    for al in alerts[:60]:                              # window covers what UI shows
        t = al["ticker"]
        if not t or t in seen:
            continue
        seen.add(t)
        if valuated >= 25:                              # cap per-run
            break
        v = valuation.valuation_for_ticker(t)
        if v:
            val_map[t] = v
            valuated += 1

    # Pre-generate Excel deep-dive for the top 5 highest-scored alerts. Each report adds
    # ~10 extra FMP calls (peer details), so capping at 5 keeps daily total under the 250
    # free-tier ceiling even with 25 valuations + other pipeline calls.
    reports = {}
    seen_for_report = set()
    for al in alerts[:30]:
        t = al["ticker"]
        if not t or t in seen_for_report:
            continue
        seen_for_report.add(t)
        if len(reports) >= 5:
            break
        rel = research.build_report(t)
        if rel:
            reports[t] = rel

    os.makedirs(os.path.dirname(config.ALERTS_JSON) or ".", exist_ok=True)
    with open(config.ALERTS_JSON, "w", encoding="utf-8") as f:
        json.dump(dict(updated=time.time(), count=len(alerts), alerts=alerts[:100]), f, indent=2)
    with open("app/valuation.json", "w", encoding="utf-8") as f:
        json.dump(dict(updated=time.time(), count=len(val_map),
                       valuations=val_map, reports=reports), f, indent=2)

    sent = 0
    if notify:
        for al in alerts[:5]:
            if notifier.send(_fmt(al)):
                sent += 1

    return dict(scanned_filings=scanned, new_insider_buys=new_buys, clusters=len(clusters),
                new_awards=new_awards, contracts_unmatched=dropped_unmatched,
                alerts=len(alerts), telegram_sent=sent,
                seconds=round(time.time() - t0, 1), top=alerts[:6])

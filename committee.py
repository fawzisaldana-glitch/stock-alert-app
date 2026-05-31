#!/usr/bin/env python3
"""
The AI Hedge Fund committee engine.

CEO -> 5 investor agents -> deterministic CIO -> QA gate -> publish, with a Learning agent
that turns past picks' realized returns into lessons the CEO applies next run.

Deterministic by design: every persona is a documented weighting of normalized features, so
the fund produces Top-5 Day + Top-5 Month with NO LLM and NO network. If the free FCC proxy
is up, we layer one-sentence narration on top — but it never affects the math (anti-hallucination,
exactly like the video's "deterministic CIO"). Output: app/picks.json.
"""
import datetime
import json
import os
import sys

import fund_config as cfg


def _num(x, default=None):
    try:
        f = float(x)
        return default if f != f else f
    except (TypeError, ValueError):
        return default


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _today():
    return datetime.date.today().isoformat()


# --------------------------- candidates & features ---------------------------
def load_candidates():
    """Build the candidate universe from alerts, enriched with valuation. Each candidate
    gets a normalized feature vector the personas score."""
    alerts = _load("app/alerts.json", {}).get("alerts", [])
    vals = _load("app/valuation.json", {}).get("valuations", {})
    # Merge multiple alerts for the SAME ticker into one candidate — a name carrying both an
    # insider cluster AND a gov contract is a stronger signal, not two separate picks.
    by_tk = {}
    for a in alerts:
        tk = a.get("ticker")
        if not tk:
            continue
        g = by_tk.setdefault(tk, {"catalyst": 0.0, "insider": 0.0, "contract": 0.0,
                                  "sector": a.get("sector") or "—", "types": set(), "whys": []})
        g["catalyst"] = max(g["catalyst"], _num(a.get("score"), 0) / 100.0)
        if a.get("type") == "insider_cluster":
            g["insider"] = 1.0
        if a.get("type") == "contract":
            g["contract"] = 1.0
        g["types"].add(a.get("type") or "signal")
        if a.get("why") or a.get("headline"):
            g["whys"].append(a.get("why") or a.get("headline"))

    out = []
    for tk, g in by_tk.items():
        v = vals.get(tk, {})
        cheap = _num(v.get("cheapness"), 0.5)
        mos = _num(v.get("margin_of_safety"))
        mos_n = 0.5 if mos is None else max(0.0, min(1.0, (max(-0.5, min(0.5, mos)) + 0.5)))
        feat = {
            "catalyst": max(0.0, min(1.0, g["catalyst"])),
            "cheap": max(0.0, min(1.0, cheap if cheap is not None else 0.5)),
            "mos": mos_n,
            "insider": g["insider"],
            "contract": g["contract"],
        }
        # representative type: insider cluster (strongest) if present, else contract, else signal
        rtype = "insider_cluster" if g["insider"] else "contract" if g["contract"] else "signal"
        out.append(dict(
            ticker=tk, sector=g["sector"], type=rtype,
            why=max(g["whys"], key=len) if g["whys"] else "", features=feat,
            market_price=_num(v.get("market_price")),
            intrinsic=_num(v.get("intrinsic_value")), mos=mos,
        ))
    return out


def persona_score(name, feat, nudges=None):
    """One investor's 0..100 score for a candidate = weighted sum of features (+ lesson nudges)."""
    w = dict(cfg.PERSONAS[name]["weights"])
    if nudges:
        for k, dv in nudges.items():
            if k in w:
                w[k] = max(0.0, w[k] + dv)
    tot = sum(w.values()) or 1.0
    return round(100.0 * sum(feat.get(k, 0.0) * w[k] for k in cfg.FEATURES) / tot, 1)


# --------------------------- CEO ---------------------------
def ceo_directive(macro, lessons):
    """The CEO reads regime + lessons, sets risk posture, the cross-persona weights, and
    any feature nudges learned from past mistakes."""
    reds = (macro or {}).get("reds")
    overall = (macro or {}).get("overall", "?")
    posture = cfg.posture_for(reds)
    weights = dict(cfg.REGIME_WEIGHTS[posture])
    nudges = (lessons or {}).get("feature_nudges", {})
    msg = {
        "defensive": f"Regime {overall} ({reds}/5 red). Defensive: favor quality/value, trim momentum.",
        "neutral": f"Regime {overall} ({reds}/5 red). Balanced posture; no strong tilt.",
        "constructive": f"Regime {overall} (0/5 red). Constructive: catalysts & momentum earn more weight.",
    }[posture]
    if nudges:
        msg += " Applying lessons: " + ", ".join(f"{k}{'+' if v >= 0 else ''}{v:.2f}" for k, v in nudges.items()) + "."
    return dict(posture=posture, regime=overall, reds=reds, persona_weights=weights,
                feature_nudges=nudges, directive=msg,
                lessons_applied=(lessons or {}).get("notes", [])[:3])


# --------------------------- CIO (deterministic) ---------------------------
def cio_score(cand, ceo):
    """Regime-weighted average of the 5 persona scores → the actual ranking number."""
    feat = cand["features"]
    nudges = ceo["feature_nudges"]
    pw = ceo["persona_weights"]
    per = {name: persona_score(name, feat, nudges) for name in cfg.PERSONAS}
    wsum = sum(pw.values()) or 1.0
    final = round(sum(per[name] * pw[name] for name in per) / wsum, 1)
    return final, per


def board_meeting(candidates, ceo):
    scored = []
    for c in candidates:
        final, per = cio_score(c, ceo)
        scored.append(dict(
            ticker=c["ticker"], sector=c["sector"], type=c["type"], score=final,
            committee=per, market_price=c["market_price"], intrinsic=c["intrinsic"],
            mos=c["mos"], why=c["why"],
        ))
    scored.sort(key=lambda x: -x["score"])
    return scored


# --------------------------- Top 5 of the Month (from history) ---------------------------
def top_month(today_ranked):
    """Aggregate the rolling 30-day history of daily picks → most-conviction names of the month.
    Cold start (little/no history) falls back to today's ranking."""
    hist = []
    try:
        with open(cfg.PICKS_HISTORY, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    hist.append(json.loads(line))
    except Exception:
        hist = []
    cutoff = (datetime.date.today() - datetime.timedelta(days=cfg.MONTH_WINDOW_DAYS)).isoformat()
    recent = [h for h in hist if h.get("date", "") >= cutoff]
    if len(recent) < cfg.TOP_N:
        return today_ranked[: cfg.TOP_N]   # not enough history yet
    agg = {}
    for h in recent:
        a = agg.setdefault(h["ticker"], {"ticker": h["ticker"], "scores": [], "appearances": 0,
                                         "sector": h.get("sector", "—"), "type": h.get("type", "signal")})
        a["scores"].append(h.get("score", 0))
        a["appearances"] += 1
    rows = [dict(ticker=a["ticker"], sector=a["sector"], type=a["type"],
                 score=round(sum(a["scores"]) / len(a["scores"]), 1), appearances=a["appearances"])
            for a in agg.values()]
    # conviction = average score, tie-broken by how often it showed up
    rows.sort(key=lambda x: (-x["score"], -x["appearances"]))
    return rows[: cfg.TOP_N]


# --------------------------- Learning agent ---------------------------
def learn_from_history():
    """Read past picks, measure forward returns on aged ones, distill lessons → lessons.json.
    Lessons become small, bounded feature nudges the CEO applies. Cold start = inert."""
    hist = []
    try:
        with open(cfg.PICKS_HISTORY, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    hist.append(json.loads(line))
    except Exception:
        hist = []
    # evaluate picks at least 14 days old that logged an entry price
    cutoff = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    aged = [h for h in hist if h.get("date", "9999") <= cutoff and h.get("entry_price")]
    lessons = dict(generated=_today(), n_evaluated=0, notes=[], feature_nudges={})
    if not aged:
        lessons["notes"].append("Cold start: no aged picks with prices yet — no lessons. The loop "
                                "will learn once picks mature (~2+ weeks of history).")
        _save_lessons(lessons)
        return lessons
    try:
        import yfinance as yf
    except Exception:
        _save_lessons(lessons)
        return lessons
    by_type = {"insider_cluster": [], "contract": []}
    for h in aged:
        try:
            cur = yf.Ticker(h["ticker"]).fast_info.get("last_price")
        except Exception:
            cur = None
        if cur and h["entry_price"]:
            ret = cur / h["entry_price"] - 1
            by_type.setdefault(h.get("type", "signal"), []).append(ret)
    lessons["n_evaluated"] = sum(len(v) for v in by_type.values())
    for t, rets in by_type.items():
        if len(rets) >= 3:
            avg = sum(rets) / len(rets)
            lessons["notes"].append(f"{t}: avg fwd return {avg:+.1%} over {len(rets)} aged picks.")
            # if a signal type is consistently negative, nudge its feature down (bounded ±0.08)
            feat = "insider" if t == "insider_cluster" else "contract" if t == "contract" else None
            if feat:
                lessons["feature_nudges"][feat] = max(-0.08, min(0.08, round(avg, 3)))
    _save_lessons(lessons)
    return lessons


def _save_lessons(lessons):
    os.makedirs(os.path.dirname(cfg.LESSONS_JSON), exist_ok=True)
    with open(cfg.LESSONS_JSON, "w", encoding="utf-8") as f:
        json.dump(lessons, f, indent=2)


# --------------------------- QA gate ---------------------------
def qa_gate(payload):
    issues = []
    day = payload.get("top_day", [])
    lo, hi = cfg.QA["score_range"]
    if len(day) < cfg.QA["min_day_picks"]:
        issues.append(f"only {len(day)} day picks (need >= {cfg.QA['min_day_picks']})")
    for p in day:
        if not (lo <= p.get("score", -1) <= hi):
            issues.append(f"{p.get('ticker')}: score {p.get('score')} out of range")
        if cfg.QA["require_reasoning"] and not p.get("why"):
            issues.append(f"{p.get('ticker')}: missing reasoning")
        if p.get("intrinsic") is not None and p["intrinsic"] != p["intrinsic"]:
            issues.append(f"{p.get('ticker')}: NaN intrinsic")
    tks = [p.get("ticker") for p in day]
    if len(tks) != len(set(tks)):
        issues.append("duplicate tickers in top_day")
    if not payload.get("top_month"):
        issues.append("top_month empty")
    return dict(passed=len(issues) == 0, issues=issues, checked_at=_today())


# --------------------------- optional free-LLM narration ---------------------------
def narrate(picks, ceo):
    """Best-effort: ask the free FCC proxy for a one-line rationale per top pick. Never blocks,
    never changes scores. Silently skipped if FCC is down."""
    if not cfg.FCC.get("enabled") or not picks:
        return
    import urllib.request
    for p in picks:
        prompt = (f"You are {ceo['posture']} CIO. In ONE sentence (<25 words), say why {p['ticker']} "
                  f"({p['sector']}, {p['type']}, score {p['score']}/100) is a top pick. No preamble.")
        body = json.dumps({"model": cfg.FCC["model"], "max_tokens": 60,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        try:
            req = urllib.request.Request(cfg.FCC["base_url"].rstrip("/") + "/chat/completions",
                                         data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cfg.FCC["timeout"]) as r:
                d = json.loads(r.read())
            txt = (d.get("choices", [{}])[0].get("message", {}) or {}).get("content", "").strip()
            if txt:
                p["narration"] = txt
        except Exception:
            return   # FCC down — bail on the whole narration pass, keep deterministic output


# --------------------------- main ---------------------------
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    lessons = learn_from_history()                       # 1. learn first
    macro = _load("app/macro.json", {})                  # 2. read regime
    ceo = ceo_directive(macro, lessons)                  # 3. CEO sets directive
    print("CEO:", ceo["directive"])

    candidates = load_candidates()
    if not candidates:
        print("no candidates (run the signal engines first)"); return
    ranked = board_meeting(candidates, ceo)              # 4. committee + CIO
    top_day = ranked[: cfg.TOP_N]
    narrate(top_day, ceo)                                # 5. optional narration
    tmonth = top_month(ranked)                           # 6. Top 5 of the month

    import time
    payload = dict(updated=time.time(), as_of=_today(),
                   cadence=cfg.CADENCE["runs_per_day"], ceo=ceo,
                   universe=len(candidates), top_day=top_day, top_month=tmonth)
    payload["qa"] = qa_gate(payload)                     # 7. QA gate

    print(f"\nTop {cfg.TOP_N} of the Day ({ceo['posture']}):")
    for p in top_day:
        print(f"  {p['ticker']:6s} {p['score']:5.1f}  {p['type']:14s} {p['sector'][:30]}")
    print(f"QA: {'PASS' if payload['qa']['passed'] else 'HOLD — ' + '; '.join(payload['qa']['issues'])}")

    if payload["qa"]["passed"]:
        os.makedirs("app", exist_ok=True)
        with open(cfg.PICKS_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        _log_history(top_day)                            # 8. log for the learning loop
        print(f"\npublished {cfg.PICKS_JSON}")
    else:
        print("\nQA HELD — not publishing (app keeps last good picks).")


def _log_history(top_day):
    os.makedirs(os.path.dirname(cfg.PICKS_HISTORY), exist_ok=True)
    with open(cfg.PICKS_HISTORY, "a", encoding="utf-8") as f:
        for p in top_day:
            f.write(json.dumps(dict(date=_today(), ticker=p["ticker"], score=p["score"],
                                    type=p["type"], sector=p["sector"],
                                    entry_price=p.get("market_price"))) + "\n")


if __name__ == "__main__":
    main()

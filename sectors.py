"""
Ticker -> sector/industry for the "learn while trading" tags. FREE via SEC:
  company_tickers.json (ticker<->CIK<->name) + data.sec.gov submissions JSON (sicDescription).
SEC uses SIC industry descriptions (not GICS) — good enough for learning labels.
"""
import re

import config
import fetch

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_tickers = None
_sic = {}
_tok_index = None


def _load():
    global _tickers
    if _tickers is None:
        try:
            data = fetch.get_json(TICKERS_URL)
            _tickers = {}
            for row in data.values():
                _tickers[row["ticker"].upper()] = {"cik": int(row["cik_str"]), "name": row["title"]}
        except Exception as e:
            print("  [sectors] ticker map load failed:", e)
            _tickers = {}
    return _tickers


def cik_for(ticker):
    r = _load().get((ticker or "").upper())
    return r["cik"] if r else None


def sector_for(ticker):
    cik = cik_for(ticker)
    if not cik:
        return "Unknown"
    if cik in _sic:
        return _sic[cik]
    try:
        j = fetch.get_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
        desc = (j.get("sicDescription") or "Unknown").title()
    except Exception:
        desc = "Unknown"
    _sic[cik] = desc
    return desc


# Strict recipient->ticker matching. Precision over recall: a WRONG ticker (alerting you
# about Philip Morris for a Sandia Labs contract) is worse than honestly saying "Unmatched".
_SUFFIX = {"CORP", "CORPORATION", "INC", "INCORPORATED", "CO", "COMPANY", "LLC", "LP", "LTD",
           "LIMITED", "PLC", "HOLDINGS", "HOLDING", "GROUP", "THE", "TRUST", "FUND", "SA", "NV", "AG"}
_GENERIC = {"NATIONAL", "AMERICAN", "AMERICA", "INTERNATIONAL", "GLOBAL", "SOLUTIONS", "SYSTEMS",
            "TECHNOLOGIES", "TECHNOLOGY", "SERVICES", "SERVICE", "INDUSTRIES", "ENTERPRISES",
            "PARTNERS", "CAPITAL", "ENERGY", "SECURITY", "NUCLEAR", "UNITED", "GENERAL",
            "STANDARD", "ASSOCIATES", "CONSOLIDATED", "FIRST", "NEW", "ALLIANCE", "DYNAMICS"}


def _tokens(name):
    return [w for w in re.sub(r"[^A-Z0-9 ]", " ", name.upper()).split()
            if w not in _SUFFIX and len(w) > 1]


def _build_index():
    global _tok_index
    _tok_index = []
    for t, info in _load().items():
        distinctive = {w for w in _tokens(info["name"]) if w not in _GENERIC and len(w) >= 4}
        if distinctive:
            _tok_index.append((t, distinctive))
    return _tok_index


def find_ticker_by_name(name):
    """Match a contract recipient to a public ticker ONLY on a strong whole-word match."""
    if not name:
        return None
    if _tok_index is None:
        _build_index()
    rtoks = set(_tokens(name))
    if not rtoks:
        return None
    best = None
    for t, cdist in _tok_index:          # ALL distinctive company tokens must appear in the recipient
        if cdist <= rtoks and (best is None or len(cdist) > best[1]):
            best = (t, len(cdist))
    return best[0] if best else None

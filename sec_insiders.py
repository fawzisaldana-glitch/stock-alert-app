"""
SIGNAL #1 (strongest, per research): open-market insider CLUSTER buys.

Source: SEC EDGAR 'getcurrent' Atom feed for Form 4, owner=only (FREE, ~10-min updates).
The feed lists recent ownership filings (buys AND sells); we fetch each filing's full
submission .txt, extract the <ownershipDocument> XML, and keep ONLY transaction code "P"
(open-market purchase, acquired). Routine awards/sells are discarded — that filtering is
the entire edge (Cohen/Malloy/Pomorski 2012: naive all-Form-4 use ~= zero alpha).
"""
import re

import defusedxml.ElementTree as ET   # hardened: forbids XXE + entity-expansion (billion-laughs)

import config
import fetch

GETCURRENT = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
              "&type=4&company=&dateb=&owner=only&count={count}&output=atom")
ATOM = "{http://www.w3.org/2005/Atom}"
OWN_RE = re.compile(r"<ownershipDocument>.*?</ownershipDocument>", re.DOTALL)
ACC_RE = re.compile(r"/([0-9]{10}-[0-9]{2}-[0-9]{6})\.txt$")


def recent_form4_txt_urls(count):
    raw = fetch.get(GETCURRENT.format(count=count), accept="application/atom+xml")
    root = ET.fromstring(raw)
    urls = []
    for entry in root.findall(f"{ATOM}entry"):
        link = entry.find(f"{ATOM}link")
        if link is None or not link.get("href"):
            continue
        href = link.get("href")
        txt = href.replace("-index.htm", ".txt").replace("-index.html", ".txt")
        urls.append(txt)
    return urls


def _t(node):
    return (node.text or "").strip() if node is not None else ""


def parse_purchases(txt_url):
    """Return (accession, list-of-purchase-dicts) for one Form 4 filing."""
    acc_m = ACC_RE.search(txt_url)
    accession = acc_m.group(1) if acc_m else txt_url
    try:
        raw = fetch.get(txt_url).decode("utf-8", "ignore")
    except Exception:
        return accession, []
    if len(raw) > 5_000_000:          # Form 4s are KBs; reject absurdly large submissions (DoS guard)
        return accession, []
    m = OWN_RE.search(raw)
    if not m:
        return accession, []
    try:
        doc = ET.fromstring(m.group(0))
    except Exception:
        return accession, []

    issuer = doc.find("issuer")
    ticker = _t(issuer.find("issuerTradingSymbol")) if issuer is not None else ""
    issuer_name = _t(issuer.find("issuerName")) if issuer is not None else ""
    if not ticker:
        return accession, []

    ro = doc.find("reportingOwner")
    owner = title = ""
    is_officer = is_director = False
    if ro is not None:
        rid = ro.find("reportingOwnerId")
        owner = _t(rid.find("rptOwnerName")) if rid is not None else ""
        rel = ro.find("reportingOwnerRelationship")
        if rel is not None:
            is_officer = _t(rel.find("isOfficer")) in ("1", "true")
            is_director = _t(rel.find("isDirector")) in ("1", "true")
            title = _t(rel.find("officerTitle"))

    ndt = doc.find("nonDerivativeTable")
    if ndt is None:
        return accession, []

    purchases = []
    for tx in ndt.findall("nonDerivativeTransaction"):
        coding = tx.find("transactionCoding")
        code = _t(coding.find("transactionCode")) if coding is not None else ""
        amts = tx.find("transactionAmounts")
        ad = shares = price = 0.0
        if amts is not None:
            ad = _t(amts.find("transactionAcquiredDisposedCode/value"))
            try:
                shares = float(_t(amts.find("transactionShares/value")) or 0)
            except ValueError:
                shares = 0.0
            try:
                price = float(_t(amts.find("transactionPricePerShare/value")) or 0)
            except ValueError:
                price = 0.0
        date = _t(tx.find("transactionDate/value"))
        if code == "P" and ad == "A":                       # open-market purchase
            purchases.append(dict(
                ticker=ticker.upper(), issuer=issuer_name, owner=owner, title=title,
                is_officer=is_officer, is_director=is_director,
                shares=shares, price=price, value=shares * price, txn_date=date,
            ))
    return accession, purchases

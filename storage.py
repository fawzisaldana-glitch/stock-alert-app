"""SQLite store. Persistence is what makes cluster detection work ACROSS runs."""
import sqlite3
import time

import config


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS insider_buys(
        accession TEXT PRIMARY KEY, ticker TEXT, issuer TEXT, owner TEXT, title TEXT,
        is_officer INT, shares REAL, price REAL, value REAL, txn_date TEXT, seen_at REAL);
    CREATE INDEX IF NOT EXISTS ix_ib_seen ON insider_buys(seen_at);
    CREATE TABLE IF NOT EXISTS contracts(
        award_id TEXT PRIMARY KEY, recipient TEXT, ticker TEXT, amount REAL,
        agency TEXT, action_date TEXT, descr TEXT, seen_at REAL);
    CREATE TABLE IF NOT EXISTS alerts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, type TEXT, score REAL,
        sector TEXT, headline TEXT, why TEXT, payload TEXT, created_at REAL);
    """)
    c.commit()
    c.close()


def upsert_insider(r):
    c = _conn()
    cur = c.execute(
        "INSERT OR IGNORE INTO insider_buys VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (r["accession"], r["ticker"], r["issuer"], r["owner"], r["title"],
         int(r["is_officer"]), r["shares"], r["price"], r["value"], r["txn_date"], time.time()))
    new = cur.rowcount > 0
    c.commit()
    c.close()
    return new


def recent_clusters(lookback_days, min_insiders):
    cutoff = time.time() - lookback_days * 86400
    c = _conn()
    rows = c.execute(
        "SELECT ticker, COUNT(DISTINCT owner) AS n, SUM(value) AS val, "
        "GROUP_CONCAT(DISTINCT owner) AS owners, MAX(is_officer) AS off, MAX(issuer) AS issuer "
        "FROM insider_buys WHERE seen_at>=? GROUP BY ticker HAVING n>=? ORDER BY val DESC",
        (cutoff, min_insiders)).fetchall()
    c.close()
    return rows


def upsert_contract(a):
    c = _conn()
    cur = c.execute(
        "INSERT OR IGNORE INTO contracts VALUES(?,?,?,?,?,?,?,?)",
        (a["award_id"], a["recipient"], a.get("ticker") or "", a["amount"],
         a.get("agency", ""), a.get("action_date", ""), a.get("descr", ""), time.time()))
    new = cur.rowcount > 0
    c.commit()
    c.close()
    return new


def recent_contracts(lookback_days, min_usd):
    cutoff = time.time() - lookback_days * 86400
    c = _conn()
    rows = c.execute(
        "SELECT * FROM contracts WHERE seen_at>=? AND amount>=? ORDER BY amount DESC LIMIT 50",
        (cutoff, min_usd)).fetchall()
    c.close()
    return rows


def add_alert(al):
    import json
    c = _conn()
    c.execute("INSERT INTO alerts(ticker,type,score,sector,headline,why,payload,created_at) "
              "VALUES(?,?,?,?,?,?,?,?)",
              (al["ticker"], al["type"], al["score"], al["sector"], al["headline"],
               al["why"], json.dumps(al.get("details", {})), al["created_at"]))
    c.commit()
    c.close()

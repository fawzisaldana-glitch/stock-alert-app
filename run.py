#!/usr/bin/env python3
"""CLI entry. Usage: python run.py [--notify]   (--notify pushes top alerts to Telegram)"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows cp1252 consoles choke on unicode
os.chdir(os.path.dirname(os.path.abspath(__file__)))   # so relative paths (db, alerts.json) work under cron
import pipeline


def main():
    notify = "--notify" in sys.argv
    s = pipeline.run(notify=notify)
    print("\n" + "=" * 64)
    print("STOCK ALERT - run complete")
    print(f"  scanned {s['scanned_filings']} Form 4 filings  ->  {s['new_insider_buys']} new open-market BUYS")
    print(f"  insider clusters (>= {2} insiders/7d): {s['clusters']}")
    print(f"  new contract catalysts: {s['new_awards']}  (dropped {s.get('contracts_unmatched', 0)} private/unmatched recipients)")
    print(f"  ALERTS written: {s['alerts']}   telegram_sent: {s['telegram_sent']}   ({s['seconds']}s)")
    print("=" * 64)
    for al in s["top"]:
        print(f"  [{al['score']:5.1f}] {al['ticker']:8s} {al['type']:15s} {al['sector'][:24]:24s} | {al['headline'][:50]}")
    if not s["top"]:
        print("  (no alerts this run — clusters accumulate as the feed is polled over days)")
    print()


if __name__ == "__main__":
    main()

# Smart-Money Alerts

A **personal** stock-alert system that surfaces *potentially undervalued* names with a
*fresh smart-money catalyst* — open-market **insider cluster buys** and **federal
contract** activity — each tagged by **sector** with a plain-English "why it matters"
note so you learn the pattern while you trade.

Two surfaces, one engine:
- **Telegram bot** — the *ping* (instant phone push when a setup appears).
- **PWA (`app/`)** — the *look deeper* (installable phone web-app to study each alert).

Built on **free, sanctioned** government feeds (SEC EDGAR + USAspending). One run was
verified against live SEC filings on 2026-05-30.

> ⚠️ **Personal use only.** Acting on these *public* disclosures is legal (not insider
> trading). Do **not** redistribute the alerts as investment advice. This is not financial
> advice and places no trades.

---

## What works today (honest status)

| Signal | Status | Notes |
|---|---|---|
| **Insider cluster buys** (SEC Form 4, code "P") | ✅ **Clean core** — the validated #1 edge | Filters to open-market buys; clusters = ≥2 insiders/ticker over 7d, built up across runs |
| Sector tagging | ✅ Works | SEC SIC description per ticker |
| Telegram push | ✅ Ready | Needs a bot token (below) |
| PWA "look deeper" | ✅ Works | Reads `app/alerts.json` |
| **Contracts** (USAspending) | ⚠️ **Experimental** | Surfaces *lifetime* award vehicles (some dating to the 1990s), not just fresh signings; ticker matching is best-effort and can mis-map single-name collisions. **v2:** switch to SEC **8-K Item 1.01** "material agreement" filings via the same EDGAR feed |
| "Undervalued" value gate | ✅ Optional | Activates when an `FMP_API_KEY` is set (free tier) |
| Congress / 13F | ⛔ Not included | Research ranked them weak/contested; deliberately omitted |

---

## Setup (5 minutes)

```
pip install -r requirements.txt
copy .env.example .env          # then edit .env
```

In `.env`:
1. **`SEC_USER_AGENT`** (required) — `YourApp your-real-email@example.com`. SEC returns HTTP 403 without a real contact.
2. **`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`** (optional, for phone push):
   - Message **@BotFather** on Telegram → `/newbot` → copy the token.
   - Message your new bot once, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `chat.id`.
3. **`FMP_API_KEY`** (optional) — turns on the "undervalued" gate (free tier, 250 calls/day).

## Run

```
python run.py            # pull signals, write app/alerts.json, print a summary
python run.py --notify   # also push the top alerts to Telegram
```

## Schedule (so clusters accumulate)

- **n8n:** import `n8n_workflow.json` (Schedule trigger → Execute Command → `run.py --notify`).
- **Windows Task Scheduler:** run `python <path>\run.py --notify` every 1–2h during market hours.
- **Oracle VM:** a cron line, e.g. `0 */2 * * 1-5 cd /path && python3 run.py --notify`.

## Host the phone app (PWA)

Serve the `app/` folder over HTTPS, open it on your phone, and **"Add to Home Screen."**
- Quick test: `python -m http.server 8080 --directory app` then visit `http://<pc-ip>:8080`.
- Real hosting: Cloudflare Pages / your Oracle VM behind Caddy. The engine writes
  `app/alerts.json` on each run, so the app stays current.

---

## Architecture

```
SEC EDGAR getcurrent (Form 4)  ┐
USAspending spending_by_award  ┼─► engine ─► SQLite (cluster memory) ─► scoring ─► app/alerts.json
SEC submissions (sector/SIC)   ┘                                                   │
                                                                    ┌──────────────┴──────────────┐
                                                              Telegram push                  PWA (app/)
```

- `sec_insiders.py` — Form 4 feed → open-market "P" buys (XML hardened with `defusedxml`)
- `contracts.py` — USAspending awards (experimental) · `sectors.py` — ticker→sector + strict name match
- `scoring.py` — **your knob**: weights that decide what alerts you (back-test before trusting)
- `storage.py` — SQLite · `notify.py` — Telegram · `pipeline.py` / `run.py` — orchestration

## Tuning — the one part that's yours

`scoring.py` is the knob. The deep-research found **no** verified scoring recipe, so the
default weights are a starting point to **back-test**, not gospel. Edit the weights and the
"why it matters" wording to match how you want to trade and learn.

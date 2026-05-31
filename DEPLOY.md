# Put it online, always-on (free) — GitHub Actions + Pages

This hosts your PWA 24/7 and refreshes the data twice a weekday — **no server, $0**. The
GitHub Actions runner executes the Python engines, commits the updated `app/*.json`, and
publishes the `app/` folder to GitHub Pages.

## One-time setup (~10 min)
1. **Create a GitHub repo** (private is fine) and push this folder:
   ```
   cd C:\Users\Owner\OneDrive\stock-alert-app
   git init && git add . && git commit -m "smart-money alerts"
   git branch -M main
   git remote add origin https://github.com/<you>/stock-alert-app.git
   git push -u origin main
   ```
2. **Add secrets** — repo → Settings → Secrets and variables → Actions → New secret:
   - `SEC_USER_AGENT` = `StockAlerts your-real-email@gmail.com`  (required)
   - `FMP_API_KEY` = your free FMP key  (optional — turns on the value gate + Politicians tab)
3. **Enable Pages** — repo → Settings → Pages → Source = **GitHub Actions**.
4. **Run it once** — repo → Actions → "refresh-and-deploy" → **Run workflow**.
   Your app goes live at `https://<you>.github.io/stock-alert-app/`.
5. **On your phone**, open that URL → **Add to Home Screen**. Done — it self-updates twice a day.

## What refreshes automatically
`macro.py` (live de-risk + CAPE) · `run.py` (insider clusters + contracts) ·
`billionaires.py` (13F) · `politicians.py` (congress, if FMP key set).
Times: ~6am & ~4pm ET, weekdays (edit the `cron:` lines in `.github/workflows/refresh-and-deploy.yml`).

## Telegram push (optional)
GitHub Actions can also push alerts: add `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` secrets and
change `python run.py` to `python run.py --notify` in the workflow.

## Alternative: your Hostinger VPS / Oracle VM
If you'd rather host on the VPS you already run n8n on: serve `app/` behind Caddy/Nginx and add a
cron line `0 11,21 * * 1-5 cd /path && python3 macro.py && python3 run.py && python3 billionaires.py && python3 politicians.py`.
GitHub Pages is simpler and needs no server upkeep, so start there unless you want everything on one box.

## Privacy note
A **private** repo keeps your watchlist/config private while Pages still serves the app publicly at an
obscure URL. Don't commit a real `.env` (it's covered by `.gitignore`); use Actions **secrets** instead.

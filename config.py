"""Central config. Reads a local .env if present (no external deps)."""
import os


def _load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

# SEC REQUIRES a descriptive User-Agent with contact info or it returns HTTP 403.
# >>> CHANGE the email to a real one you control. <<<
USER_AGENT = os.environ.get("SEC_USER_AGENT", "StockAlertApp personal-use you@example.com")

# Optional. Adds the "undervalued" gate (the "Both" mode). Without it, alerts are catalyst-only.
FMP_API_KEY = os.environ.get("FMP_API_KEY", "").strip()

# Optional. Without these, alerts are written to disk but not pushed to your phone.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# --- tunables ---
INSIDER_FEED_COUNT = int(os.environ.get("INSIDER_FEED_COUNT", "80"))
CLUSTER_LOOKBACK_DAYS = int(os.environ.get("CLUSTER_LOOKBACK_DAYS", "7"))
MIN_CLUSTER_INSIDERS = int(os.environ.get("MIN_CLUSTER_INSIDERS", "2"))
MIN_CONTRACT_USD = float(os.environ.get("MIN_CONTRACT_USD", "10000000"))   # $10M
CONTRACT_LOOKBACK_DAYS = int(os.environ.get("CONTRACT_LOOKBACK_DAYS", "5"))
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "0.12"))            # SEC fair-access: <10 req/s
DB_PATH = os.environ.get("DB_PATH", "alerts.db")
ALERTS_JSON = os.environ.get("ALERTS_JSON", "app/alerts.json")

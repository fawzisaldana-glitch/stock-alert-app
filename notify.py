"""Telegram push. No-op (returns False) until you set a bot token + chat id."""
import config
import fetch


def send(text):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        fetch.post_json(url, {"chat_id": config.TELEGRAM_CHAT_ID, "text": text,
                              "parse_mode": "Markdown", "disable_web_page_preview": True})
        return True
    except Exception as e:
        print("  [telegram] send failed:", e)
        return False

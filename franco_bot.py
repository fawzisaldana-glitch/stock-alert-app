"""Franco Roofing Telegram alert bot — registers recipients, broadcasts lead alerts.

Telegram bots CANNOT message a phone number directly: each person must open the bot
and tap Start once. After that this module knows their chat id and can push alerts
forever. Verification is automatic:
  - phone allowlist  (FRANCO_ALLOWED_PHONES): user taps "Share my number" and, if it
    matches, they're in. Telegram sends the account's own verified number, and we
    reject forwarded contact cards, so this can't be spoofed by typing a number.
  - join code        (FRANCO_JOIN_CODE): fallback passphrase, e.g. for yourself.
  - if NEITHER is configured, anyone who finds the bot can register (warned loudly).

CLI:
  python franco_bot.py run          # long-poll loop: handles Start/verify live
  python franco_bot.py register     # one-shot: drain pending messages, then exit
  python franco_bot.py send "..."   # broadcast a message to everyone registered
  python franco_bot.py test         # broadcast a canned test alert
  python franco_bot.py status       # list registered recipients

Other code can `import franco_bot; franco_bot.broadcast("New lead: ...")`.
Recipients persist in franco_state/recipients.json (gitignored — contains chat ids).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import truststore
    truststore.inject_into_ssl()      # OS cert store, same rationale as fetch.py
except Exception:
    pass


def _load_env(path=".env"):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

BOT_TOKEN = os.environ.get("FRANCO_BOT_TOKEN", "").strip()
ALLOWED_PHONES = [p for p in re.split(r"[,;]", os.environ.get("FRANCO_ALLOWED_PHONES", "")) if p.strip()]
JOIN_CODE = os.environ.get("FRANCO_JOIN_CODE", "").strip()
STATE_PATH = os.environ.get("FRANCO_STATE_PATH", os.path.join("franco_state", "recipients.json"))

WELCOME = "👋 This is the Franco Roofing alert bot. New leads and updates land here."


# ── state ─────────────────────────────────────────────────────────────────────

def _load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"last_update_id": 0, "recipients": {}}


def _save_state(state):
    d = os.path.dirname(STATE_PATH)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


# ── telegram api ──────────────────────────────────────────────────────────────

class TelegramError(RuntimeError):
    def __init__(self, code, description):
        super().__init__(f"telegram HTTP {code}: {description}")
        self.code, self.description = code, description


def _api(method, params=None, timeout=35):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    req = Request(url, data=json.dumps(params or {}).encode("utf-8"),
                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read())
    except HTTPError as e:
        try:
            desc = json.loads(e.read()).get("description", "")
        except Exception:
            desc = ""
        raise TelegramError(e.code, desc) from None
    if not out.get("ok"):
        raise TelegramError(0, out.get("description", "unknown"))
    return out["result"]


def _send(chat_id, text, reply_markup=None):
    params = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_markup:
        params["reply_markup"] = reply_markup
    return _api("sendMessage", params)


# ── verification ──────────────────────────────────────────────────────────────

def _digits(s):
    return re.sub(r"\D", "", s or "")


def _phone_allowed(phone):
    """Compare on the last 10 digits so '+1 (510) 246-7438' matches '15102467438'."""
    d = _digits(phone)
    if not d:
        return False
    for allowed in ALLOWED_PHONES:
        a = _digits(allowed)
        if a and ((len(d) >= 10 and len(a) >= 10 and d[-10:] == a[-10:]) or d == a):
            return True
    return False


def _open_registration():
    return not ALLOWED_PHONES and not JOIN_CODE


def _contact_keyboard():
    return {"keyboard": [[{"text": "📱 Share my number to verify", "request_contact": True}]],
            "resize_keyboard": True, "one_time_keyboard": True}


def _verify_prompt():
    ways = []
    if ALLOWED_PHONES:
        ways.append("tap the “📱 Share my number” button below")
    if JOIN_CODE:
        ways.append("send the join code you were given")
    return "To start receiving alerts, " + " — or — ".join(ways) + "."


# ── registration flow ─────────────────────────────────────────────────────────

def _register(state, chat, from_, via, phone=None):
    rec = {"chat_id": chat["id"],
           "name": " ".join(x for x in [from_.get("first_name"), from_.get("last_name")] if x),
           "username": from_.get("username", ""),
           "phone": _digits(phone) if phone else "",
           "via": via, "active": True,
           "joined": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    state["recipients"][str(chat["id"])] = rec
    print(f"  [franco] registered {rec['name'] or rec['username'] or chat['id']} (chat {chat['id']}, via {via})")
    _send(chat["id"], "✅ You're in! Franco Roofing alerts will arrive in this chat.\n"
                      "Commands: /status · /test · /stop", reply_markup={"remove_keyboard": True})


def _handle_update(state, upd):
    msg = upd.get("message") or {}
    chat, from_ = msg.get("chat") or {}, msg.get("from") or {}
    if chat.get("type") != "private" or not from_ or from_.get("is_bot"):
        return
    cid = str(chat["id"])
    rec = state["recipients"].get(cid)
    text = (msg.get("text") or "").strip()
    contact = msg.get("contact")

    if text.startswith("/start"):
        if rec:
            rec["active"] = True
            _send(chat["id"], "✅ You're already registered — alerts are on. (/stop to pause)")
        elif _open_registration():
            _send(chat["id"], WELCOME)
            _register(state, chat, from_, via="open")
        else:
            kb = _contact_keyboard() if ALLOWED_PHONES else None
            _send(chat["id"], WELCOME + "\n\n" + _verify_prompt(), reply_markup=kb)
        return

    if text == "/stop":
        if rec:
            rec["active"] = False
            _send(chat["id"], "🔕 Paused. Send /start to turn alerts back on.")
        return

    if text == "/status":
        n = sum(1 for r in state["recipients"].values() if r["active"])
        mine = "✅ Registered" if rec and rec["active"] else ("🔕 Paused" if rec else "❌ Not registered")
        _send(chat["id"], f"{mine} — {n} recipient(s) currently get alerts.")
        return

    if text == "/test":
        if rec and rec["active"]:
            who = rec["name"] or rec["username"] or cid
            broadcast(f"🔔 Test alert from the Franco Roofing bot (requested by {who}). "
                      f"If you can read this, you're wired up.", state=state)
        else:
            _send(chat["id"], "Register first — send /start.")
        return

    if contact and not rec:
        # only the sender's OWN contact card counts — a forwarded card has a different user_id
        if contact.get("user_id") != from_.get("id"):
            _send(chat["id"], "Please share your own number with the button, not a forwarded contact.")
        elif _phone_allowed(contact.get("phone_number")):
            _register(state, chat, from_, via="phone", phone=contact.get("phone_number"))
        else:
            _send(chat["id"], "That number isn't on the approved list. "
                              "Ask the person who set up the bot to add you.")
        return

    if not rec and text and not text.startswith("/"):
        if JOIN_CODE and text.casefold() == JOIN_CODE.casefold():
            _register(state, chat, from_, via="code")
        elif JOIN_CODE:
            _send(chat["id"], "That code didn't match. Try again, or "
                              + ("share your number with the button below." if ALLOWED_PHONES else "check with the bot owner."),
                  reply_markup=_contact_keyboard() if ALLOWED_PHONES else None)
        elif ALLOWED_PHONES:
            _send(chat["id"], "Tap the “📱 Share my number” button to verify.", reply_markup=_contact_keyboard())


# ── broadcast ─────────────────────────────────────────────────────────────────

def broadcast(text, state=None):
    """Send `text` to every active recipient. Returns how many sends succeeded."""
    own_state = state is None
    if own_state:
        state = _load_state()
    ok = 0
    for cid, rec in list(state["recipients"].items()):
        if not rec.get("active"):
            continue
        label = rec.get("name") or rec.get("username") or cid
        try:
            _send(rec["chat_id"], text)
            ok += 1
            print(f"  [franco] sent → {label}")
        except TelegramError as e:
            if e.code == 403:                       # user blocked the bot
                rec["active"] = False
                print(f"  [franco] {label} blocked the bot — deactivated")
            else:
                print(f"  [franco] send to {label} failed: {e}")
        except (URLError, OSError) as e:
            print(f"  [franco] send to {label} failed: {e}")
    if own_state:
        _save_state(state)
    return ok


# ── polling ───────────────────────────────────────────────────────────────────

def _poll(state, long=True):
    """One getUpdates round. Returns number of updates processed."""
    params = {"offset": state["last_update_id"] + 1, "allowed_updates": ["message"]}
    if long:
        params["timeout"] = 50
    updates = _api("getUpdates", params, timeout=65 if long else 35)
    for upd in updates:
        state["last_update_id"] = max(state["last_update_id"], upd["update_id"])
        try:
            _handle_update(state, upd)
        except TelegramError as e:
            print("  [franco] handler error:", e)
    if updates:
        _save_state(state)
    return len(updates)


def _startup_banner():
    me = _api("getMe")
    print(f"[franco] bot @{me['username']} connected — people join at t.me/{me['username']}")
    if _open_registration():
        print("[franco] ⚠ OPEN REGISTRATION: set FRANCO_ALLOWED_PHONES and/or FRANCO_JOIN_CODE in .env")
    return me


def run_loop():
    _startup_banner()
    state = _load_state()
    print(f"[franco] {sum(1 for r in state['recipients'].values() if r['active'])} active recipient(s). "
          "Polling — Ctrl+C to stop.")
    while True:
        try:
            _poll(state, long=True)
        except KeyboardInterrupt:
            _save_state(state)
            print("\n[franco] stopped.")
            return
        except TelegramError as e:
            if e.code == 409:
                print("[franco] another poller/webhook is active for this token — stop it first:", e.description)
            elif e.code == 401:
                print("[franco] bad FRANCO_BOT_TOKEN — recheck the token from @BotFather")
                return
            else:
                print("[franco] poll error:", e)
            import time; time.sleep(3)
        except (URLError, OSError) as e:
            print("[franco] network hiccup:", e)
            import time; time.sleep(3)


def register_once():
    _startup_banner()
    state = _load_state()
    before = len(state["recipients"])
    while _poll(state, long=False):
        pass
    _save_state(state)
    print(f"[franco] done — {len(state['recipients']) - before} new, "
          f"{sum(1 for r in state['recipients'].values() if r['active'])} active total.")


def print_status():
    state = _load_state()
    if not state["recipients"]:
        print("[franco] nobody registered yet — run `python franco_bot.py run`, then have each "
              "person open the bot on Telegram and tap Start.")
        return
    for rec in state["recipients"].values():
        flag = "✅" if rec["active"] else "🔕"
        who = rec["name"] or "?"
        user = f"@{rec['username']}" if rec["username"] else ""
        print(f"  {flag} {who} {user}  chat={rec['chat_id']}  via={rec['via']}  joined={rec['joined']}")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "run"
    if not BOT_TOKEN:
        print("Set FRANCO_BOT_TOKEN in .env first (token from @BotFather). See FRANCO_BOT.md.")
        return 1
    if cmd == "run":
        run_loop()
    elif cmd == "register":
        register_once()
    elif cmd == "status":
        print_status()
    elif cmd == "send":
        text = " ".join(argv[2:]).strip()
        if not text:
            print('Usage: python franco_bot.py send "message text"')
            return 1
        n = broadcast(text)
        print(f"[franco] delivered to {n} recipient(s).")
        return 0 if n else 1
    elif cmd == "test":
        n = broadcast("🔔 Test alert from the Franco Roofing bot — you're wired up.")
        print(f"[franco] delivered to {n} recipient(s).")
        return 0 if n else 1
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

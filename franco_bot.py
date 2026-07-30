"""Franco Roofing Telegram update hub — two-way bot + daily/weekly digests.

Everything for keeping the Franco Roofing side (you + whoever runs their Telegram)
updated in one chat:
  - INSTANT posts: any verified member just messages the bot → it relays to everyone
    else ("💬 Andres: crew finished the Fruitvale job").
  - DAILY digest: notes queued via /note (or `franco_bot.py note` from scripts/n8n)
    go out as ONE message at FRANCO_DAILY_AT (default 09:00, FRANCO_TZ).
  - WEEKLY recap: everything posted/digested in the last 7 days, Monday morning.

Telegram bots CANNOT message a phone number directly: each person must open the bot
and tap Start once. Verification is automatic:
  - phone allowlist  (FRANCO_ALLOWED_PHONES): tap "Share my number" — Telegram sends
    the account's own verified number and forwarded contact cards are rejected.
  - join code        (FRANCO_JOIN_CODE): fallback passphrase.
  Verified members are admins (can post/relay). If NEITHER check is configured,
  anyone who finds the bot can register (warned loudly) — as receive-only.

CLI:
  python franco_bot.py run           # long-poll loop: live commands + scheduled digests
  python franco_bot.py register      # one-shot: drain pending messages, then exit
  python franco_bot.py send "..."    # broadcast now (also lands in the weekly recap)
  python franco_bot.py note "..."    # queue an item for the next daily digest
  python franco_bot.py digest daily|weekly   # send a digest now (for cron/n8n setups)
  python franco_bot.py test          # canned test alert
  python franco_bot.py status        # recipients + queue

Other code can `import franco_bot; franco_bot.broadcast("New lead: ...")`.
State persists in franco_state/recipients.json (gitignored — chat ids live there).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
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
DAILY_AT = os.environ.get("FRANCO_DAILY_AT", "09:00")
WEEKLY_AT = os.environ.get("FRANCO_WEEKLY_AT", "mon 09:00")
TZ_NAME = os.environ.get("FRANCO_TZ", "America/Los_Angeles")

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(TZ_NAME)
except Exception:                     # no tz database (Windows: pip install tzdata)
    print(f"[franco] ⚠ timezone '{TZ_NAME}' unavailable — digests will use UTC "
          "(on Windows: pip install tzdata)")
    TZ = timezone.utc

WELCOME = ("👋 This is the Franco Roofing update hub — leads, job updates, and the "
           "daily/weekly digests land here. Members can post by simply messaging this chat.")
COMMANDS = "Commands: /status · /note <text> · /digest · /test · /stop"
ARCHIVE_DAYS = 30                     # weekly recap needs 7; keep a month for reference


def _now():
    return datetime.now(TZ)


# ── state ─────────────────────────────────────────────────────────────────────

def _load_state():
    state = {"last_update_id": 0, "recipients": {}, "queue": [], "archive": [],
             "last_daily": "", "last_weekly": ""}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            state.update(json.load(f))
    return state


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
    return "To join, " + " — or — ".join(ways) + "."


# ── registration flow ─────────────────────────────────────────────────────────

def _label(rec):
    return rec.get("name") or rec.get("username") or str(rec.get("chat_id"))


def _register(state, chat, from_, via, phone=None):
    rec = {"chat_id": chat["id"],
           "name": " ".join(x for x in [from_.get("first_name"), from_.get("last_name")] if x),
           "username": from_.get("username", ""),
           "phone": _digits(phone) if phone else "",
           "via": via, "admin": via in ("phone", "code"), "active": True,
           "joined": _now().isoformat(timespec="seconds")}
    state["recipients"][str(chat["id"])] = rec
    print(f"  [franco] registered {_label(rec)} (chat {chat['id']}, via {via}"
          f"{', admin' if rec['admin'] else ''})")
    _send(chat["id"], "✅ You're in! Franco Roofing updates arrive in this chat"
                      + (", and anything you type here goes out to the whole team." if rec["admin"] else ".")
                      + "\n" + COMMANDS, reply_markup={"remove_keyboard": True})


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
            _send(chat["id"], "✅ You're already in — updates are on. (/stop to pause)")
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
            _send(chat["id"], "🔕 Paused. Send /start to turn updates back on.")
        return

    if text == "/status":
        n = sum(1 for r in state["recipients"].values() if r["active"])
        mine = "✅ Member" if rec and rec["active"] else ("🔕 Paused" if rec else "❌ Not registered")
        _send(chat["id"], f"{mine} — {n} recipient(s), {len(state['queue'])} note(s) queued "
                          f"for the next daily digest.")
        return

    if text == "/test":
        if rec and rec["active"]:
            broadcast(f"🔔 Test alert from the Franco Roofing bot (requested by {_label(rec)}). "
                      f"If you can read this, you're wired up.", state=state)
        else:
            _send(chat["id"], "Join first — send /start.")
        return

    if text.startswith("/note"):
        body = text[len("/note"):].strip()
        if not (rec and rec["active"]):
            _send(chat["id"], "Join first — send /start.")
        elif not body:
            _send(chat["id"], "Usage: /note crew needs more shingles for the Alameda job")
        else:
            state["queue"].append({"ts": _now().isoformat(timespec="seconds"),
                                   "text": body, "by": _label(rec)})
            _send(chat["id"], "📝 Noted — goes out with the next daily digest (or /digest to send now).")
        return

    if text == "/digest":
        if not (rec and rec["active"] and rec.get("admin")):
            _send(chat["id"], "Only members who joined with a verified number or the join code can do that.")
        elif not state["queue"]:
            _send(chat["id"], "Nothing queued right now — add items with /note first.")
        else:
            flush_daily(state, on_demand=True)
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
        return

    # plain text from a member = post it to everyone else, and into the weekly recap
    if rec and rec["active"] and text and not text.startswith("/"):
        if rec.get("admin"):
            n = broadcast(f"💬 {_label(rec)}: {text}", state=state,
                          exclude_chat_id=chat["id"], archive_as=_label(rec), archive_text=text)
            _send(chat["id"], f"✓ Sent to {n} other member(s)." if n
                  else "✓ Logged for the weekly recap — nobody else is registered yet.")
        else:
            _send(chat["id"], "Only verified members can post updates — you'll keep receiving them here.")
        return

    if rec and text.startswith("/"):
        _send(chat["id"], COMMANDS)


# ── broadcast ─────────────────────────────────────────────────────────────────

def broadcast(text, state=None, exclude_chat_id=None, archive_as=None, archive_text=None):
    """Send `text` to every active recipient. Returns how many sends succeeded.

    archive_as: attribution to store in the weekly-recap archive ("" = no attribution,
    None = don't archive). archive_text overrides what gets archived (e.g. without
    the "💬 name:" prefix the live relay carries)."""
    own_state = state is None
    if own_state:
        state = _load_state()
    ok = 0
    for cid, rec in list(state["recipients"].items()):
        if not rec.get("active") or rec["chat_id"] == exclude_chat_id:
            continue
        try:
            _send(rec["chat_id"], text)
            ok += 1
            print(f"  [franco] sent → {_label(rec)}")
        except TelegramError as e:
            if e.code == 403:                       # user blocked the bot
                rec["active"] = False
                print(f"  [franco] {_label(rec)} blocked the bot — deactivated")
            else:
                print(f"  [franco] send to {_label(rec)} failed: {e}")
        except (URLError, OSError) as e:
            print(f"  [franco] send to {_label(rec)} failed: {e}")
    if archive_as is not None:
        state["archive"].append({"ts": _now().isoformat(timespec="seconds"),
                                 "text": archive_text if archive_text is not None else text,
                                 "by": archive_as})
        _prune_archive(state)
    if own_state:
        _save_state(state)
    return ok


# ── digests ───────────────────────────────────────────────────────────────────

def _prune_archive(state):
    cutoff = _now() - timedelta(days=ARCHIVE_DAYS)
    state["archive"] = [a for a in state["archive"]
                        if datetime.fromisoformat(a["ts"]) >= cutoff]


def _bullets(items, stamp):
    out = []
    for it in items[:30]:
        t = datetime.fromisoformat(it["ts"]).astimezone(TZ)
        by = f" — {it['by']}" if it.get("by") else ""
        out.append(f"• {t.strftime(stamp)} · {it['text']}{by}")
    if len(items) > 30:
        out.append(f"…and {len(items) - 30} more")
    return "\n".join(out)


def flush_daily(state, on_demand=False):
    """Send queued notes as one digest; move them to the recap archive."""
    now = _now()
    state["last_daily"] = now.date().isoformat()
    if not state["queue"]:
        print("  [franco] daily digest: queue empty — skipped")
        return 0
    head = f"🏠 Franco Roofing — Daily update · {now.strftime('%a %b %d')}"
    if on_demand:
        head += " (on demand)"
    n = broadcast(head + "\n" + _bullets(state["queue"], "%H:%M"), state=state)
    state["archive"].extend(state["queue"])
    state["queue"] = []
    _prune_archive(state)
    return n


def flush_weekly(state):
    """Recap everything posted or digested in the last 7 days."""
    now = _now()
    iso = now.isocalendar()
    state["last_weekly"] = f"{iso[0]}-W{iso[1]:02d}"
    cutoff = now - timedelta(days=7)
    items = [a for a in state["archive"] if datetime.fromisoformat(a["ts"]) >= cutoff]
    items += state["queue"]           # not yet digested, but part of the week
    if not items:
        print("  [franco] weekly recap: quiet week — skipped")
        return 0
    head = (f"📅 Franco Roofing — Week in review · "
            f"{cutoff.strftime('%b %d')}–{now.strftime('%b %d')}\n"
            f"{len(items)} update(s) this week:")
    return broadcast(head + "\n" + _bullets(items, "%a"), state=state)


def _parse_hhmm(s, fallback=(9, 0)):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s.strip())
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return int(m.group(1)), int(m.group(2))
    return fallback


_WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse_weekly(s):
    parts = s.strip().casefold().split()
    day = _WEEKDAYS.get(parts[0][:3], 0) if parts else 0
    h, m = _parse_hhmm(parts[1] if len(parts) > 1 else "", fallback=(9, 0))
    return day, h, m


def _maybe_scheduled(state):
    """Called each poll round: fire daily/weekly digests when their time has passed."""
    now = _now()
    h, m = _parse_hhmm(DAILY_AT)
    if state["last_daily"] != now.date().isoformat() and (now.hour, now.minute) >= (h, m):
        flush_daily(state)
        _save_state(state)
    wd, wh, wm = _parse_weekly(WEEKLY_AT)
    iso = now.isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    if state["last_weekly"] != week and now.weekday() == wd and (now.hour, now.minute) >= (wh, wm):
        flush_weekly(state)
        _save_state(state)


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
    d, w = _parse_hhmm(DAILY_AT), _parse_weekly(WEEKLY_AT)
    print(f"[franco] {sum(1 for r in state['recipients'].values() if r['active'])} active recipient(s). "
          f"Daily digest {d[0]:02d}:{d[1]:02d}, weekly {WEEKLY_AT} ({TZ_NAME}). Polling — Ctrl+C to stop.")
    while True:
        try:
            _poll(state, long=True)
            _maybe_scheduled(state)
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
            time.sleep(3)
        except (URLError, OSError) as e:
            print("[franco] network hiccup:", e)
            time.sleep(3)


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
        user = f"@{rec['username']}" if rec["username"] else ""
        role = "admin" if rec.get("admin") else "receive-only"
        print(f"  {flag} {_label(rec)} {user}  chat={rec['chat_id']}  {role}  via={rec['via']}  joined={rec['joined']}")
    print(f"  queue: {len(state['queue'])} note(s) · archive: {len(state['archive'])} item(s) "
          f"· last daily: {state['last_daily'] or '—'} · last weekly: {state['last_weekly'] or '—'}")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "status":               # works offline
        print_status()
        return 0
    if not BOT_TOKEN:
        print("Set FRANCO_BOT_TOKEN in .env first (token from @BotFather). See FRANCO_BOT.md.")
        return 1
    if cmd == "run":
        run_loop()
    elif cmd == "register":
        register_once()
    elif cmd == "send":
        text = " ".join(argv[2:]).strip()
        if not text:
            print('Usage: python franco_bot.py send "message text"')
            return 1
        n = broadcast(text, archive_as="")
        print(f"[franco] delivered to {n} recipient(s).")
        return 0 if n else 1
    elif cmd == "note":
        text = " ".join(argv[2:]).strip()
        if not text:
            print('Usage: python franco_bot.py note "goes out with the next daily digest"')
            return 1
        state = _load_state()
        state["queue"].append({"ts": _now().isoformat(timespec="seconds"), "text": text, "by": ""})
        _save_state(state)
        print(f"[franco] queued ({len(state['queue'])} note(s) pending).")
    elif cmd == "digest":
        which = argv[2] if len(argv) > 2 else "daily"
        state = _load_state()
        n = flush_weekly(state) if which == "weekly" else flush_daily(state, on_demand=True)
        _save_state(state)
        print(f"[franco] {which} digest delivered to {n} recipient(s).")
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

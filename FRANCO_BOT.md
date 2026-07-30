# Franco Roofing Telegram Update Hub

One bot, one purpose: keep everyone on the Franco Roofing side updated — you and
whoever manages their Telegram. Completely separate from the stock-alert push: its own
bot token, its own recipient list (`franco_state/`, never committed).

Three ways updates flow:

1. **Instant posts** — any verified member just *messages the bot* and it relays to
   everyone else: `💬 Andres: crew finished the Fruitvale job`. Works both directions;
   the bot is a tiny private team channel.
2. **Daily digest** — notes queued with `/note` (or by scripts/n8n via
   `franco_bot.py note`) go out as **one** tidy message at `FRANCO_DAILY_AT`
   (default 09:00 Pacific) instead of drip-spamming all day.
3. **Weekly recap** — Monday morning roll-up of everything posted or digested in the
   last 7 days.

> **The one thing Telegram won't let a bot do:** message a phone number out of the blue.
> Each person opens the bot and taps **Start** once — after that the bot can push to them
> forever. Verification is automatic (below), so onboarding is ~20 seconds.

## Setup (once)

1. You already made the bot with **@BotFather** — put its token in `.env`:
   ```
   FRANCO_BOT_TOKEN=123456:ABC-your-token
   FRANCO_ALLOWED_PHONES=+15105551234        # numbers auto-approved on "Share my number"
   FRANCO_JOIN_CODE=some-passphrase          # fallback: send this word to the bot to join
   FRANCO_TZ=America/Los_Angeles             # digest clock (default shown)
   FRANCO_DAILY_AT=09:00                     # daily digest time (default shown)
   FRANCO_WEEKLY_AT=mon 09:00                # weekly recap slot (default shown)
   ```
   `FRANCO_ALLOWED_PHONES` is comma-separated; spaces/dashes/parens are fine.
   Real numbers live only in your local `.env` — never commit them.
2. Start the bot:
   ```
   python franco_bot.py run
   ```
   It prints the bot's `t.me/...` link. The `run` loop is also what fires the
   scheduled digests, so on a VPS keep it running (tmux/systemd/pm2). No always-on
   machine? See "cron mode" below.
3. Each member opens the `t.me/...` link → **Start** → taps **"📱 Share my number"**
   (auto-approved if the number is in `FRANCO_ALLOWED_PHONES`) or types the join code.
   Everyone verified this way is an **admin**: they receive *and* can post.

Message to forward to a teammate:

> Tap this link → t.me/YOUR_BOT_USERNAME → press **Start** → tap **"📱 Share my number
> to verify"**. Done — Franco Roofing updates arrive there, and anything you type in
> that chat goes out to the team.

## Sending updates

```
python franco_bot.py send "🏠 New lead: Maria G — roof leak, Oakland — call back today"
python franco_bot.py note "supplier confirmed Tuesday delivery"     # → next daily digest
python franco_bot.py digest daily      # flush the note queue now
python franco_bot.py digest weekly     # send the 7-day recap now
python franco_bot.py test              # canned test message
python franco_bot.py status           # members, queue, last digest times
```

From Python: `import franco_bot; franco_bot.broadcast("🏠 New lead: ...")`.
Everything `send`-ed or posted also lands in the weekly recap automatically.

**From n8n:** an Execute Command node running `python franco_bot.py send "{{...}}"`
(instant) or `... note "{{...}}"` (batched into the daily digest). Direct HTTP works
too: `https://api.telegram.org/bot<TOKEN>/sendMessage` with a `chat_id` from
`python franco_bot.py status`.

**Cron mode (no always-on `run` loop):** register people with one-shot
`python franco_bot.py register` after they message the bot, then schedule
`digest daily` / `digest weekly` from cron, Task Scheduler, or n8n — e.g.
`0 9 * * * cd /path && python3 franco_bot.py digest daily`.

## In-chat commands

| Command | Effect |
|---|---|
| *(any plain text)* | Admins: posted to every other member + logged for the weekly recap |
| `/note <text>` | Queue an item for the next daily digest |
| `/digest` | Flush the queued notes now (admins) |
| `/status` | Membership, recipient count, queued notes |
| `/test` | Send a test alert to everyone |
| `/stop` / `/start` | Pause / resume updates for that person |

## Troubleshooting

- **409 Conflict** on `run` — something else is polling this token (another `run`
  window, or a webhook set by n8n). Stop the other poller, or delete the webhook:
  `https://api.telegram.org/bot<TOKEN>/deleteWebhook`.
- **401** — token typo; recheck with @BotFather.
- **Digests at the wrong time / UTC warning on Windows** — `pip install tzdata`
  (Windows has no built-in IANA timezone database).
- **Someone stopped getting updates** — they may have blocked the bot (it deactivates
  them automatically; `status` shows 🔕). They send `/start` to rejoin.
- **"That number isn't on the approved list"** — add it to `FRANCO_ALLOWED_PHONES`
  in `.env` (or give them the join code) and have them try again.
- **Missed a digest because the machine was off** — the loop back-fills the same day
  when it comes up; for a fully-off day, `python franco_bot.py digest daily` sends
  whatever is still queued.

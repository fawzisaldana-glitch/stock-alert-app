# Franco Roofing Telegram Bot

Pushes Franco Roofing alerts (new leads, job updates, anything) to everyone registered —
you and whoever manages the business Telegram. Completely separate from the stock-alert
push: its own bot token, its own recipient list (`franco_state/`, never committed).

> **The one thing Telegram won't let a bot do:** message a phone number out of the blue.
> Each person opens the bot and taps **Start** once — after that the bot can push to them
> forever. Verification is automatic (details below), so onboarding is ~20 seconds.

## Setup (once)

1. You already made the bot with **@BotFather** — put its token in `.env`:
   ```
   FRANCO_BOT_TOKEN=123456:ABC-your-token
   FRANCO_ALLOWED_PHONES=+15105551234        # numbers auto-approved on "Share my number"
   FRANCO_JOIN_CODE=some-passphrase          # fallback: send this word to the bot to join
   ```
   `FRANCO_ALLOWED_PHONES` is comma-separated; spaces/dashes/parens are fine.
   Real numbers live only in your local `.env` — never commit them.
2. Start the bot listener:
   ```
   python franco_bot.py run
   ```
   It prints the bot's `t.me/...` link. Leave it running while people join
   (afterwards it only needs to run when you want interactive commands —
   sending alerts works without it).
3. Each recipient opens the `t.me/...` link → **Start** → taps **“📱 Share my number”**
   (auto-approved if the number is in `FRANCO_ALLOWED_PHONES`) or types the join code.

Message to forward to a teammate:

> Tap this link → t.me/YOUR_BOT_USERNAME → press **Start** → tap **“📱 Share my number to
> verify”**. That's it — Franco Roofing alerts will show up in that chat.

No always-on machine? Skip `run`: have people message the bot, then execute
`python franco_bot.py register` — it drains the pending messages, verifies and
registers everyone, and exits. Re-run it any time someone new joins.

## Sending alerts

```
python franco_bot.py send "🏠 New lead: Maria G — roof leak, Oakland — call back today"
python franco_bot.py test                 # canned test message to everyone
python franco_bot.py status               # who's registered
```

From Python:

```python
import franco_bot
franco_bot.broadcast("🏠 New lead: ...")
```

From **n8n**: an Execute Command node running `python franco_bot.py send "{{...}}"`,
or an HTTP Request node calling Telegram directly
(`https://api.telegram.org/bot<TOKEN>/sendMessage` with a `chat_id` from
`python franco_bot.py status`) — the bot file is just the easy way to hit all
recipients at once.

## In-chat commands

| Command | Effect |
|---|---|
| `/start` | Join (with verification) or resume alerts |
| `/stop` | Pause alerts for that person |
| `/status` | Am I registered + how many recipients |
| `/test` | Send a test alert to everyone (registered users only) |

## Troubleshooting

- **409 Conflict** on `run` — something else is polling this token (another `run`
  window, or a webhook set by n8n). Stop the other poller, or delete the webhook:
  `https://api.telegram.org/bot<TOKEN>/deleteWebhook`.
- **401** — token typo; recheck with @BotFather.
- **Someone stopped getting alerts** — they may have blocked the bot (the bot
  deactivates them automatically; `status` shows 🔕). They send `/start` to rejoin.
- **“That number isn't on the approved list”** — add it to `FRANCO_ALLOWED_PHONES`
  in `.env` (or give them the join code) and have them try again.

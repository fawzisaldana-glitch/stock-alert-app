# Bronco Painting — ads workflow: status and launch checklist

**Status as of 2026-08-01: built, never switched on.** Blocked on four values only Fawzi can
supply. This file exists so that blocker stops being described as "a decision" and starts
being four fields with a deadline.

## Why this file exists

`CEO_Brain/HANDOFF.md` (2026-07-21) recorded:

> **Bronco ads brief still never switched on.** […] no daily brief has ever been generated.
> Blocker is a **decision from Fawzi** (confirm ad account + go / or "paused"), not tooling.
> Now the **#1 item for the 4th brief running.**

Four consecutive weekly briefs carried it as the top item without moving, because "confirm the
ad account and go" isn't actionable in five minutes on a phone. The four fields below are.

## Verified state (checked 2026-08-01)

| Component | State |
|---|---|
| `daily-ads-watch` skill | Exists, authored 2026-05-15. Complete — quality scoring, anomaly signals, auto-action safety rules |
| `.bronco-meta-config.md` | **Missing.** Template now at `bronco/.bronco-meta-config.example.md` |
| `daily-ads-watch.log.json` | Never created — no auto-action has ever run |
| Daily 8am cron | **Does not exist.** 50 Routines on the account; all are `send_later` reminders, none scheduled |
| Meta ad account | **Never connected.** Motion returns zero workspaces; Supermetrics Facebook Ads is `NOT_AUTHENTICATED` |
| Creative assets | ~25 generated images/videos in Downloads (`hf_*.png` / `.mp4`, 2026-07-26 → 07-31) |
| Ad playbooks | `meta-ads-painting-contractors-admaker.md`, `meta-ads-high-ticket-contractors.md` (Downloads, 2026-07-27) |
| Ad descriptions (Codex) | **On the local PC, in Buzz.** Not synced to Drive — unreachable from a cloud session |

Corroborating: Motion emailed `broncopainting1820@gmail.com` on 2026-05-21 — *"since you haven't
connected any ad accounts…"* — six days after the skill was written. The account was never wired up.

## The four values that unblock this

Fill these into `bronco/.bronco-meta-config.md` (copy from the `.example.md`):

1. **`meta_ad_account_id`** — `act_…` from Ads Manager → Settings
2. **`campaign_id`** — the campaign the daily watch should monitor
3. **`daily_budget_hard_cap`** — the number the skill may never spend past
4. **`lead_endpoint`** — or explicitly blank, accepting degraded quality scoring

Plus one binary: **go, or paused.** If paused, say so and this drops off the weekly brief
instead of occupying the top slot a fifth time.

## Launch order

1. Fill the four values above. Export `META_ACCESS_TOKEN` in whichever environment runs the schedule.
2. Run `daily-ads-watch` **report-only** (`auto_execute_enabled: false`) for one week. Read the reports.
3. Only if the reports look sane, flip `auto_execute_enabled: true`.
4. Create the daily cron — from an interactive session, since cron-spawned sessions can't create crons:
   ```
   taskId:         bronco-daily-ads-watch
   cronExpression: 0 8 * * *
   prompt:         Run the daily-ads-watch skill for Bronco Painting using
                   bronco/.bronco-meta-config.md. Post the daily report.
   ```
5. Move Codex's ad descriptions out of Buzz to somewhere reachable (Drive, or this repo) so
   creative and copy live together rather than on one machine.

## Note on where this runs

The daily watch needs ad-level pause and budget-change permissions, which means the Meta
Marketing API with `ads_management` — not the Supermetrics connector, which is reporting-only
and campaign-level. Whichever environment holds the token is the one that must run the cron.

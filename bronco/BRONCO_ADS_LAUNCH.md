# Bronco Painting — ads workflow: status and launch checklist

**Status as of 2026-08-02: built, never switched on.** Blocked on four values only Fawzi can
supply. This file exists so that blocker stops being described as "a decision" and starts
being four fields with a deadline.

Those four fields are now machine-checked. Run `python bronco_ads/meta_bridge.py preflight`
— it needs neither a token nor a config file, and prints exactly what is still outstanding.
Every other piece is built and waiting on them.

## Why this file exists

`CEO_Brain/HANDOFF.md` (2026-07-21) recorded:

> **Bronco ads brief still never switched on.** […] no daily brief has ever been generated.
> Blocker is a **decision from Fawzi** (confirm ad account + go / or "paused"), not tooling.
> Now the **#1 item for the 4th brief running.**

Four consecutive weekly briefs carried it as the top item without moving, because "confirm the
ad account and go" isn't actionable in five minutes on a phone. The four fields below are.

## Verified state (re-checked 2026-08-02)

| Component | State |
|---|---|
| `daily-ads-watch` skill | Exists, authored 2026-05-15. Complete — quality scoring, anomaly signals, auto-action safety rules |
| `bronco_ads/` bridge | **Built 2026-08-02.** Read-only Meta reporting: `preflight`, `discover`, `audit`, `report`, `selftest` |
| `.bronco-meta-config.md` | **Missing.** Template at `bronco/.bronco-meta-config.example.md`; `preflight` reports what is unfilled |
| `daily-ads-watch.log.json` | Never created — no auto-action has ever run |
| Daily 8am cron | **Does not exist.** Re-checked across 200 Routines: every one is a one-shot `send_later`, none has a cron expression |
| Meta ad account | **Never connected.** Motion returned zero organizations and zero workspaces on a live call 2026-08-02; Supermetrics Facebook Ads is `NOT_AUTHENTICATED` |
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

1. Add `META_ACCESS_TOKEN` as a repo secret, then run the `bronco-meta` workflow with
   **`discover`**. It lists every ad account, page and pixel the token can reach — that is
   where `meta_ad_account_id` comes from, without digging through Ads Manager on a phone.
2. Fill the four values, either in `bronco/.bronco-meta-config.md` locally or as repository
   **variables** in CI (`BRONCO_META_AD_ACCOUNT_ID`, `BRONCO_CAMPAIGN_ID`,
   `BRONCO_DAILY_BUDGET`, `BRONCO_DAILY_BUDGET_HARD_CAP`, `BRONCO_LEAD_ENDPOINT`). The
   gitignored file does not exist in CI, which is why the variables are the CI route.
3. Run **`preflight`** until it says `READY`, then **`audit`** to confirm the account and
   campaign are the ones you meant.
4. Run `daily-ads-watch` **report-only** (`auto_execute_enabled: false`) for one week. Read
   the reports. The bridge's `report` action gives the same numbers on demand.
5. Only if the reports look sane, flip `auto_execute_enabled: true`. Note that the bridge
   itself still cannot act — see "On the read-only boundary" below.
6. Create the daily cron — from an interactive session, since cron-spawned sessions can't create crons:
   ```
   taskId:         bronco-daily-ads-watch
   cronExpression: 0 8 * * *
   prompt:         Run the daily-ads-watch skill for Bronco Painting using
                   bronco/.bronco-meta-config.md. Post the daily report.
   ```
7. Move Codex's ad descriptions out of Buzz to somewhere reachable (Drive, or this repo) so
   creative and copy live together rather than on one machine. Still outstanding as of
   2026-08-02 — Buzz is on the local PC and no cloud session can read it.

## On the read-only boundary

`bronco_ads/meta_bridge.py` has no POST helper. It cannot pause an ad, move a budget, or
create anything — not because a flag is off, but because the code does not exist. That is
deliberate: step 4 calls for a week of clean report-only runs first, and a capability that
can only be added by a reviewable change is a stronger guarantee than one guarded by a
config value.

Granting it write powers later means adding a `post()` helper and the specific actions
wanted, with the `daily_budget_hard_cap` enforced in code. Until then a token with
`ads_read` alone is enough, and is what should be issued.

## Note on where this runs

The daily watch needs ad-level pause and budget-change permissions, which means the Meta
Marketing API with `ads_management` — not the Supermetrics connector, which is reporting-only
and campaign-level. Whichever environment holds the token is the one that must run the cron.
The reporting bridge above needs only `ads_read`.

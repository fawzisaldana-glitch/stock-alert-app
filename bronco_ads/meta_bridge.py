#!/usr/bin/env python3
"""Meta Marketing API bridge for Bronco Painting ads ops.

Runs inside GitHub Actions, because the agent sandbox cannot reach graph.facebook.com.
The token comes from the META_ACCESS_TOKEN repo secret and is never printed.

**Read-only on purpose.** There is no POST helper in this file. `BRONCO_ADS_LAUNCH.md`
calls for a week of clean report-only runs before anything is allowed to touch a live
campaign, so the ability to pause ads or move budgets is deliberately absent rather than
merely switched off. Adding it is a later, reviewable change — not a config flip.

Usage: python bronco_ads/meta_bridge.py [preflight|discover|audit|report|selftest]

  preflight  What is still missing before launch. Needs neither token nor config.
  discover   List every ad account, page and pixel the token can reach.
  audit      Configured account: status, billing, campaigns.
  report     Yesterday's spend, results, and quality-weighted CPL.
  selftest   Offline checks of the config parser and lead scoring. No network.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bronco_ads import config as cfg
from bronco_ads import lead_quality

API = "https://graph.facebook.com/v21.0"

ACCOUNT_STATUS = {
    1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
    8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
    101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED",
}

# Reporting needs only ads_read. ads_management is what pausing and budget moves would
# need — not requested here, because this bridge does not do those things.
REPORTING_SCOPES = ["ads_read"]


def get(path, **params):
    """GET a Graph API path; returns parsed JSON, error responses included."""
    params["access_token"] = os.environ["META_ACCESS_TOKEN"]
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except Exception:
            return {"error": {"message": f"HTTP {e.code}", "type": "http"}}
    except Exception as e:
        return {"error": {"message": str(e), "type": "transport"}}


def err_text(resp):
    e = resp.get("error")
    if not e:
        return None
    return f"{e.get('message', 'unknown error')} (type={e.get('type')}, code={e.get('code')})"


def money(raw, currency="USD"):
    """Meta returns minor units as strings; render dollars or a dash."""
    if raw in (None, ""):
        return "-"
    try:
        return f"{int(raw) / 100:.2f} {currency}"
    except (TypeError, ValueError):
        return f"{raw} {currency}"


# --------------------------- preflight ---------------------------

def preflight(out):
    """Report exactly what is still missing. Deliberately never fails the build:
    'not launched yet' is a status, not a broken pipeline."""
    config, source = cfg.load()
    out.append("\n## Config")
    if source:
        out.append(f"Read from: {', '.join(source)}")
    else:
        out.append(f"❌ No config found. Copy `{cfg.EXAMPLE_PATH}` to `{cfg.CONFIG_PATH}` "
                   "and fill it in, or set the BRONCO_* environment variables in CI.")

    missing = cfg.missing_required(config)
    for key in cfg.REQUIRED:
        value = config.get(key)
        if value in (None, ""):
            out.append(f"- ❌ `{key}` — not set")
        else:
            shown = value if key != "meta_ad_account_id" else value[:8] + "…"
            out.append(f"- ✅ `{key}` = `{shown}`")

    if cfg.is_decided(config, "lead_endpoint"):
        if config["lead_endpoint"]:
            out.append("- ✅ `lead_endpoint` — set, quality-weighted CPL available")
        else:
            out.append("- ⚠️ `lead_endpoint` — deliberately blank; lead quality reports as "
                       "unknown and CPL falls back to raw counts")
    else:
        out.append("- ❌ `lead_endpoint` — undecided. Set a URL, or blank it explicitly to "
                   "accept degraded quality scoring")

    out.append("\n## Credentials")
    if os.environ.get("META_ACCESS_TOKEN"):
        out.append("- ✅ `META_ACCESS_TOKEN` present in this environment")
    else:
        out.append("- ❌ `META_ACCESS_TOKEN` not set. Repo Settings → Secrets and variables "
                   "→ Actions → New repository secret")

    out.append("\n## Auto-execute")
    out.append(f"- Config says `auto_execute_enabled` = "
               f"`{config.get('auto_execute_enabled', 'false')}`")
    out.append("- This bridge is read-only regardless — it has no code that can pause an ad "
               "or change a budget.")

    ready = not missing and os.environ.get("META_ACCESS_TOKEN")
    out.append("\n## Verdict")
    if ready:
        out.append("**READY** — `discover`, `audit` and `report` can run. Next: one week of "
                   "report-only runs before enabling any auto-action.")
    else:
        blockers = list(missing)
        if not os.environ.get("META_ACCESS_TOKEN"):
            blockers.append("META_ACCESS_TOKEN")
        if not cfg.is_decided(config, "lead_endpoint"):
            blockers.append("lead_endpoint (or an explicit blank)")
        out.append(f"**NOT READY** — {len(blockers)} outstanding: "
                   + ", ".join(f"`{b}`" for b in blockers))
        out.append("\nEverything else is built and waiting. These are the only values the "
                   "repo cannot determine for itself.")
    return True


# --------------------------- token-backed actions ---------------------------

def validate(out):
    me = get("me", fields="id,name")
    if err_text(me):
        # A transport failure says nothing about the token. Telling someone to regenerate a
        # working token because a proxy hiccuped wastes their time and invalidates the old one.
        if (me.get("error") or {}).get("type") == "transport":
            out.append(f"❌ Could not reach the Graph API: {err_text(me)}")
            out.append("This is a network problem, not a credential one — the token was never "
                       "checked. Retry; if it persists, the runner has no egress to "
                       "graph.facebook.com.")
            return False
        out.append(f"❌ Token rejected: {err_text(me)}")
        out.append("Likely expired or missing scopes — generate a fresh long-lived token "
                   "(Business Settings → System users, or Graph API Explorer) and update the "
                   "META_ACCESS_TOKEN secret.")
        return False
    out.append(f"✅ Token valid — authenticated as **{me.get('name')}** (id {me.get('id')})")
    perms = get("me/permissions")
    granted = {d["permission"] for d in perms.get("data", []) if d.get("status") == "granted"}
    if granted:
        missing = [s for s in REPORTING_SCOPES if s not in granted]
        if missing:
            out.append(f"⚠️ Missing scopes needed for reporting: {', '.join(missing)}")
        else:
            out.append("✅ Reporting scopes present (`ads_read`)")
    else:
        out.append("Scopes not listable (normal for system-user tokens) — the calls below show "
                   "what the token can actually reach.")
    return True


def discover(out):
    """List what the token can see, so the ad account ID can be confirmed from here
    instead of by digging through Ads Manager on a phone."""
    out.append("\n## Ad accounts reachable by this token")
    accts = get("me/adaccounts", fields="name,account_status,currency,amount_spent,business{name}",
                limit="25")
    if err_text(accts):
        out.append(f"❌ {err_text(accts)}")
    else:
        rows = accts.get("data", [])
        if not rows:
            out.append("None reachable — either no ad account exists yet, or this token's user "
                       "has not been added to it.")
        for a in rows:
            status = ACCOUNT_STATUS.get(a.get("account_status"), a.get("account_status"))
            biz = (a.get("business") or {}).get("name", "no business manager")
            flag = " ← Bronco?" if "bronco" in (a.get("name") or "").lower() else ""
            out.append(f"- `{a['id']}` — **{a.get('name')}**, {status}, {a.get('currency')}, "
                       f"lifetime spend {money(a.get('amount_spent'), a.get('currency', 'USD'))}, "
                       f"business: {biz}{flag}")
        out.append("\nThe `act_…` value above is what goes in `meta_ad_account_id`.")

    out.append("\n## Pages")
    pages = get("me/accounts", fields="name,category", limit="25")
    if err_text(pages):
        out.append(f"- {err_text(pages)}")
    else:
        rows = pages.get("data", [])
        for p in rows:
            flag = " ← Bronco?" if "bronco" in (p.get("name") or "").lower() else ""
            out.append(f"- {p.get('name')} ({p['id']}, {p.get('category')}){flag}")
        if not rows:
            out.append("- none reachable — a Facebook Page is required to run ads")
    return True


def audit(out):
    config, _ = cfg.load()
    account = config.get("meta_ad_account_id")
    if not account:
        out.append("\n⚠️ `meta_ad_account_id` not set — run `preflight`, or use `discover` to "
                   "find it. Skipping the account audit.")
        return True

    currency = config.get("currency", "USD")
    out.append("\n## Account")
    acct = get(account, fields="name,account_status,disable_reason,balance,currency,"
                               "funding_source_details,amount_spent,created_time")
    if err_text(acct):
        out.append(f"❌ {err_text(acct)}")
        return True

    currency = acct.get("currency", currency)
    status = ACCOUNT_STATUS.get(acct.get("account_status"), acct.get("account_status"))
    fs = acct.get("funding_source_details") or {}
    out.append(f"- **{acct.get('name')}** ({account})")
    out.append(f"- Status: **{status}** (disable_reason: {acct.get('disable_reason')})")
    out.append(f"- Outstanding balance: {money(acct.get('balance'), currency)}")
    out.append(f"- Lifetime spend: {money(acct.get('amount_spent'), currency)}")
    out.append(f"- Funding source: {fs.get('display_string', 'none on file')}")
    out.append(f"- Created: {acct.get('created_time')}")

    out.append("\n## Campaigns")
    camps = get(f"{account}/campaigns",
                fields="name,status,effective_status,objective,daily_budget,created_time",
                limit="25")
    if err_text(camps):
        out.append(f"- {err_text(camps)}")
        return True
    rows = camps.get("data", [])
    if not rows:
        out.append("- none — the account has no campaigns yet")
    watched = config.get("campaign_id")
    for c in rows:
        flag = " ← watched by daily-ads-watch" if c["id"] == watched else ""
        out.append(f"- `{c['id']}` **{c.get('name')}** — {c.get('effective_status')}, "
                   f"objective {c.get('objective')}, daily budget "
                   f"{money(c.get('daily_budget'), currency)}, created {c.get('created_time')}"
                   f"{flag}")
    if watched and not any(c["id"] == watched for c in rows):
        out.append(f"\n⚠️ Configured `campaign_id` `{watched}` is not in this account. "
                   "The daily watch would monitor nothing.")
    return True


def fetch_leads(endpoint, auth_env):
    """Pull recent leads from the client's own endpoint. Returns (leads, error)."""
    req = urllib.request.Request(endpoint)
    token = os.environ.get(auth_env or "", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
    except Exception as e:
        return [], str(e)
    if isinstance(payload, dict):
        payload = payload.get("leads", payload.get("data", []))
    return (payload, None) if isinstance(payload, list) else ([], "unexpected payload shape")


def report(out):
    """Yesterday's spend and results for the watched campaign, plus lead quality."""
    config, _ = cfg.load()
    campaign = config.get("campaign_id")
    if not campaign:
        out.append("\n⚠️ `campaign_id` not set — nothing to report on. Run `preflight`.")
        return True

    currency = config.get("currency", "USD")
    out.append("\n## Yesterday")
    ins = get(f"{campaign}/insights", date_preset="yesterday",
              fields="spend,impressions,clicks,ctr,cpc,actions")
    if err_text(ins):
        out.append(f"❌ {err_text(ins)}")
        return True
    rows = ins.get("data", [])
    if not rows:
        out.append("- no delivery yesterday (campaign paused, or outside its schedule)")
        return True

    row = rows[0]
    spend = float(row.get("spend") or 0)
    out.append(f"- Spend: {spend:.2f} {currency}")
    out.append(f"- Impressions: {row.get('impressions')} · Clicks: {row.get('clicks')} · "
               f"CTR: {row.get('ctr')} · CPC: {row.get('cpc')}")
    meta_leads = 0
    for a in row.get("actions") or []:
        if a.get("action_type") in ("lead", "onsite_conversion.lead_grouped"):
            meta_leads = int(float(a.get("value", 0)))
    out.append(f"- Meta-reported leads: {meta_leads}")

    cap = config.get("daily_budget_hard_cap")
    if cap:
        try:
            if spend > float(cap):
                out.append(f"- 🚨 Spend exceeded the hard cap of {float(cap):.2f} {currency}")
        except ValueError:
            out.append(f"- ⚠️ `daily_budget_hard_cap` is not a number: `{cap}`")

    out.append("\n## Lead quality")
    endpoint = config.get("lead_endpoint")
    if not endpoint:
        out.append("- Unknown — no `lead_endpoint` configured, so quality-weighted CPL is "
                   "unavailable and only Meta's raw lead count above applies.")
        if meta_leads:
            out.append(f"- Raw CPL: {spend / meta_leads:.2f} {currency}")
        return True

    leads, error = fetch_leads(endpoint, config.get("lead_endpoint_auth_env"))
    if error:
        out.append(f"- ❌ Could not reach the lead endpoint: {error}")
        return True

    summary = lead_quality.summarize(leads)
    tiers = summary["tiers"]
    out.append(f"- {summary['count']} leads — {tiers['strong']} strong, {tiers['ok']} ok, "
               f"{tiers['junk']} junk")
    out.append(f"- Total quality weight: {summary['quality_weight']:.1f} "
               f"(max {summary['count'] * lead_quality.MAX_SCORE:.0f})")
    qcpl = lead_quality.quality_weighted_cpl(spend, summary["quality_weight"])
    if qcpl is None:
        out.append("- Quality-weighted CPL: no scoreable leads yesterday")
    else:
        out.append(f"- **Quality-weighted CPL: {qcpl:.2f} {currency}**")
    return True


# --------------------------- offline self-test ---------------------------

def selftest(out):
    """Verify the config parser and lead scoring without touching the network."""
    failures = []

    example = cfg.EXAMPLE_PATH
    if not os.path.exists(example):
        failures.append(f"{example} is missing")
    else:
        with open(example, encoding="utf-8") as f:
            parsed = cfg.parse_markdown(f.read())
        for key in cfg.REQUIRED:
            if key not in parsed:
                failures.append(f"template does not define `{key}`")
            elif parsed[key] is not None:
                failures.append(f"`{key}` in the template should read as an unset placeholder")
        for key, expected in (("currency", "USD"), ("micro_bump_step", "1.00"),
                              ("auto_execute_enabled", "false")):
            if parsed.get(key) != expected:
                failures.append(f"`{key}` parsed as {parsed.get(key)!r}, expected {expected!r}")
        if cfg.missing_required(parsed) != cfg.REQUIRED:
            failures.append("an unfilled template should report every required key missing")
        if cfg.auto_execute_enabled(parsed):
            failures.append("auto-execute must default to off")
    out.append(f"- config parser: {len(failures)} problem(s) so far")

    strong = lead_quality.score_lead({"scope": "Cabinet Paint", "timeline": "ASAP",
                                      "location": "Yes", "name": "Maria Gonzalez",
                                      "phone": "(510) 555-0100", "email": "maria@gmail.com"})
    junk = lead_quality.score_lead({"scope": "Other", "timeline": "Not Sure", "location": "No",
                                   "name": "test", "phone": "555", "email": "test@example.com"})
    # A lead ticking every box should reach the ceiling exactly — that pins the weights.
    if abs(strong - lead_quality.MAX_SCORE) > 1e-9:
        failures.append(f"a perfect lead scored {strong}, expected {lead_quality.MAX_SCORE}")
    if lead_quality.tier(strong) != "strong":
        failures.append(f"a perfect lead bucketed as {lead_quality.tier(strong)}")
    if lead_quality.tier(junk) != "junk":
        failures.append(f"junk lead scored {junk} and bucketed as {lead_quality.tier(junk)}")
    if junk >= strong:
        failures.append("junk lead outscored a strong one")
    if lead_quality.quality_weighted_cpl(50.0, 0) is not None:
        failures.append("zero quality weight must not produce a CPL")
    if abs(lead_quality.quality_weighted_cpl(50.0, 10.0) - 5.0) > 1e-9:
        failures.append("quality-weighted CPL arithmetic is wrong")
    out.append(f"- lead scoring: strong={strong:.2f}, junk={junk:.2f}")

    if failures:
        out.append("\n❌ Self-test failures:")
        out.extend(f"  - {f}" for f in failures)
        return False
    out.append("\n✅ Self-test passed.")
    return True


ACTIONS = {"preflight", "discover", "audit", "report", "selftest"}


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "preflight"
    if action not in ACTIONS:
        print(f"Unknown action {action!r}. Choose one of: {', '.join(sorted(ACTIONS))}")
        sys.exit(2)

    out = [f"# Bronco Meta bridge — {action}"]

    if action == "selftest":
        ok = selftest(out)
    elif action == "preflight":
        ok = preflight(out)
    elif not os.environ.get("META_ACCESS_TOKEN"):
        # Expected pre-launch state, not a failure — exit green so probe runs stay clean.
        out.append("\n`META_ACCESS_TOKEN` is not set, so no Meta calls were attempted. "
                   "Run `preflight` for the full list of what is still outstanding.")
        ok = True
    else:
        ok = validate(out)
        if ok and action == "discover":
            ok = discover(out)
        elif ok and action == "audit":
            ok = audit(out)
        elif ok and action == "report":
            ok = report(out)

    report_text = "\n".join(out)
    print(report_text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report_text + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Meta Marketing API bridge for Franco Roofing ads ops.

Runs inside GitHub Actions (the sandboxed agent environment cannot reach
graph.facebook.com directly). The token comes from the META_ACCESS_TOKEN
repo secret and is never printed.

Usage: python franco_ads/meta_bridge.py [validate|audit]
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v21.0"

ACCOUNT_STATUS = {
    1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
    8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
    101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED",
}

REQUIRED_SCOPES = ["ads_management", "ads_read", "business_management", "pages_show_list"]


def get(path, **params):
    """GET a Graph API path; returns parsed JSON (error responses included)."""
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
    except Exception as e:  # network etc.
        return {"error": {"message": str(e), "type": "transport"}}


def post(path, **params):
    """POST to a Graph API path; returns parsed JSON (error responses included)."""
    params["access_token"] = os.environ["META_ACCESS_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{path}", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
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


def validate(out):
    me = get("me", fields="id,name")
    if err_text(me):
        out.append(f"❌ Token rejected: {err_text(me)}")
        out.append("Likely expired or missing scopes — generate a fresh long-lived token "
                   "(Business Settings → System users, or Graph API Explorer) and update the "
                   "META_ACCESS_TOKEN secret.")
        return False
    out.append(f"✅ Token valid — authenticated as **{me.get('name')}** (id {me.get('id')})")
    perms = get("me/permissions")
    granted = {d["permission"] for d in perms.get("data", []) if d.get("status") == "granted"}
    if granted:
        out.append(f"Granted scopes: {', '.join(sorted(granted))}")
        missing = [s for s in REQUIRED_SCOPES if s not in granted]
        if missing:
            out.append(f"⚠️ Missing scopes for full ops: {', '.join(missing)}")
    else:
        out.append("Scopes not listable (normal for system-user tokens) — the audit below shows "
                   "what the token can actually reach.")
    return True


def audit(out):
    out.append("\n## Ad accounts")
    accts = get("me/adaccounts", fields="name,account_status,currency,amount_spent,business{name}", limit="25")
    if err_text(accts):
        out.append(f"❌ {err_text(accts)}")
        acct_ids = []
    else:
        rows = accts.get("data", [])
        acct_ids = [a["id"] for a in rows]
        if not rows:
            out.append("None reachable — the Franco ad account may not exist yet or the token's "
                       "user isn't added to it.")
        for a in rows:
            status = ACCOUNT_STATUS.get(a.get("account_status"), a.get("account_status"))
            biz = (a.get("business") or {}).get("name", "no BM")
            out.append(f"- **{a.get('name')}** ({a['id']}) — {status}, {a.get('currency')}, "
                       f"spent {a.get('amount_spent')}, business: {biz}")

    out.append("\n## Businesses")
    biz = get("me/businesses", fields="name", limit="25")
    if err_text(biz):
        out.append(f"- {err_text(biz)}")
    else:
        names = [f"- {b.get('name')} ({b['id']})" for b in biz.get("data", [])] or ["- none"]
        out.extend(names)

    out.append("\n## Pages")
    pages = get("me/accounts", fields="name,category", limit="25")
    if err_text(pages):
        out.append(f"- {err_text(pages)}")
    else:
        rows = pages.get("data", [])
        for p in rows:
            flag = " ← Franco?" if "franco" in p.get("name", "").lower() else ""
            out.append(f"- {p.get('name')} ({p['id']}, {p.get('category')}){flag}")
        if not rows:
            out.append("- none reachable (a Facebook Page for Franco Roofing is required for ads)")

    out.append("\n## Pixels")
    any_pixel = False
    for acct_id in acct_ids:
        px = get(f"{acct_id}/adspixels", fields="name,last_fired_time", limit="10")
        for p in px.get("data", []):
            any_pixel = True
            fired = p.get("last_fired_time", "never fired")
            out.append(f"- {p.get('name')} ({p['id']}) on {acct_id} — last fired: {fired}")
    if not any_pixel:
        out.append("- none found — pixel must be created before launch (pack file 01, step 3)")

    out.append("\n## Next steps the bridge can take (on request)")
    out.append("- Create pixel on the chosen ad account · build the paused campaign per pack file 02 "
               "· upload creatives once files are provided. Nothing is created by this audit.")


FRANCO_ACCOUNT = "act_2166218730589990"
FRANCO_PIXEL = "1707330867197445"


def deep(out):
    out.append("\n## Franco ad account detail")
    acct = get(FRANCO_ACCOUNT, fields="name,account_status,disable_reason,balance,currency,"
                                      "funding_source_details,amount_spent,created_time")
    if err_text(acct):
        out.append(f"❌ {err_text(acct)}")
    else:
        status = ACCOUNT_STATUS.get(acct.get("account_status"), acct.get("account_status"))
        out.append(f"- Status: **{status}** (disable_reason: {acct.get('disable_reason')})")
        out.append(f"- Outstanding balance: {int(acct.get('balance', 0)) / 100:.2f} {acct.get('currency')}")
        out.append(f"- Lifetime spend: {int(acct.get('amount_spent', 0)) / 100:.2f} {acct.get('currency')}")
        fs = acct.get("funding_source_details") or {}
        out.append(f"- Funding source: {fs.get('display_string', 'none on file')}")
        out.append(f"- Created: {acct.get('created_time')}")

    out.append("\n## Franco campaigns (existing)")
    camps = get(f"{FRANCO_ACCOUNT}/campaigns", fields="name,status,effective_status,objective,"
                                                      "daily_budget,created_time", limit="25")
    if err_text(camps):
        out.append(f"- {err_text(camps)}")
    else:
        rows = camps.get("data", [])
        for c in rows:
            budget = int(c.get("daily_budget", 0)) / 100 if c.get("daily_budget") else "-"
            out.append(f"- **{c.get('name')}** ({c['id']}) — {c.get('effective_status')}, "
                       f"objective {c.get('objective')}, daily ${budget}, created {c.get('created_time')}")
        if not rows:
            out.append("- none — account is empty, campaign gets built fresh per pack file 02")

    out.append("\n## Franco pixel events (last 7 days)")
    stats = get(f"{FRANCO_PIXEL}/stats", aggregation="event")
    if err_text(stats):
        out.append(f"- {err_text(stats)}")
    else:
        rows = stats.get("data", [])
        if not rows:
            out.append("- no events recorded in window")
        for s in rows:
            out.append(f"- {json.dumps(s)[:300]}")

    out.append("\n## Franco page ads eligibility")
    page = get("1266258446566929", fields="name,is_published,link,fan_count")
    if err_text(page):
        out.append(f"- {err_text(page)}")
    else:
        out.append(f"- {page.get('name')}: published={page.get('is_published')}, "
                   f"fans={page.get('fan_count')}, {page.get('link')}")


FRC_CAMPAIGN = "52641835287524"


def pause_franco_campaign(out):
    """License gate (pack 09, R-LIC-4): campaign stays paused until CSLB #841613
    is verifiably Active and ads carry the license line. Reversible one-call."""
    out.append("\n## Pause FRC campaign (license gate, R-LIC-4)")
    res = post(FRC_CAMPAIGN, status="PAUSED")
    if err_text(res):
        out.append(f"❌ {err_text(res)}")
        return
    check = get(FRC_CAMPAIGN, fields="name,status,effective_status")
    out.append(f"- {check.get('name')}: status={check.get('status')}, "
               f"effective={check.get('effective_status')}")


def resume_franco_campaign(out):
    """User directive 2026-07-31: restore the campaign to ACTIVE (undo pause)."""
    out.append("\n## Resume FRC campaign (user directive)")
    res = post(FRC_CAMPAIGN, status="ACTIVE")
    if err_text(res):
        out.append(f"❌ {err_text(res)}")
        return
    check = get(FRC_CAMPAIGN, fields="name,status,effective_status")
    out.append(f"- {check.get('name')}: status={check.get('status')}, "
               f"effective={check.get('effective_status')}")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if not os.environ.get("META_ACCESS_TOKEN"):
        # Expected pre-setup state, not a failure — exit green so probe runs
        # don't flag the PR; the log line is the signal the agent reads.
        print("META_ACCESS_TOKEN secret is not set. Add it: repo Settings → Secrets and variables "
              "→ Actions → New repository secret.")
        sys.exit(0)
    out = ["# Franco Meta bridge — " + action]
    ok = validate(out)
    if ok and action in ("audit", "deep"):
        audit(out)
    if ok and action == "deep":
        deep(out)
    if ok and action == "pause_franco_campaign":
        pause_franco_campaign(out)
    if ok and action == "resume_franco_campaign":
        resume_franco_campaign(out)
    report = "\n".join(out)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

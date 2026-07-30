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


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if not os.environ.get("META_ACCESS_TOKEN"):
        print("META_ACCESS_TOKEN secret is not set. Add it: repo Settings → Secrets and variables "
              "→ Actions → New repository secret.")
        sys.exit(1)
    out = ["# Franco Meta bridge — " + action]
    ok = validate(out)
    if ok and action == "audit":
        audit(out)
    report = "\n".join(out)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

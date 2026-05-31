"""
One-shot GitHub Pages deployer. Reads the PAT from env GH_TOKEN (never hardcoded),
the secret VALUES from the local .env (via config.py), and:
  1. resolves your username from the token
  2. creates a PUBLIC repo (free-tier Pages requires public)
  3. pushes main
  4. sets Actions secrets SEC_USER_AGENT + FMP_API_KEY (sealed-box encrypted)
  5. enables Pages (build from GitHub Actions)
  6. dispatches the refresh-and-deploy workflow
Prints the run URL + the live Pages URL.

Usage (token stays out of files/history — passed via env for one command):
  GH_TOKEN=ghp_xxx python deploy_github.py
"""
import base64
import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import config

REPO = "stock-alert-app"
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "").strip()


def api(method, path, body=None, accept="application/vnd.github+json"):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "stock-alert-deployer",
    })
    try:
        with urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw.decode("utf-8", "replace")[:300]}
        return e.code, parsed


def encrypt_secret(public_key_b64, value):
    from nacl import encoding, public
    pk = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    return base64.b64encode(public.SealedBox(pk).encrypt(value.encode())).decode()


def run(cmd):
    print("  $", " ".join(c if "@" not in c else c.split("@")[0].split("//")[0] + "//***@" + c.split("@")[1] for c in cmd))
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("   stderr:", (p.stderr or "").strip()[:300])
    return p.returncode == 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not TOKEN:
        print("ERROR: set GH_TOKEN env var"); sys.exit(1)

    # 1) username
    st, me = api("GET", "/user")
    if st != 200:
        print(f"ERROR: token auth failed (HTTP {st}): {me}"); sys.exit(1)
    user = me["login"]
    print(f"[1/6] authenticated as {user}")

    # 2) create repo (public)
    st, resp = api("POST", "/user/repos", {
        "name": REPO, "private": False, "has_issues": False, "has_wiki": False,
        "description": "Smart Money — insider/contract catalyst alerts + yfinance valuation (DCF/comps), PWA",
    })
    if st in (200, 201):
        print(f"[2/6] created public repo {user}/{REPO}")
    elif st == 422:
        print(f"[2/6] repo {user}/{REPO} already exists — continuing")
    else:
        print(f"ERROR creating repo (HTTP {st}): {resp}"); sys.exit(1)

    # 3) push main via tokenized URL, then set a clean origin
    push_url = f"https://{user}:{TOKEN}@github.com/{user}/{REPO}.git"
    clean_url = f"https://github.com/{user}/{REPO}.git"
    subprocess.run(["git", "remote", "remove", "origin"], capture_output=True, text=True)
    run(["git", "remote", "add", "origin", clean_url])
    if not run(["git", "push", push_url, "main", "--force"]):
        print("ERROR: git push failed"); sys.exit(1)
    print("[3/6] pushed main")

    # 4) secrets (sealed-box encrypted)
    st, key = api("GET", f"/repos/{user}/{REPO}/actions/secrets/public-key")
    if st != 200:
        print(f"ERROR getting public key (HTTP {st}): {key}"); sys.exit(1)
    secrets = {"SEC_USER_AGENT": config.USER_AGENT, "FMP_API_KEY": config.FMP_API_KEY}
    for name, val in secrets.items():
        if not val:
            print(f"   skip {name} (empty locally)"); continue
        enc = encrypt_secret(key["key"], val)
        st, r = api("PUT", f"/repos/{user}/{REPO}/actions/secrets/{name}",
                    {"encrypted_value": enc, "key_id": key["key_id"]})
        print(f"   secret {name}: {'OK' if st in (201,204) else 'FAIL '+str(st)+' '+str(r)}")
    print("[4/6] secrets set")

    # 5) enable Pages (source = GitHub Actions / workflow)
    st, r = api("POST", f"/repos/{user}/{REPO}/pages", {"build_type": "workflow"})
    if st in (201, 204):
        print("[5/6] Pages enabled (workflow build)")
    elif st in (409, 422):
        # already enabled — ensure build_type is workflow
        api("PUT", f"/repos/{user}/{REPO}/pages", {"build_type": "workflow"})
        print("[5/6] Pages already enabled — ensured workflow build")
    else:
        print(f"[5/6] WARN enabling Pages (HTTP {st}): {r} — the workflow's configure-pages may still handle it")

    # 6) dispatch the workflow
    st, r = api("POST", f"/repos/{user}/{REPO}/actions/workflows/refresh-and-deploy.yml/dispatches",
                {"ref": "main"})
    print(f"[6/6] workflow dispatch: {'OK' if st == 204 else 'HTTP '+str(st)+' '+str(r)}")

    print("\n=== LINKS ===")
    print(f"Repo:     https://github.com/{user}/{REPO}")
    print(f"Actions:  https://github.com/{user}/{REPO}/actions")
    print(f"Live URL: https://{user}.github.io/{REPO}/   (live ~1-2 min after the run goes green)")
    # emit username for the caller to poll
    print(f"USER={user}")


if __name__ == "__main__":
    main()

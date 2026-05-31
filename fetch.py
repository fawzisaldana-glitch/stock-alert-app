"""HTTP helper. Enforces the SEC User-Agent + a polite delay, and validates TLS against
the OS trust store so corporate/AV interception or missing intermediates don't break calls."""
import json
import time
from urllib.request import Request, urlopen

try:
    import truststore
    truststore.inject_into_ssl()      # use the OS cert store (Windows/macOS/Linux) for TLS verification
except Exception:
    pass

import config


def get(url, accept=None):
    headers = {"User-Agent": config.USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = Request(url, headers=headers)
    time.sleep(config.REQUEST_DELAY)          # rate-limit courtesy (SEC: <10 req/s)
    with urlopen(req, timeout=30) as r:
        return r.read()


def get_json(url):
    return json.loads(get(url, accept="application/json"))


def post_json(url, body):
    headers = {"User-Agent": config.USER_AGENT, "Content-Type": "application/json"}
    req = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    time.sleep(config.REQUEST_DELAY)
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read())

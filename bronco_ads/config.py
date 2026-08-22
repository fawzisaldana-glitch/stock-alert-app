"""Config reader for the Bronco Painting Meta ads bridge.

Values live in `bronco/.bronco-meta-config.md` — a gitignored markdown file, so real
account IDs never land in git. GitHub Actions has no such file, so every key also falls
back to an environment variable: `daily_budget` -> `BRONCO_DAILY_BUDGET`.

The access token is deliberately NOT readable from here. It is always `META_ACCESS_TOKEN`
in the environment, never a file (see the Credentials section of the template).
"""
import os
import re

CONFIG_PATH = "bronco/.bronco-meta-config.md"
EXAMPLE_PATH = "bronco/.bronco-meta-config.example.md"

# Keys the daily watch cannot run without. `lead_endpoint` is deliberately absent —
# it may be explicitly blank (degraded quality scoring), which is a decision, not a gap.
REQUIRED = ["meta_ad_account_id", "campaign_id", "daily_budget", "daily_budget_hard_cap"]

# A cell still carrying the template's placeholder means "nobody has decided yet",
# which is different from a cell deliberately left empty.
PLACEHOLDER = re.compile(r"fill\s*me", re.IGNORECASE)

_ROW = re.compile(r"^\s*\|(?P<key>[^|]*)\|(?P<value>[^|]*)\|")


def _clean(cell):
    """Strip whitespace, surrounding backticks, and bold markers from a table cell."""
    return cell.strip().strip("*").strip().strip("`").strip()


def parse_markdown(text):
    """Pull `key -> value` out of the markdown tables in a config file.

    Returns a dict where the value is either a string or None. None means the key was
    present but still holds the `FILL ME` placeholder — an undecided field. A key mapped
    to "" was deliberately left blank, which some keys accept.
    """
    found = {}
    for line in text.splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        key = _clean(m.group("key"))
        value = _clean(m.group("value"))
        # Skip header and separator rows.
        if not key or key.lower() in ("key", "---") or set(key) <= set("-: "):
            continue
        # Keys are snake_case identifiers; anything else is prose in a different table.
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            continue
        found[key] = None if PLACEHOLDER.search(value) else value
    return found


def _env_name(key):
    return "BRONCO_" + key.upper()


def load(path=CONFIG_PATH):
    """Load config from the markdown file, then let environment variables win.

    Env override matters in CI, where the gitignored file does not exist. Returns
    (config, source) where source describes where values actually came from.
    """
    config, source = {}, []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            config = parse_markdown(f.read())
        source.append(path)

    for key in set(REQUIRED) | set(config) | {"lead_endpoint", "service_area", "timezone",
                                              "currency", "auto_execute_enabled",
                                              "campaign_start_date", "micro_bump_step",
                                              "records_ad_id", "lead_endpoint_auth_env"}:
        env = os.environ.get(_env_name(key))
        if env is not None and env != "":
            config[key] = env
            if "environment" not in source:
                source.append("environment")
    return config, source


def missing_required(config):
    """Required keys that are absent or still holding the template placeholder."""
    return [k for k in REQUIRED if config.get(k) in (None, "")]


def is_decided(config, key):
    """True when a key has been deliberately answered — including answered as blank."""
    return key in config and config[key] is not None


def auto_execute_enabled(config):
    """Whether the operator has opted into mutating actions. Defaults to off."""
    return str(config.get("auto_execute_enabled", "false")).strip().lower() == "true"

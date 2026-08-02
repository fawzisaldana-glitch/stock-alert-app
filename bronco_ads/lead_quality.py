"""Lead quality scoring for Bronco Painting.

Mirrors the scoring model defined in the `daily-ads-watch` skill so the bridge and the
skill agree on what a lead is worth. If the skill's weights change, change them here too —
the numbers below are the contract, not an approximation of it.

The point of scoring: a "Cabinet Paint, ASAP, in service area, valid phone" lead is worth
roughly 3x an "Other, Not sure, out of area, throwaway phone" one. Counting leads hides
that; quality-weighted CPL does not.
"""
import re

SCOPE_WEIGHTS = {"Cabinet Paint": 1.2, "Interior Paint": 1.0, "Exterior Paint": 0.9, "Other": 0.4}
TIMELINE_WEIGHTS = {"ASAP": 1.0, "This Month": 0.85, "Next Month": 0.6, "Not Sure": 0.3}
JUNK_NAME_MARKERS = ["test", "asdf", "qwerty", "bot"]

STRONG, OK = 3.5, 2.0

# The skill's prose calls this a "max 5.0" score, but its own component weights only reach
# 4.5 (1.2 scope + 1.0 timeline + 1.0 area + 0.5 name + 0.8 phone). Reporting against an
# unreachable ceiling would make every batch look worse than it is, so we use the real one.
# Worth reconciling with the skill text at some point; the weights are the contract.
MAX_SCORE = max(SCOPE_WEIGHTS.values()) + max(TIMELINE_WEIGHTS.values()) + 1.0 + 0.5 + 0.8


def score_lead(lead):
    """Score one lead 0..5. Higher is better; 0 is the floor even for junk."""
    score = 0.0
    score += SCOPE_WEIGHTS.get(lead.get("scope") or lead.get("serviceType"), 0.4)
    score += TIMELINE_WEIGHTS.get(lead.get("timeline"), 0.3)
    score += 1.0 if lead.get("location") in ("Yes", "yes", "y") else 0.0

    name = (lead.get("name") or "").strip().lower()
    if name and " " in name and not any(t in name for t in JUNK_NAME_MARKERS):
        score += 0.5

    digits = re.sub(r"\D", "", lead.get("phone") or "")
    if 10 <= len(digits) <= 11 and not digits.startswith("555"):
        score += 0.8

    email = lead.get("email") or ""
    if email and (email.startswith("test@") or "noreply" in email or "@example." in email):
        score -= 0.5

    return max(score, 0.0)


def tier(score):
    """Bucket a score the way the daily report groups leads."""
    if score > STRONG:
        return "strong"
    if score >= OK:
        return "ok"
    return "junk"


def summarize(leads):
    """Score a batch of leads and bucket them.

    Returns a dict with the per-tier counts, the total quality weight, and the scored
    leads themselves so a report can name the junk ones.
    """
    scored = [(lead, score_lead(lead)) for lead in leads]
    counts = {"strong": 0, "ok": 0, "junk": 0}
    for _, s in scored:
        counts[tier(s)] += 1
    return {
        "count": len(scored),
        "tiers": counts,
        "quality_weight": sum(s for _, s in scored),
        "scored": scored,
    }


def quality_weighted_cpl(spend, quality_weight):
    """Spend per unit of lead quality — the metric the daily watch is built around.

    Returns None when there is no quality to divide by, which the caller must render as
    "no leads" rather than as a zero or an infinity.
    """
    if quality_weight <= 0:
        return None
    return spend / quality_weight

"""
SIGNAL #2: fresh federal contract awards (catalyst). Source: USAspending.gov
POST /api/v2/search/spending_by_award/ — FREE, no API key. Honest limitation:
USAspending lists the RECIPIENT legal name, not a ticker, and most contractors are
private — so we best-effort match the recipient to a public ticker via SEC names.
"""
import datetime

import config
import fetch
import sectors

AWARD_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def recent_large_awards(lookback_days, min_usd, limit=50):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=lookback_days)
    body = {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],          # contract award types
            "time_period": [{"start_date": start.isoformat(), "end_date": end.isoformat()}],
            "award_amounts": [{"lower_bound": min_usd}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount",
                   "Awarding Agency", "Start Date", "Description"],
        "sort": "Award Amount", "order": "desc", "limit": limit, "page": 1,
    }
    try:
        data = fetch.post_json(AWARD_URL, body)
    except Exception as e:
        print("  [contracts] USAspending fetch failed:", e)
        return []

    out = []
    for r in data.get("results", []):
        recipient = r.get("Recipient Name") or ""
        amount = float(r.get("Award Amount") or 0)
        if not recipient or amount < min_usd:
            continue
        ticker = sectors.find_ticker_by_name(recipient)            # best-effort, may be None
        out.append(dict(
            award_id=str(r.get("Award ID") or r.get("generated_internal_id") or recipient[:40]),
            recipient=recipient, ticker=ticker, amount=amount,
            agency=r.get("Awarding Agency") or "", action_date=r.get("Start Date") or "",
            descr=(r.get("Description") or "")[:200],
        ))
    return out

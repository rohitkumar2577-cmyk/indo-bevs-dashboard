"""
Fetches Meta Ads insights for the ad account, broken down by country,
and writes dashboard/data.json in the shape the dashboard expects.

Required environment variables (set as GitHub Secrets, never hardcode):
  META_ACCESS_TOKEN   - System User access token with ads_read permission
  META_AD_ACCOUNT_ID  - e.g. act_1234567890

Brand is inferred from the campaign name. Campaigns must be named with a
'BroCode' or 'BongaBonga' prefix/substring (case-insensitive) for the
split to work, e.g. "BroCode_USA_Sep26", "BongaBonga - UK - Reels".
Campaigns that match neither are grouped under "Unmapped" so nothing
silently disappears from the totals.
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

GRAPH_VERSION = "v21.0"
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN")
AD_ACCOUNT_ID = os.environ.get("META_AD_ACCOUNT_ID")

# Country name normalization: Meta returns ISO-ish country names/codes
# depending on the breakdown; map them to the labels used in the plan.
COUNTRY_LABELS = {
    "US": "USA", "USA": "USA", "United States": "USA",
    "GB": "UK", "UK": "UK", "United Kingdom": "UK",
    "CA": "Canada", "Canada": "Canada",
    "AU": "Australia", "Australia": "Australia",
    "NZ": "New Zealand", "New Zealand": "New Zealand",
    "AE": "UAE (Ajman)", "United Arab Emirates": "UAE (Ajman)",
    "KE": "Kenya", "Kenya": "Kenya",
    "LK": "Sri Lanka", "Sri Lanka": "Sri Lanka",
    "SC": "Seychelles", "Seychelles": "Seychelles",
    "NP": "Nepal", "Nepal": "Nepal",
}

RISK_BY_COUNTRY = {
    "USA": "Low", "UK": "Low", "Canada": "Low", "Australia": "Low",
    "New Zealand": "Medium", "UAE (Ajman)": "High", "Kenya": "Medium",
    "Sri Lanka": "High", "Seychelles": "High", "Nepal": "High",
}


def detect_brand(campaign_name: str) -> str:
    name = (campaign_name or "").lower()
    if "brocode" in name or "bro code" in name:
        return "BroCode"
    if "bongabonga" in name or "bonga bonga" in name:
        return "BongaBonga"
    return "Unmapped"


def graph_get(path: str, params: dict) -> dict:
    params = {**params, "access_token": ACCESS_TOKEN}
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_insights():
    """Pulls campaign-level insights broken down by country for the account."""
    if not ACCESS_TOKEN or not AD_ACCOUNT_ID:
        print("Missing META_ACCESS_TOKEN or META_AD_ACCOUNT_ID env vars.", file=sys.stderr)
        sys.exit(1)

    params = {
        "level": "campaign",
        "breakdowns": "country",
        "fields": "campaign_name,spend,impressions,reach,frequency,"
                   "cpm,actions",
        "date_preset": "maximum",  # adjust to a fixed date_start/date_stop once the flight is live
        "limit": 500,
    }
    path = f"{AD_ACCOUNT_ID}/insights"
    all_rows = []
    while True:
        data = graph_get(path, params)
        all_rows.extend(data.get("data", []))
        paging = data.get("paging", {})
        next_url = paging.get("next")
        if not next_url:
            break
        # subsequent pages come as full URLs; fetch directly
        req = urllib.request.Request(next_url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        all_rows.extend(data.get("data", []))
        if not data.get("paging", {}).get("next"):
            break
    return all_rows


def extract_ad_recall(actions):
    """Ad recall lift isn't a standard insights field - it comes from a
    separate Brand Lift / Ad Recall Lift study via the API. As a proxy
    until a study is attached, this looks for an 'estimated_ad_recallers'
    action type if present; otherwise returns None so the dashboard falls
    back gracefully rather than showing a fabricated number."""
    if not actions:
        return None
    for a in actions:
        if a.get("action_type") in ("estimated_ad_recallers", "ad_recall_lift"):
            try:
                return float(a.get("value", 0))
            except (TypeError, ValueError):
                return None
    return None


def build_rows(raw_rows):
    rows = []
    for r in raw_rows:
        country_raw = r.get("country", "Unknown")
        country = COUNTRY_LABELS.get(country_raw, country_raw)
        brand = detect_brand(r.get("campaign_name", ""))
        spend = float(r.get("spend", 0) or 0)
        impressions = float(r.get("impressions", 0) or 0)
        reach = float(r.get("reach", 0) or 0)
        freq = float(r.get("frequency", 0) or 0)
        cpm = float(r.get("cpm", 0) or 0)
        ad_recall = extract_ad_recall(r.get("actions"))

        rows.append({
            "country": country,
            "brand": brand,
            "budget": None,  # actual budget config isn't in insights; keep plan's figure separately if needed
            "delivery_rate": None,
            "effective_spend": round(spend),
            "cpm": round(cpm),
            "freq": round(freq, 1),
            "impressions": round(impressions),
            "reach": round(reach),
            "ad_recall_lift": round(ad_recall) if ad_recall is not None else None,
            "risk": RISK_BY_COUNTRY.get(country, "Unknown"),
        })
    return rows


def merge_duplicate_rows(rows):
    """Multiple campaigns can share the same country+brand; sum them."""
    merged = {}
    for r in rows:
        key = (r["country"], r["brand"])
        if key not in merged:
            merged[key] = dict(r)
        else:
            m = merged[key]
            for field in ("effective_spend", "impressions", "reach"):
                m[field] = (m[field] or 0) + (r[field] or 0)
            if r["ad_recall_lift"] is not None:
                m["ad_recall_lift"] = (m["ad_recall_lift"] or 0) + r["ad_recall_lift"]
            # weighted-ish average for cpm/freq is good enough for a dashboard
            m["cpm"] = round((m["cpm"] + r["cpm"]) / 2)
            m["freq"] = round((m["freq"] + r["freq"]) / 2, 1)
    return list(merged.values())


def main():
    raw_rows = fetch_insights()
    rows = build_rows(raw_rows)
    rows = merge_duplicate_rows(rows)

    output = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "rows": rows,
    }

    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()

# INDO BEVS Recall Dashboard — Setup

## What's in this folder
- `index.html` — the dashboard itself. Open it directly in a browser and it
  works immediately with sample data from the approved plan. Once `data.json`
  exists next to it, it switches to live data automatically.
- `fetch_meta_data.py` — pulls campaign insights from the Meta Marketing API,
  broken down by country, and writes `data.json`.
- `.github_workflows_fetch-ads-data.yml` — a GitHub Actions workflow that runs
  the fetch script every 6 hours and commits the result. **Rename/move this
  file to `.github/workflows/fetch-ads-data.yml`** in your repo — GitHub only
  recognizes workflows in that exact folder.

## Where to put your token — do this in GitHub, not in any file
1. Push this folder to a GitHub repo.
2. In the repo, go to **Settings → Secrets and variables → Actions**.
3. Click **New repository secret** and add two secrets:
   - Name: `META_ACCESS_TOKEN` → Value: your System User access token
   - Name: `META_AD_ACCOUNT_ID` → Value: your ad account ID, e.g. `act_1234567890`
4. That's it — the workflow reads them as environment variables at run time.
   The token is never visible in the code, the repo, or this dashboard.

## Turning on GitHub Pages (to host the dashboard for free)
1. Repo → **Settings → Pages**.
2. Under "Build and deployment", set Source to **Deploy from a branch**,
   branch `main`, folder `/dashboard` (or `/root` if you move index.html
   to the repo root).
3. GitHub gives you a URL like `https://<username>.github.io/<repo>/` —
   share that with your manager.

## Important note on Ad Recall Lift
Meta's standard Insights API doesn't return "Ad Recall Lift" as a normal
field — that number comes from a dedicated **Brand Lift study**, which you
set up separately in Ads Manager (Measure & Report → Brand Lift). Until a
study is attached to your campaigns, `ad_recall_lift` in `data.json` will
come back empty for real data, and the dashboard will show it as missing
rather than guessing a number. If you want that metric live, the study is
the piece to set up next — happy to walk through it once you're ready.

## Campaign naming requirement
Since brand isn't a native Meta field, `fetch_meta_data.py` detects
BroCode vs BongaBonga from the **campaign name**. Make sure campaign names
contain "BroCode" or "BongaBonga" somewhere (case-insensitive), e.g.
`BroCode_USA_Sep26`. Anything that doesn't match either gets grouped under
"Unmapped" in the data so nothing silently vanishes from your totals —
that's your signal to fix a campaign's name if you see it.

## Testing the fetch script locally (optional)
```bash
export META_ACCESS_TOKEN="your-token"
export META_AD_ACCOUNT_ID="act_1234567890"
python3 fetch_meta_data.py
```
This writes `data.json` in this same folder. Open `index.html` in a browser
afterward to see it pick up the live data.

# Review → Product Pulse → Fee Explainer → Approval-gated MCP
Product: ChatGPT mobile app, India (same as Milestones 1–2).

## How to run
1. `pip install pandas scikit-learn google-play-scraper mcp`
2. `python scrape_reviews.py 12` → `data/reviews.csv` (public Play Store reviews, last 12 weeks; columns date, rating, text, thumbs_up)
3. `python pipeline.py analyze` → ≤5 TF-IDF/KMeans themes, top 3, 3 quotes, fee issue, `outputs/weekly_pulse.md` (≤250 words, asserted), `outputs/fee_explainer.md`, `outputs/payload.json`
4. `python pipeline.py approve` → approval gate, then MCP actions

## Hosted prototype (no auth, per brief)
`app.py` is a small Flask UI: upload CSV → themes, pulse, explainer → **Approve & run MCP actions** / Reject.
Local: `pip install -r requirements.txt && python app.py` (port 8000).
Deploy: push this folder to GitHub, create a Render (or Railway/HF Spaces) web service, build `pip install -r requirements.txt`, start `gunicorn app:app`. The Procfile is included.

## Where MCP approval happens
In the hosted app: the Approve button on the results page (`/approve` runs only after the click). In the CLI: the `APPROVE` prompt in `approve()`.
`approve()` in `pipeline.py`: prints both pending actions (doc append, Gmail draft) and executes nothing unless you type `APPROVE`. Only then `mcp_actions.py` calls the Docs and Gmail MCP servers (config in `mcp_servers.json`). Gmail is draft-only; there is no send call. Without a config it simulates into `outputs/notes_log.md` and `outputs/email_draft.txt`.

## Fee issue identified from reviews
_Filled in after running on the real CSV (see outputs/analysis.json → fee)._

## Files
`kb/fee_explainers.json`: verified facts + 2 official links + last-checked date per fee type, filled only from official pages.

"""Review -> Product Pulse + Fee Explainer -> approval-gated MCP actions.
Usage:
  python pipeline.py analyze  [--csv data/reviews.csv]   # steps 1-3, writes outputs/
  python pipeline.py approve                              # approval gate + MCP actions
"""
import argparse, json, re, datetime as dt
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

OUT = Path("outputs"); OUT.mkdir(exist_ok=True)

# ---- fee/charge lexicon (what users complain about) ----
FEES = {
 "Subscription auto-renewal / charged after cancelling": r"auto[- ]?renew|renewal|renewed|still charged|charged again|cancel(?:l)?ed?.{0,40}(?:charge|deduct)|unsubscrib",
 "GST / tax added on top of listed price": r"\bgst\b|\btax(?:es)?\b|extra (?:charge|amount)|added (?:charge|amount)|more than (?:the )?(?:price|399|1999)|hidden (?:charge|fee|cost)",
 "Unexpected deduction / refund difficulty": r"deduct|refund|money (?:was )?(?:taken|cut)|debited|charged without",
 "Plan price / Go vs Plus confusion": r"(?=.*(?:\bprice\b|\bamount\b|\bgo plan\b|\bchatgpt go\b|₹ ?\d{3,}|rs\.? ?\d{3,}|\b399\b|\b1999\b|free trial|\btrial\b))(?=.*(?:\bshown\b|\blisted\b|\bsaid\b|\bdifferent\b|\bmore\b|\bextra\b|\bwrong\b|\bhigher\b|\bcharged\b|\bdeducted\b))",
}
MONEY = re.compile(r"charg|deduct|debit|refund|gst|tax|price|pay|billing|subscription|renew|₹|\brs\b|money|plan|upi", re.I)
STOP = {"app","chatgpt","gpt","chat","openai","use","using","just","really","very","good","like","one","get","also"}

def load(csv):
    df = pd.read_csv(csv)
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"content": "text", "review": "text", "score": "rating", "at": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["text", "date"]).drop_duplicates("text")
    df = df[df.text.str.len() > 15]
    cutoff = df.date.max() - pd.Timedelta(weeks=12)
    return df[df.date >= cutoff].reset_index(drop=True)

def cluster(df, k=5):
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=3, max_df=0.5)
    X = vec.fit_transform(df.text)
    km = KMeans(n_clusters=min(k, 5), n_init=10, random_state=0).fit(X)
    df["cluster"] = km.labels_
    terms = vec.get_feature_names_out()
    themes = []
    for c in range(km.n_clusters):
        sub = df[df.cluster == c]
        top = [terms[i] for i in km.cluster_centers_[c].argsort()[::-1] if terms[i] not in STOP][:5]
        themes.append({"id": c, "keywords": top, "count": len(sub),
                       "share_pct": round(100 * len(sub) / len(df), 1),
                       "avg_rating": round(sub.rating.mean(), 2),
                       "label": " / ".join(top[:3])})
    return sorted(themes, key=lambda t: -t["count"])

def pick_quotes(df, themes, n=3):
    quotes = []
    for t in themes[:n]:
        sub = df[(df.cluster == t["id"]) & df.text.str.len().between(40, 220)]
        sub = sub.sort_values(["thumbs_up" if "thumbs_up" in sub else "rating"], ascending=False)
        if len(sub):
            r = sub.iloc[0]; quotes.append({"theme": t["label"], "rating": int(r.rating),
                                            "date": str(r.date.date()), "quote": r.text.strip()})
    return quotes

def detect_fee(df):
    neg = df[df.rating <= 3]
    scores = {}
    remaining = neg
    for name in ("GST / tax added on top of listed price",
                 "Subscription auto-renewal / charged after cancelling",
                 "Unexpected deduction / refund difficulty",
                 "Plan price / Go vs Plus confusion"):
        m = remaining[remaining.text.str.contains(FEES[name], case=False, regex=True)]
        scores[name] = m
        remaining = remaining.drop(m.index)
    best = max(scores, key=lambda k: len(scores[k]))
    m = scores[best]
    ex = m[m.text.str.len().between(40, 240)].head(2).text.str.strip().tolist()
    return {"fee_issue": best, "mentions": len(m),
            "share_of_negative_pct": round(100 * len(m) / max(len(neg), 1), 1),
            "examples": ex, "all_scores": {k: len(v) for k, v in scores.items()}}

def wc(s): return len(re.findall(r"\S+", s))

def pulse(df, themes, quotes, fee, week_of):
    top = themes[:3]
    md = f"# Weekly Product Pulse — ChatGPT India (week of {week_of})\n"
    md += f"**Base:** {len(df)} Play Store reviews, last 12 weeks · avg rating {df.rating.mean():.2f}\n\n"
    md += "## Top themes\n" + "\n".join(f"{i+1}. **{t['label']}** — {t['share_pct']}% of reviews, avg {t['avg_rating']}★" for i, t in enumerate(top))
    md += "\n\n## User voices\n" + "\n".join(f"- “{q['quote'][:160]}” ({q['rating']}★)" for q in quotes)
    md += (f"\n\n## Key observation\n{fee['share_of_negative_pct']}% of ≤3★ reviews mention "
           f"**{fee['fee_issue']}** — the most common billing confusion.\n")
    md += ("\n## Actions\n1. Show final INR price (incl. GST) and renewal date before the pay button.\n"
           "2. Add an in-app “Why was I charged?” link to the billing explainer.\n"
           "3. Send renewal reminder + one-tap cancel path; track billing-related 1★ weekly.\n")
    assert wc(md) <= 250, f"pulse is {wc(md)} words (>250) — trim quotes"
    return md

def analyze(csv):
    df = load(csv); themes = cluster(df); quotes = pick_quotes(df, themes); fee = detect_fee(df)
    today = dt.date.today().isoformat()
    md = pulse(df, themes, quotes, fee, today)
    (OUT / "weekly_pulse.md").write_text(md)
    explainer = json.loads(Path("kb/fee_explainers.json").read_text()).get(fee["fee_issue"])
    if not explainer: raise ValueError(f"No verified explainer in kb/fee_explainers.json for: {fee['fee_issue']}")
    bullets = explainer["bullets"][:6]
    exp_md = "## Fee explainer: " + fee["fee_issue"] + "\n" + "\n".join(f"- {b}" for b in bullets)
    exp_md += "\n\nSources:\n" + "\n".join(f"- {u}" for u in explainer["sources"][:2])
    exp_md += f"\n\nLast checked: {explainer['last_checked']}\n"
    (OUT / "fee_explainer.md").write_text(exp_md)
    payload = {"date": today, "top_themes": [t["label"] for t in themes[:3]], "weekly_pulse": md,
               "identified_fee_issue": fee["fee_issue"], "explanation_bullets": bullets,
               "source_links": explainer["sources"][:2]}
    (OUT / "payload.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    (OUT / "analysis.json").write_text(json.dumps({"themes": themes, "quotes": quotes, "fee": fee}, indent=2, default=str))
    return {"payload": payload, "pulse": md, "explainer": exp_md, "pulse_words": wc(md), "analysis": json.loads((OUT / "analysis.json").read_text())}

def build_email(p):
    subj = f"Weekly Product Pulse + Customer Clarification — {p['date']}"
    body = p["weekly_pulse"] + "\n\n--- Support snippet ---\n" + "\n".join("• " + b for b in p["explanation_bullets"]) \
           + "\n\nSources:\n" + "\n".join(p["source_links"])
    return subj, body

def execute(p):
    """MCP actions. Call ONLY after approval."""
    subj, body = build_email(p)
    cfg = Path("mcp_servers.json")
    if cfg.exists():
        import asyncio; from mcp_actions import run; asyncio.run(run(json.loads(cfg.read_text()), p, subj, body))
        return "MCP: appended doc entry, created Gmail draft (not sent)"
    with open(OUT / "notes_log.md", "a") as f: f.write(f"\n\n---\n```json\n{json.dumps(p, indent=2, ensure_ascii=False)}\n```\n")
    (OUT / "email_draft.txt").write_text(f"Subject: {subj}\n\n{body}\n")
    return "Simulated MCP: appended outputs/notes_log.md, wrote outputs/email_draft.txt (not sent)"

def approve():
    p = json.loads((OUT / "payload.json").read_text()); subj, _ = build_email(p)
    print("=== PENDING MCP ACTIONS (nothing executed yet) ===")
    print("1. docs.append_entry ->", json.dumps({k: p[k] for k in ("date", "top_themes", "identified_fee_issue")}))
    print("2. gmail.create_draft ->", subj, "(NO auto-send)")
    print(execute(p) if input("\nType APPROVE to execute: ").strip() == "APPROVE" else "Rejected. No action taken.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["analyze", "approve"])
    ap.add_argument("--csv", default="data/reviews.csv"); a = ap.parse_args()
    (print(analyze(a.csv)["pulse"]) if a.cmd == "analyze" else approve())

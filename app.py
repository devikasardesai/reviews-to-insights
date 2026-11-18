"""Minimal hosted UI (no auth, per brief): upload CSV -> analyze -> review -> APPROVE button -> MCP actions."""
import json, html, os
from flask import Flask, request
import pipeline as P

app = Flask(__name__)
PAGE = "<body style='font-family:sans-serif;max-width:820px;margin:2rem auto'><h2>Review → Product Pulse → Fee Explainer</h2>{}</body>"
esc = html.escape

@app.get("/")
def home():
    return PAGE.format("""<form method=post action=/analyze enctype=multipart/form-data>
    <p>Reviews CSV (date, rating, text):</p><input type=file name=csv required> <button>Analyze</button></form>""")

@app.post("/analyze")
def analyze():
    os.makedirs("data", exist_ok=True)
    request.files["csv"].save("data/reviews.csv")
    try: r = P.analyze("data/reviews.csv")
    except Exception as e: return PAGE.format(f"<p style='color:#b00'>{esc(str(e))}</p><a href=/>Back</a>")
    a = r["analysis"]
    th = "".join(f"<li>{esc(t['label'])} — {t['count']} reviews, {t['avg_rating']}★</li>" for t in a["themes"])
    return PAGE.format(f"""<h3>Themes</h3><ul>{th}</ul>
    <h3>Weekly pulse ({r['pulse_words']} words)</h3><pre style='white-space:pre-wrap'>{esc(r['pulse'])}</pre>
    <h3>Fee explainer</h3><pre style='white-space:pre-wrap'>{esc(r['explainer'])}</pre>
    <h3>Approval required</h3><p>Pending: (1) append entry to notes/doc, (2) create email draft — <b>not sent</b>.</p>
    <form method=post action=/approve><button>✅ Approve &amp; run MCP actions</button></form>
    <form method=get action=/><button>❌ Reject</button></form>""")

@app.post("/approve")
def approve():
    p = json.loads((P.OUT / "payload.json").read_text()); subj, body = P.build_email(p)
    msg = P.execute(p)
    return PAGE.format(f"<p><b>{esc(msg)}</b></p><h3>Email draft</h3><pre style='white-space:pre-wrap'>Subject: {esc(subj)}\n\n{esc(body)}</pre><a href=/>Start over</a>")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

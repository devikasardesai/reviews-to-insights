"""Run ON YOUR OWN MACHINE (needs internet): pip install google-play-scraper pandas
Usage: python scrape_reviews.py [weeks=12] -> data/reviews.csv  (public Play Store reviews, India)"""
import sys, datetime as dt, pandas as pd
from google_play_scraper import reviews, Sort
weeks = int(sys.argv[1]) if len(sys.argv) > 1 else 12
cutoff = dt.datetime.now() - dt.timedelta(weeks=weeks)
out, token = [], None
while True:
    batch, token = reviews("com.openai.chatgpt", lang="en", country="in",
                           sort=Sort.NEWEST, count=200, continuation_token=token)
    out += batch
    if not batch or batch[-1]["at"] < cutoff or len(out) >= 6000 or token is None: break
df = pd.DataFrame(out)[["at", "score", "content", "thumbsUpCount"]]
df.columns = ["date", "rating", "text", "thumbs_up"]
df = df[df.date >= cutoff]
df.to_csv("data/reviews.csv", index=False); print(len(df), "reviews saved")

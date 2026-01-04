import os
import json
import time
import hashlib
import datetime
from typing import Dict, List
import requests
import feedparser

TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(TZ)

DATA_DIR = "data"
CACHE_FILE = os.path.join(DATA_DIR, "sent_news.txt")

FEEDS = {
    "TW": "https://news.google.com/rss/search?q=site:twstocknews.com.tw+OR+台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "US": "https://news.google.com/rss/search?q=stock+market+USA&hl=en-US&gl=US&ceid=US:en",
    "CRYPTO": "https://news.google.com/rss/search?q=cryptocurrency+bitcoin+ethereum&hl=en&gl=US&ceid=US:en",
}

WEBHOOKS = {
    "TW": os.getenv("NEWS_WEBHOOK_TW", ""),
    "US": os.getenv("NEWS_WEBHOOK_US", ""),
    "CRYPTO": os.getenv("NEWS_WEBHOOK_CRYPTO", ""),
}

COLOR_MAP = {
    "重大": 0xFF0000,
    "中級": 0xFFAA00,
    "一般": 0x00FF00,
}

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        open(CACHE_FILE, "w", encoding="utf-8").close()

def _load_sent() -> set:
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return set(x.strip() for x in f if x.strip())

def _save_sent(ids: List[str]):
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        for i in ids:
            f.write(i + "\n")

def _hash_post(title: str, link: str) -> str:
    return hashlib.md5(f"{title}|{link}".encode()).hexdigest()

def _judge_level(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["crash", "暴跌", "崩盤", "重挫", "利率", "fed", "cpi"]):
        return "重大"
    if any(k in t for k in ["財報", "展望", "回檔", "反彈"]):
        return "中級"
    return "一般"

def _build_header_embed(title: str) -> Dict:
    return {
        "title": f"📊 {title}",
        "description": f"更新時間：{NOW.strftime('%Y-%m-%d %H:%M')}",
        "color": 0x2F3136
    }

def _build_news_embed(market: str, post: Dict) -> Dict:
    level = post["level"]
    return {
        "title": f"[{market}] {post['title']}",
        "url": post["link"],
        "color": COLOR_MAP[level],
        "fields": [
            {"name": "重要程度", "value": level, "inline": True},
            {"name": "來源", "value": "Google News", "inline": True},
            {"name": "時間", "value": NOW.strftime("%H:%M"), "inline": True},
        ],
        "footer": {"text": "Smart News Radar System"}
    }

def _send_embeds(webhook: str, embeds: List[Dict]):
    for i in range(0, len(embeds), 10):
        payload = {"embeds": embeds[i:i+10]}
        r = requests.post(webhook, json=payload, timeout=10)
        if r.status_code >= 300:
            raise RuntimeError(f"Discord error {r.status_code}: {r.text[:200]}")

def run_market(market: str):
    webhook = WEBHOOKS.get(market)
    if not webhook:
        print(f"⚠️ no webhook for {market}")
        return

    feed = feedparser.parse(FEEDS[market])
    sent = _load_sent()
    new_ids = []
    embeds = [_build_header_embed(
        "台股市場快訊" if market == "TW"
        else "美股市場快訊" if market == "US"
        else "Crypto 市場快訊"
    )]

    for e in feed.entries[:8]:
        title = e.get("title", "")
        link = e.get("link", "")
        hid = _hash_post(title, link)
        if hid in sent:
            continue

        level = _judge_level(title)
        embeds.append(_build_news_embed(market, {
            "title": title,
            "link": link,
            "level": level
        }))
        new_ids.append(hid)

    if len(embeds) > 1:
        _send_embeds(webhook, embeds)
        _save_sent(new_ids)
        print(f"✅ {market} sent {len(new_ids)} news")
    else:
        print(f"ℹ️ {market} no new news")

def main():
    _ensure_data_dir()
    for market in ["TW", "US", "CRYPTO"]:
        run_market(market)
        time.sleep(1)

if __name__ == "__main__":
    main()

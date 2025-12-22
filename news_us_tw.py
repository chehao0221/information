import feedparser
import requests
import os
import urllib.parse
from datetime import datetime

WEBHOOK = os.environ.get("NEWS_WEBHOOK_URL", "").strip()

def get_news(query, lang='zh-TW', region='TW'):
    safe_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={safe_query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:2]] if feed.entries else []

def send_to_discord(content):
    if WEBHOOK and content:
        res = requests.post(WEBHOOK, json={"content": content}, timeout=15)
        print(f"📡 傳送狀態: {res.status_code}")

def run():
    if not WEBHOOK:
        print("❌ 錯誤：找不到 NEWS_WEBHOOK_URL")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. 處理台股 (分開傳送)
    tw_msg = f"🟢 **台股情報** ({now})\n"
    tw_targets = {"大盤": "台股 走勢", "台積電": "台積電 2330"}
    for label, query in tw_targets.items():
        news = get_news(query)
        tw_msg += f"**{label}**\n"
        for n in news:
            tw_msg += f"• {n['title']}\n{n['link']}\n"
    send_to_discord(tw_msg)

    # 2. 處理美股 (分開傳送)
    us_msg = f"🔵 **美股情報** ({now})\n"
    us_targets = {"總經": "Fed CPI", "科技": "NVIDIA Apple"}
    for label, query in us_targets.items():
        news = get_news(query, lang='zh-TW', region='US')
        us_msg += f"**{label}**\n"
        for n in news:
            us_msg += f"• {n['title']}\n{n['link']}\n"
    send_to_discord(us_msg)

if __name__ == "__main__":
    run()

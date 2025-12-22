import feedparser
import requests
import os
import urllib.parse
from datetime import datetime

# 讀取並清理 Secret
WEBHOOK = os.environ.get("NEWS_WEBHOOK_URL", "").strip()

def get_news(query, lang='zh-TW', region='TW'):
    safe_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={safe_query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:3]] if feed.entries else []

def run():
    if not WEBHOOK:
        print("❌ 錯誤：完全抓不到 NEWS_WEBHOOK_URL。")
        return

    # 先發送一個簡單的測試訊息，確認 Webhook 本身是通的
    test_res = requests.post(WEBHOOK, json={"content": "🚀 機器人連線測試：如果您看到這則訊息，代表 Webhook 設定正確！"})
    
    tw_targets = {"台股大盤": "台股 走勢", "晶圓代工": "台積電 2330"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🗞️ **台美股焦點消息面報** ({now})\n"

    for label, query in tw_targets.items():
        news = get_news(query)
        msg += f"**【{label}】**\n"
        for n in news:
            msg += f"🔹 {n['title']}\n  <{n['link']}>\n"

    # 發送正式新聞
    res = requests.post(WEBHOOK, json={"content": msg})
    print(f"📡 測試訊息狀態: {test_res.status_code}")
    print(f"📡 新聞訊息狀態: {res.status_code}")

if __name__ == "__main__":
    run()

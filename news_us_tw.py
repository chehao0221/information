import feedparser
import requests
import os
import urllib.parse
from datetime import datetime

# 讀取 Secret 並確保無空白
WEBHOOK = os.environ.get("NEWS_WEBHOOK_URL", "").strip()

def get_news(query, lang='zh-TW', region='TW'):
    safe_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={safe_query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    # 只取標題和網址
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:2]] if feed.entries else []

def send_msg(text):
    if WEBHOOK and text:
        # 使用 json 格式發送，並設定 timeout
        payload = {"content": text}
        res = requests.post(WEBHOOK, json=payload, timeout=15)
        print(f"📡 發送狀態碼: {res.status_code}")

def run():
    if not WEBHOOK:
        print("❌ 錯誤：未設定 NEWS_WEBHOOK_URL")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # --- 1. 台股區 ---
    tw_content = f"【台股情報】{now}\n"
    # 簡化關鍵字，減少連結複雜度
    news_list = get_news("台積電")
    for n in news_list:
        tw_content += f"• {n['title']}\n<{n['link']}>\n"
    send_msg(tw_content)

    # --- 2. 美股區 ---
    us_content = f"【美股情報】{now}\n"
    news_list = get_news("Nvidia", lang='zh-TW', region='US')
    for n in news_list:
        us_content += f"• {n['title']}\n<{n['link']}>\n"
    send_msg(us_content)

if __name__ == "__main__":
    run()

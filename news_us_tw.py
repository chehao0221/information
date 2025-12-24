import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse

# 設定
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"

def get_market_news(market_type="TW"):
    """抓取市場消息，並透過快取過濾重複內容"""
    # 建立 data 資料夾
    if not os.path.exists("data"): os.makedirs("data")
    
    # 讀取已發送過的快取
    sent_titles = []
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = [line.strip() for line in f.readlines()]

    # 關鍵字設定
    if market_type == "TW":
        queries = ["台股 財經", "加權指數 走勢"]
        label = "🏹 台股市場概況"
    else:
        queries = ["美股 盤前", "聯準會 利率", "S&P500 走勢"]
        label = "⚡ 美股即時情報"

    new_posts = []
    current_sent_titles = []

    for q in queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        
        for entry in feed.entries[:3]:
            title = entry.title.split(" - ")[0]
            # 檢查是否重複
            if title in sent_titles: continue
            
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            # 只取 12 小時內的
            if (datetime.datetime.utcnow() - pub_time).total_seconds() / 3600 < 12:
                new_posts.append({
                    "title": title,
                    "link": entry.link,
                    "time": (pub_time + datetime.timedelta(hours=8)).strftime("%H:%M")
                })
                current_sent_titles.append(title)

    if new_posts:
        # 組合並發送 Discord (此處省略 Embed 組合程式碼，同前次回答)
        send_to_discord(label, new_posts)
        
        # 更新快取檔案 (只保留最近 100 筆，防止檔案過大)
        all_titles = (current_sent_titles + sent_titles)[:100]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for t in all_titles: f.write(f"{t}\n")

def send_to_discord(label, posts):
    # 實作發送邏輯...
    pass

if __name__ == "__main__":
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    # 判斷目前時段：台北 08:30~17:00 跑台股，17:00~06:00 跑美股
    if 8 <= now.hour < 17:
        get_market_news("TW")
    else:
        get_market_news("US")

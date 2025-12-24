import requests
import datetime
import os
import feedparser
import urllib.parse

# 設定
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"

def send_to_discord(label, posts):
    """將消息發送到 Discord，並依市場區分顏色 """
    if not DISCORD_WEBHOOK_URL or not posts: return
    
    embeds = []
    for post in posts:
        embeds.append({
            "title": post["title"],
            "url": post["link"],
            "description": f"⏰ 發布時間: {post['time']}",
            "color": 3066993 if "台股" in label else 15258703 # 台股綠，美股橘
        })

    for i in range(0, len(embeds), 10):
        payload = {"content": f"## {label}", "embeds": embeds[i:i+10]}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)

def get_market_news(market_type="TW"):
    """抓取新聞並透過快取過濾重複 """
    if not os.path.exists("data"): os.makedirs("data")
    
    sent_titles = []
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = [line.strip() for line in f.readlines()]

    if market_type == "TW":
        queries = ["台股 財經", "加權指數 走勢"]
        label = "🏹 台股市場概況"
    else:
        queries = ["美股 盤前", "聯準會 利率", "S&P500 走勢"]
        label = "⚡ 美股即時情報"

    new_posts = []
    current_session_titles = []

    for q in queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            title = entry.title.split(" - ")[0]
            if title in sent_titles: continue
            
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            # 過濾 12 小時內的新聞 
            if (datetime.datetime.utcnow() - pub_time).total_seconds() / 3600 < 12:
                new_posts.append({
                    "title": title,
                    "link": entry.link,
                    "time": (pub_time + datetime.timedelta(hours=8)).strftime("%H:%M")
                })
                current_session_titles.append(title)

    if new_posts:
        send_to_discord(label, new_posts)
        # 更新並保留最新 100 筆紀錄 
        all_titles = (current_session_titles + sent_titles)[:100]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for t in all_titles: f.write(f"{t}\n")

if __name__ == "__main__":
    # 強制校準台北時間 
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)
    
    # 按照您要求的時段精準佈防
    if 6 <= now.hour < 17:
        get_market_news("TW")
    else:
        get_market_news("US")

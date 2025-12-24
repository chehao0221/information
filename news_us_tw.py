import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse

# 基礎設定
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"

def get_market_price(market_type="TW"):
    """獲取主要指數的即時行情摘要"""
    try:
        if market_type == "TW":
            # 台指期近月、加權指數
            symbols = {"台指期貨": "WTX&=F", "加權指數": "^TWII"}
        else:
            # 小道瓊期貨、標普500期貨、那斯達克期貨
            symbols = {"道瓊期貨": "YM=F", "S&P500期貨": "ES=F", "那指期貨": "NQ=F"}
        
        price_text = "📊 **當前行情摘要：**\n"
        for name, sym in symbols.items():
            ticker = yf.Ticker(sym)
            data = ticker.fast_info
            current = data.last_price
            change = current - data.previous_close
            pct_change = (change / data.previous_close) * 100
            emoji = "🔴" if change < 0 else "🟢"
            price_text += f"{emoji} {name}: {current:.2f} ({change:+.2f} / {pct_change:+.2f}%)\n"
        return price_text
    except Exception as e:
        return f"⚠️ 無法取得即時報價: {e}"

def send_to_discord(label, posts, price_summary=""):
    """將新聞與行情發送到 Discord"""
    if not DISCORD_WEBHOOK_URL or not posts: return
    
    embeds = []
    for post in posts:
        color = 3066993 if "台股" in label else 15258703
        embeds.append({
            "title": post["title"],
            "url": post["link"],
            "description": f"⏰ 時間: {post['time']} (台北)",
            "color": color
        })

    # 分批發送，行情摘要放在首則訊息
    for i in range(0, len(embeds), 10):
        payload = {
            "content": f"## {label}\n{price_summary if i == 0 else ''}",
            "embeds": embeds[i:i+10]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload)

def get_market_news(market_type="TW"):
    """抓取新聞並過濾重複"""
    if not os.path.exists("data"): os.makedirs("data")
    
    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = {line.strip() for line in f.readlines()}

    price_summary = get_market_price(market_type)
    
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
        for entry in feed.entries[:5]:
            title = entry.title.split(" - ")[0]
            if title in sent_titles: continue
            
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            if (datetime.datetime.utcnow() - pub_time).total_seconds() / 3600 < 12:
                new_posts.append({
                    "title": title,
                    "link": entry.link,
                    "time": (pub_time + datetime.timedelta(hours=8)).strftime("%H:%M")
                })
                sent_titles.add(title)
                current_session_titles.append(title)

    if new_posts:
        send_to_discord(label, new_posts, price_summary)
        # 更新快取，保留最新 150 筆
        all_titles = list(sent_titles)[-150:]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for t in all_titles: f.write(f"{t}\n")

if __name__ == "__main__":
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)
    
    if 6 <= now.hour < 17:
        get_market_news("TW")
    else:
        get_market_news("US")

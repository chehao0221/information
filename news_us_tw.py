import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse
import warnings

warnings.filterwarnings("ignore")

# 讀取 Webhook 網址
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

def get_live_news(query):
    """抓取最新新聞，並過濾掉超過 12 小時的舊聞"""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        
        if feed.entries:
            entry = feed.entries[0]
            
            # 時間過濾：只抓 12 小時內的新聞
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            now_time = datetime.datetime.utcnow()
            diff_hours = (now_time - pub_time).total_seconds() / 3600
            
            if diff_hours > 12:
                return None
            
            clean_title = entry.title.split(" - ")[0]
            return {"title": clean_title, "link": entry.link}
        return None
    except:
        return None

def run():
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：找不到 Webhook URL")
        return

    # 監控清單
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 1. 發送標題
    header_msg = (
        f"📢 **股市即時消息速報**\n"
        f"⏰ 報告時間：`{now_time}` (台北)\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"content": header_msg})

    for sym in must_watch:
        try:
            # 2. 抓取現價
            ticker = yf.Ticker(sym)
            df = ticker.history(period="1d")
            if df.empty: continue
            curr_price = float(df['Close'].iloc[-1])

            # 3. 抓取新聞
            news = get_live_news(sym.split('.')[0])

            # 4. 組合訊息
            report = (
                f"**標的：{sym}**\n"
                f"💰 現價：`{curr_price:.2f}`\n"
            )
            
            if news:
                report += f"📰 最新：{news['title']}\n🔗 <{news['link']}>\n"
            else:
                report += f"ℹ️ 近 12 小時無重大相關新聞\n"
            
            requests.post(DISCORD_WEBHOOK_URL, json={"content": report})
            print(f"✅ {sym} 處理完成")

        except Exception as e:
            print(f"❌ {sym} 錯誤: {e}")

    # 結尾
    requests.post(DISCORD_WEBHOOK_URL, json={"content": "━━━━━━━━━━━━━━━━━━"})

if __name__ == "__main__":
    run()

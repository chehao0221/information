import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse
import warnings

warnings.filterwarnings("ignore")

DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

def get_live_news(query):
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        if feed.entries:
            entry = feed.entries[0]
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            now_time = datetime.datetime.utcnow()
            if (now_time - pub_time).total_seconds() / 3600 > 12:
                return None
            return {"title": entry.title.split(" - ")[0], "link": entry.link}
        return None
    except:
        return None

def send_to_discord(embed):
    """專門發送 Embed 格式的函式"""
    payload = {"embeds": [embed]}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def run():
    if not DISCORD_WEBHOOK_URL: return

    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 1. 發布總體標頭
    requests.post(DISCORD_WEBHOOK_URL, json={
        "content": f"📊 **市場開盤情報** | `{now_time}` (台北)\n━━━━━━━━━━━━━━━━━━"
    })

    for sym in must_watch:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2d")
            if df.empty: continue
            
            # 計算今日漲跌
            curr_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            change = curr_price - prev_price
            change_pct = (change / prev_price) * 100
            
            # 專業變色：漲紅(台股邏輯)用 0xFF0000，美股可調為 0x00FF00
            color = 0xFF0000 if change > 0 else 0x00FF00 if change < 0 else 0x808080
            direction = "🔺" if change > 0 else "🔻" if change < 0 else "➖"

            news = get_live_news(sym.split('.')[0])
            
            # 2. 構建 Embed 內容
            embed = {
                "title": f"📈 {sym} 盤勢快訊",
                "color": color,
                "fields": [
                    {
                        "name": "💰 即時現價",
                        "value": f"**{curr_price:.2f}** ({direction} `{change_pct:+.2f}%`)",
                        "inline": True
                    },
                    {
                        "name": "📰 關鍵頭條",
                        "value": f"[{news['title']}]({news['link']})" if news else "近 12 小時暫無重大消息",
                        "inline": False
                    }
                ],
                "footer": {"text": "數據源: Yahoo Finance | Google News"}
            }
            
            send_to_discord(embed)

        except Exception as e:
            print(f"Error {sym}: {e}")

if __name__ == "__main__":
    run()

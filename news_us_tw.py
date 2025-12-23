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
            # 簡化解析邏輯
            return {"title": entry.title.split(" - ")[0], "link": entry.link}
        return None
    except:
        return None

def send_to_discord(embed):
    payload = {"embeds": [embed]}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def run():
    if not DISCORD_WEBHOOK_URL: return

    # 包含台美股重要標的
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA", "QQQ", "SOXL"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 發布總體標頭
    requests.post(DISCORD_WEBHOOK_URL, json={
        "content": f"📊 **市場即時情報** | `{now_time}` (台北)\n━━━━━━━━━━━━━━━━━━"
    })

    for sym in must_watch:
        try:
            # 使用 period="5d" 確保一定能抓到最近兩個交易日的資料
            ticker = yf.Ticker(sym)
            df = ticker.history(period="5d")
            if df.empty or len(df) < 2: continue
            
            curr_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            change = curr_price - prev_price
            change_pct = (change / prev_price) * 100
            
            # 漲紅跌綠 (台股習慣)
            color = 0xFF0000 if change > 0 else 0x00FF00 if change < 0 else 0x808080
            direction = "🔺" if change > 0 else "🔻" if change < 0 else "➖"

            news = get_live_news(sym.split('.')[0])
            
            embed = {
                "title": f"📈 {sym} 盤勢快訊",
                "color": color,
                "fields": [
                    {
                        "name": "💰 即時價格",
                        "value": f"**{curr_price:.2f}** ({direction} `{change_pct:+.2f}%`)",
                        "inline": True
                    },
                    {
                        "name": "📰 最新相關新聞",
                        "value": f"[{news['title']}]({news['link']})" if news else "暫無重大消息",
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

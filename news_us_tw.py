import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse
import warnings

warnings.filterwarnings("ignore")

# 從 GitHub Secrets 讀取 Webhook URL
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

def get_live_news(query):
    """
    抓取 Google News 並過濾掉超過 12 小時的舊聞 (方案 A)
    """
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        
        if feed.entries:
            entry = feed.entries[0]
            # 取得新聞發布時間 (UTC)
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            now_time = datetime.datetime.utcnow()
            
            # 計算時間差 (小時)
            diff_hours = (now_time - pub_time).total_seconds() / 3600
            
            # 方案 A 核心：如果新聞超過 12 小時，視為「舊聞」不回傳
            if diff_hours > 12:
                return None
                
            return {
                "title": entry.title.split(" - ")[0], 
                "link": entry.link,
                "time": (pub_time + datetime.timedelta(hours=8)).strftime("%m/%d %H:%M") # 轉台北時間
            }
        return None
    except:
        return None

def send_to_discord(embed):
    """發送 Embed 格式到 Discord"""
    payload = {"embeds": [embed]}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def run():
    if not DISCORD_WEBHOOK_URL:
        print("錯誤: 找不到 NEWS_WEBHOOK_URL 設定")
        return

    # 監控清單
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA", "QQQ", "SOXL"]
    
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_str = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 1. 發送總體標頭
    requests.post(DISCORD_WEBHOOK_URL, json={
        "content": f"📊 **市場即時情報** | `{now_str}` (台北)\n━━━━━━━━━━━━━━━━━━"
    })

    for sym in must_watch:
        try:
            # 抓取最近 5 天資料確保有足夠 K 線計算漲跌
            ticker = yf.Ticker(sym)
            df = ticker.history(period="5d")
            if df.empty or len(df) < 2: continue
            
            curr_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            change = curr_price - prev_price
            change_pct = (change / prev_price) * 100
            
            # 顏色與符號判定
            color = 0xFF0000 if change > 0 else 0x00FF00 if change < 0 else 0x808080
            direction = "🔺" if change > 0 else "🔻" if change < 0 else "➖"

            # 取得過濾後的新聞
            news = get_live_news(sym.split('.')[0])
            
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
                        "value": f"[{news['title']}]({news['link']})\n*(發布時間: {news['time']})*" if news else "近 12 小時暫無重大消息",
                        "inline": False
                    }
                ],
                "footer": {"text": "數據源: Yahoo Finance | Google News"}
            }
            send_to_discord(embed)

        except Exception as e:
            print(f"處理 {sym} 時發生錯誤: {e}")

if __name__ == "__main__":
    run()

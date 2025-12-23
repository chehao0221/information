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
    """方案 A：自動抓取並過濾 12 小時內的最新消息"""
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
            return {
                "title": entry.title.split(" - ")[0], 
                "link": entry.link,
                "time": (pub_time + datetime.timedelta(hours=8)).strftime("%H:%M")
            }
        return None
    except: return None

def run():
    if not DISCORD_WEBHOOK_URL: return
    
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    current_hour = now.hour

    # --- 💡 雙市場流行清單設定 ---
    if current_hour < 12:
        market_title = "🏹 台股開盤前瞻 | Morning Brief"
        # 標籤化：讓您一眼看出標的屬性
        watch_list = {
            "2330.TW": "護國神山/AI晶片", 
            "2317.TW": "鴻海/AI伺服器", 
            "2382.TW": "廣達/筆電代工", 
            "2454.TW": "聯發科/IC設計", 
            "0050.TW": "台股大盤權值", 
            "00878.TW": "高股息熱門指標"
        }
    else:
        market_title = "⚡ 美股即時戰報 | US Market Radar"
        watch_list = {
            "NVDA": "AI 晶片霸主", 
            "TSLA": "特斯拉/自動駕駛", 
            "AAPL": "蘋果/消費電子", 
            "MSTR": "比特幣巨鯨概念", 
            "SOXL": "半導體3倍看多", 
            "QQQ": "納斯達克指標"
        }

    # 1. 發送結構化標頭
    requests.post(DISCORD_WEBHOOK_URL, json={
        "content": f"### {market_title}\n📅 `{now.strftime('%Y-%m-%d %H:%M')}`\n" + "━"*15
    })

    for sym, label in watch_list.items():
        try:
            ticker = yf.Ticker(sym)
            # 使用 5d 確保跨週末也能抓到資料
            df = ticker.history(period="5d")
            if df.empty or len(df) < 2: continue
            
            curr_p, prev_p = df['Close'].iloc[-1], df['Close'].iloc[-2]
            change_pct = ((curr_p - prev_p) / prev_p) * 100
            
            # 2. 流行視覺：根據漲跌幅強度顯示狀態
            if change_pct > 1.5:
                status, color = "🔥 強勢", 0xFF4500 # 橘紅
            elif change_pct < -1.5:
                status, color = "❄️ 弱勢", 0x1E90FF # 閃亮藍
            else:
                status, color = "⚖️ 平穩", 0x95A5A6 # 質感灰

            news = get_live_news(sym.split('.')[0])
            
            # 3. 構建專業 Embed 訊息
            embed = {
                "title": f"{sym} | {label}",
                "description": f"市場表現：**{status}**",
                "color": color,
                "fields": [
                    {"name": "💵 當前報價", "value": f"`{curr_p:.2f}` (`{change_pct:+.2f}%`)", "inline": True},
                    {"name": "🗞️ 焦點頭條", "value": f"[{news['title']}]({news['link']}) \n*(🕒 來源發布時間: {news['time']})*" if news else "🧊 近 12 小時暫無突發重磅消息", "inline": False}
                ],
                "footer": {"text": "Quant Bot Intelligence System"}
            }
            requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        except: continue

if __name__ == "__main__": run()

import feedparser
import requests
import os
from datetime import datetime

# 讀取環境變數
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL")

def get_news(query, lang='zh-TW', region='TW'):
    url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    # 確保有抓到資料，避免空的 list 導致報錯
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:3]] if feed.entries else []

def run():
    # 檢查 Webhook 是否存在
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：找不到 NEWS_WEBHOOK_URL 環境變數，請檢查 GitHub Secrets 設定。")
        exit(1)

    # 定義追蹤目標
    tw_targets = {"📈 台股大盤": "台股 走勢", "晶圓代工": "台積電 2330", "AI 伺服器": "鴻海 廣達"}
    us_targets = {"🦅 聯準會/總經": "Federal Reserve Fed CPI", "💻 美股科技": "NVIDIA Apple AI stock", "🚗 熱門個股": "TSLA Tesla stock"}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🗞️ **台美股焦點消息面報**\n更新時間: {now} (TW)\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    # 台股區
    msg += "🇹🇼 **台股盤前焦點**\n"
    for label, query in tw_targets.items():
        news = get_news(query)
        msg += f"**【{label}】**\n"
        if news:
            for n in news:
                msg += f"🔹 {n['title']}\n  <{n['link']}>\n"
        else:
            msg += "暫無新聞\n"
    
    # 美股區
    msg += "\n🇺🇸 **美股重要趨勢**\n"
    for label, query in us_targets.items():
        news = get_news(query, lang='zh-TW', region='US')
        msg += f"**【{label}】**\n"
        if news:
            for n in news:
                msg += f"🔸 {n['title']}\n  <{n['link']}>\n"
        else:
            msg += "暫無新聞\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 *本內容由 AI 彙整，僅供投資參考。*"

    # 發送至 Discord 並檢查狀態
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=15)
        response.raise_for_status()
        print(f"✅ 消息報表已於 {now} 成功發送至 Discord")
    except Exception as e:
        print(f"❌ 發送失敗，錯誤原因: {e}")
        exit(1)

if __name__ == "__main__":
    run()

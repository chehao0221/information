import feedparser
import requests
import os
from datetime import datetime

# Discord Webhook 設定 (請在 GitHub Secrets 設定 NEWS_WEBHOOK_URL)
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL")

def get_news(query, lang='zh-TW', region='TW'):
    """從 Google News RSS 抓取新聞"""
    url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    # 僅取前 3 則最相關新聞
    results = []
    for entry in feed.entries[:3]:
        results.append({"title": entry.title, "link": entry.link})
    return results

def run():
    # 定義要追蹤的關鍵字 (台股用中文，美股用英文搜尋再取中文版)
    tw_targets = {"台股大盤": "台股", "台積電": "台積電 2330", "熱門半導體": "半導體 趨勢"}
    us_targets = {"美股大盤": "S&P 500 Index", "人工智慧": "NVIDIA NVDA AI", "聯準會": "Federal Reserve Fed"}

    today = datetime.now().strftime("%Y-%m-%d")
    msg = f"🔔 **台美股消息面早報** ({today})\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"

    # 1. 抓取台股新聞
    msg += "🇹🇼 **台股重點情報**\n"
    for label, query in tw_targets.items():
        news_list = get_news(query, lang='zh-TW', region='TW')
        msg += f"**【{label}】**\n"
        for n in news_list:
            msg += f"• {n['title']}\n  <{n['link']}>\n"
    
    msg += "\n🇺🇸 **美股重點情報 (繁中)**\n"
    for label, query in us_targets.items():
        # 美股關鍵字也直接抓取繁體中文版 Google News
        news_list = get_news(query, lang='zh-TW', region='US')
        msg += f"**【{label}】**\n"
        for n in news_list:
            msg += f"• {n['title']}\n  <{n['link']}>\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "⚠️ *免責聲明：本內容由 AI 自動彙整新聞，不代表投資建議。投資前應獨立評估風險。*"

    # 發送到 Discord
    if DISCORD_WEBHOOK_URL:
        payload = {"content": msg}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
        print("✅ 消息面報表已發送")
    else:
        print("❌ 找不到 NEWS_WEBHOOK_URL")

if __name__ == "__main__":
    run()

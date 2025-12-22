import feedparser
import requests
import os
from datetime import datetime

DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL")

def get_news(query, lang='zh-TW', region='TW'):
    url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:3]]

def run():
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
        for n in news:
            msg += f"🔹 {n['title']}\n  <{n['link']}>\n"
    
    # 美股區
    msg += "\n🇺🇸 **美股重要趨勢**\n"
    for label, query in us_targets.items():
        news = get_news(query, lang='zh-TW', region='US')
        msg += f"**【{label}】**\n"
        for n in news:
            msg += f"🔸 {n['title']}\n  <{n['link']}>\n"

    msg += "━━━━━━━━━━━━━━━━━━\n"
    msg += "💡 *本內容由 AI 彙整，點擊連結查看詳情。*"

    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
        print(f"✅ 消息報表已於 {now} 發送")

if __name__ == "__main__":
    run()

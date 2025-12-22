import feedparser
import requests
import os
import urllib.parse
from datetime import datetime

# 讀取並清理 Secret
WEBHOOK = os.environ.get("NEWS_WEBHOOK_URL", "").strip()

def get_news(query, lang='zh-TW', region='TW'):
    safe_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={safe_query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    # 限制只取前 2 則，確保訊息不會過長被 Discord 阻擋
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:2]] if feed.entries else []

def run():
    if not WEBHOOK:
        print("❌ 錯誤：找不到 NEWS_WEBHOOK_URL")
        return

    # 定義關鍵追蹤標的
    tw_targets = {"📈 台股大盤": "台股 走勢", "晶圓代工": "台積電 2330"}
    us_targets = {"🦅 聯準會趨勢": "Fed CPI", "💻 美股科技": "NVIDIA Apple"}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🗞️ **台美股盤前情報** ({now})\n━━━━━━━━━━━━━━━━━━\n"

    # 台股摘要
    for label, query in tw_targets.items():
        news = get_news(query)
        msg += f"**{label}**\n"
        for n in news:
            msg += f"🔹 {n['title']}\n<{n['link']}>\n"
    
    msg += "\n"

    # 美股摘要
    for label, query in us_targets.items():
        news = get_news(query, lang='zh-TW', region='US')
        msg += f"**{label}**\n"
        for n in news:
            msg += f"🔸 {n['title']}\n<{n['link']}>\n"

    msg += "━━━━━━━━━━━━━━━━━━\n💡 *AI 自動彙整，投資請獨立評估。*"

    # 發送正式新聞
    res = requests.post(WEBHOOK, json={"content": msg}, timeout=15)
    print(f"📡 最終發送狀態: {res.status_code}")

if __name__ == "__main__":
    run()

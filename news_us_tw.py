import feedparser
import requests
import os
from datetime import datetime

# 讀取並自動清理網址可能的空白或換行
WEBHOOK = os.environ.get("NEWS_WEBHOOK_URL", "").strip()

def get_news(query, lang='zh-TW', region='TW'):
    url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:3]] if feed.entries else []

def run():
    if not WEBHOOK:
        print("❌ 錯誤：找不到 NEWS_WEBHOOK_URL，請檢查 Secrets 設定。")
        return

    # 定義標的
    targets = {
        "📈 台美股焦點": "台股 走勢 NVIDIA Apple",
        "🦅 總經動態": "Federal Reserve Fed CPI"
    }

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🗞️ **盤前消息面報** ({now})\n━━━━━━━━━━━━━━━━━━\n"

    for label, query in targets.items():
        news = get_news(query)
        msg += f"**【{label}】**\n"
        for n in news:
            msg += f"🔹 {n['title']}\n  <{n['link']}>\n"

    msg += "━━━━━━━━━━━━━━━━━━\n💡 *AI 自動彙整，僅供參考。*"

    # 發送並強制回報結果
    res = requests.post(WEBHOOK, json={"content": msg})
    print(f"📡 發送狀態: {res.status_code}")
    if res.status_code not in [200, 204]:
        print(f"❌ 錯誤內容: {res.text}")

if __name__ == "__main__":
    run()

import feedparser
import requests
import os
from datetime import datetime

# 確保從環境變數正確讀取
DISCORD_WEBHOOK_URL = os.environ.get("NEWS_WEBHOOK_URL")

def get_news(query, lang='zh-TW', region='TW'):
    url = f"https://news.google.com/rss/search?q={query}&hl={lang}&gl={region}&ceid={region}:{lang}"
    feed = feedparser.parse(url)
    # 確保有抓到資料，避免空的清單導致後續出錯
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:3]] if feed.entries else []

def run():
    # 檢查 Webhook 是否存在，若無則強制停止並顯示錯誤
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：找不到 NEWS_WEBHOOK_URL。請確認 GitHub Secrets 設定無誤。")
        return

    # 定義追蹤標的
    tw_targets = {"📈 台股大盤": "台股 走勢", "晶圓代工": "台積電 2330", "AI 伺服器": "鴻海 廣達"}
    us_targets = {"🦅 聯準會/總經": "Federal Reserve Fed CPI", "💻 美股科技": "NVIDIA Apple AI stock", "🚗 熱門個股": "TSLA Tesla stock"}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"🗞️ **台美股焦點消息面報**\n更新時間: {now} (TW)\n━━━━━━━━━━━━━━━━━━\n"

    # 彙整台股資訊
    msg += "🇹🇼 **台股盤前焦點**\n"
    for label, query in tw_targets.items():
        news = get_news(query)
        msg += f"**【{label}】**\n"
        for n in news:
            msg += f"🔹 {n['title']}\n  <{n['link']}>\n"
    
    # 彙整美股資訊
    msg += "\n🇺🇸 **美股重要趨勢**\n"
    for label, query in us_targets.items():
        news = get_news(query, lang='zh-TW', region='US')
        msg += f"**【{label}】**\n"
        for n in news:
            msg += f"🔸 {n['title']}\n  <{n['link']}>\n"

    msg += "━━━━━━━━━━━━━━━━━━\n💡 *本內容由 AI 彙整，僅供投資參考。*"

    # 發送至 Discord
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=15)
        if res.status_code in [200, 204]:
            print(f"✅ 報表已於 {now} 成功發送")
        else:
            print(f"❌ Discord 傳送失敗，狀態碼: {res.status_code}")
    except Exception as e:
        print(f"❌ 發生異常: {e}")

if __name__ == "__main__":
    run()

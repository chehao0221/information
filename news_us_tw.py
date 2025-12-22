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
    # 每個主題取 2 則最相關的新聞
    return [{"title": entry.title, "link": entry.link} for entry in feed.entries[:2]] if feed.entries else []

def send_msg(text):
    if WEBHOOK and text:
        payload = {"content": text}
        res = requests.post(WEBHOOK, json=payload, timeout=15)
        print(f"📡 發送狀態碼: {res.status_code}")

def run():
    if not WEBHOOK:
        print("❌ 錯誤：未設定 NEWS_WEBHOOK_URL")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # --- 第一報：台股大盤與總經 ---
    msg1 = f"🆕 **【台股大盤與總經】** {now}\n"
    targets1 = {"大盤走勢": "台股 大盤 走勢", "三大法人": "外資 自營商 買超"}
    for label, q in targets1.items():
        news = get_news(q)
        msg1 += f"**{label}**\n"
        for n in news: msg1 += f"• {n['title']}\n<{n['link']}>\n"
    send_msg(msg1)

    # --- 第二報：台股核心權值與半導體 ---
    msg2 = f"🆕 **【核心權值與半導體】**\n"
    targets2 = {"權王動態": "台積電 TSMC", "IC設計": "聯發科 聯電"}
    for label, q in targets2.items():
        news = get_news(q)
        msg2 += f"**{label}**\n"
        for n in news: msg2 += f"• {n['title']}\n<{n['link']}>\n"
    send_msg(msg2)

    # --- 第三報：台股熱門產業 (AI與電力) ---
    msg3 = f"🆕 **【熱門產業觀察】**\n"
    targets3 = {"AI 伺服器": "鴻海 廣達 緯創", "重電能源": "華城 中興電 能源"}
    for label, q in targets3.items():
        news = get_news(q)
        msg3 += f"**{label}**\n"
        for n in news: msg3 += f"• {n['title']}\n<{n['link']}>\n"
    send_msg(msg3)

    # --- 第四報：美股與全球趨勢 ---
    msg4 = f"🆕 **【美股與全球趨勢】**\n"
    targets4 = {"美股總經": "Fed 利率 CPI", "科技巨頭": "Nvidia Apple Tesla"}
    for label, q in targets4.items():
        news = get_news(q, lang='zh-TW', region='US')
        msg4 += f"**{label}**\n"
        for n in news: msg4 += f"• {n['title']}\n<{n['link']}>\n"
    send_msg(msg4)

if __name__ == "__main__":
    run()

import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse

# =============================
# 基礎設定
# =============================
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"
TZ_TW = datetime.timezone(datetime.timedelta(hours=8))
MAX_EMBEDS = 10
NEWS_HOURS_LIMIT = 12

# =============================
# 指數摘要
# =============================
def get_market_price(market_type="TW"):
    try:
        sym = "^TWII" if market_type == "TW" else "^GSPC"
        name = "加權指數" if market_type == "TW" else "S&P 500"

        ticker = yf.Ticker(sym)
        info = ticker.fast_info
        current = info.get("last_price")
        prev = info.get("previous_close")

        if not current or not prev:
            return "⚠️ 指數資料暫缺"

        pct = ((current - prev) / prev) * 100
        emoji = "📈" if pct >= 0 else "📉"
        return f"{emoji} {name}: {current:.2f} ({pct:+.2f}%)"
    except Exception:
        return "⚠️ 指數取得失敗"

# =============================
# Embed 卡片（仿 Quant Bot 圖二）
# =============================
def create_news_embed(post, market_type):
    color = 0x3498db if market_type == "TW" else 0xe74c3c

    return {
        "title": post["title"],
        "url": post["link"],
        "color": color,
        "fields": [
            {
                "name": "⚖️ 市場表現",
                "value": "平穩",
                "inline": True
            },
            {
                "name": "🕒 發布時間",
                "value": f"{post['time']}（台北）",
                "inline": True
            },
            {
                "name": "📰 新聞來源",
                "value": post["source"],
                "inline": False
            }
        ],
        "footer": {
            "text": "Quant Bot Intelligence System"
        }
    }

# =============================
# 主流程
# =============================
def get_market_news(market_type="TW"):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 未設定 NEWS_WEBHOOK_URL")
        return

    os.makedirs("data", exist_ok=True)

    # 已推送新聞快取
    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = {line.strip() for line in f if line.strip()}

    # 搜尋設定
    if market_type == "TW":
        queries = ["台股 財經", "加權指數 走勢", "ETF 配息"]
        label = "🏹 台股市場快訊 | Morning Brief"
    else:
        queries = ["美股 盤前", "聯準會 利率", "S&P500 走勢"]
        label = "⚡ 美股市場快訊 | Market Brief"

    collected = {}
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for q in queries:
        url = (
            "https://news.google.com/rss/search?"
            f"q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        )
        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:
            if not hasattr(entry, "published_parsed"):
                continue

            title = entry.title.split(" - ")[0]
            source = entry.title.split(" - ")[-1] if " - " in entry.title else "財經新聞"

            if title in sent_titles or title in collected:
                continue

            pub_utc = datetime.datetime(
                *entry.published_parsed[:6],
                tzinfo=datetime.timezone.utc
            )

            if (now_utc - pub_utc).total_seconds() / 3600 > NEWS_HOURS_LIMIT:
                continue

            pub_tw = pub_utc.astimezone(TZ_TW)

            collected[title] = {
                "title": title,
                "link": entry.link,
                "source": source,
                "time": pub_tw.strftime("%H:%M"),
                "sort_time": pub_tw
            }

    if not collected:
        print("ℹ️ 沒有新新聞")
        return

    # 依時間新 → 舊排序
    posts = sorted(
        collected.values(),
        key=lambda x: x["sort_time"],
        reverse=True
    )[:MAX_EMBEDS]

    embeds = [create_news_embed(p, market_type) for p in posts]

    now_str = datetime.datetime.now(TZ_TW).strftime("%Y-%m-%d %H:%M")
    price_summary = get_market_price(market_type)

    payload = {
        "content": (
            f"## {label}\n"
            f"📅 `{now_str}`\n"
            f"📊 **{price_summary}**\n"
            f"────────────────────"
        ),
        "embeds": embeds
    }

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        if resp.status_code in (200, 204):
            sent_titles.update(p["title"] for p in posts)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                for t in list(sent_titles)[-300:]:
                    f.write(f"{t}\n")
            print(f"✅ 成功推送 {len(embeds)} 則新聞")
        else:
            print(f"❌ Webhook 失敗：{resp.status_code}")
    except Exception as e:
        print(f"❌ 發送錯誤：{e}")

# =============================
# 入口
# =============================
if __name__ == "__main__":
    now = datetime.datetime.now(TZ_TW)
    market = "TW" if 6 <= now.hour < 17 else "US"
    get_market_news(market)

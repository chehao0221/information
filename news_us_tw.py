import yfinance as yf
import requests
import datetime
import os
import feedparser
import urllib.parse

# =========================
# 基礎設定
# =========================
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"


# =========================
# 市場行情摘要
# =========================
def get_market_price(market_type="TW"):
    """獲取主要指數的即時行情摘要"""
    try:
        if market_type == "TW":
            symbols = {"加權指數": "^TWII"}
        else:
            symbols = {
                "道瓊期貨": "YM=F",
                "S&P500期貨": "ES=F",
                "那指期貨": "NQ=F"
            }

        price_text = "📊 **市場行情摘要**\n"
        for name, sym in symbols.items():
            ticker = yf.Ticker(sym)
            data = ticker.fast_info

            current = data.get("last_price")
            prev = data.get("previous_close")

            if not current or not prev:
                continue

            change = current - prev
            pct = (change / prev) * 100
            emoji = "🟢" if change >= 0 else "🔴"

            price_text += f"{emoji} {name}: {current:.2f} ({pct:+.2f}%)\n"

        return price_text

    except Exception:
        return "📊 市場行情摘要：資料暫時無法取得\n"


# =========================
# Discord 發送（成功才算）
# =========================
def send_to_discord(label, posts, price_summary=""):
    """發送到 Discord，全部成功才回傳 True"""
    if not DISCORD_WEBHOOK_URL or not posts:
        return False

    embeds = []
    for post in posts:
        color = 3066993 if "台股" in label else 15258703
        embeds.append({
            "title": post["title"],
            "url": post["link"],
            "description": f"🕒 來源發布時間：{post['time']}（台北）",
            "color": color
        })

    success = True

    for i in range(0, len(embeds), 10):
        payload = {
            "content": f"## {label}\n{price_summary if i == 0 else ''}",
            "embeds": embeds[i:i + 10]
        }

        try:
            resp = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=10
            )
            if resp.status_code not in (200, 204):
                success = False
        except Exception:
            success = False

    return success


# =========================
# 新聞抓取與去重
# =========================
def get_market_news(market_type="TW"):
    if not os.path.exists("data"):
        os.makedirs("data")

    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = {line.strip() for line in f.readlines()}

    price_summary = get_market_price(market_type)

    if market_type == "TW":
        queries = ["台股 財經", "加權指數 走勢", "ETF 配息"]
        label = "🏹 台股市場快訊"
    else:
        queries = ["美股 盤前", "聯準會 利率", "S&P500 走勢"]
        label = "⚡ 美股市場快訊"

    new_posts = []

    for q in queries:
        url = (
            "https://news.google.com/rss/search?q="
            f"{urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        )
        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:
            title = entry.title.split(" - ")[0]
            if title in sent_titles:
                continue

            if not hasattr(entry, "published_parsed"):
                continue

            pub_time = datetime.datetime(*entry.published_parsed[:6])
            hours_diff = (datetime.datetime.utcnow() - pub_time).total_seconds() / 3600

            if hours_diff > 12:
                continue

            new_posts.append({
                "title": title,
                "link": entry.link,
                "time": (pub_time + datetime.timedelta(hours=8)).strftime("%H:%M")
            })

    # =========================
    # 只有「送成功」才寫入快取
    # =========================
    if new_posts:
        sent_ok = send_to_discord(label, new_posts, price_summary)

        if sent_ok:
            for post in new_posts:
                sent_titles.add(post["title"])

            all_titles = list(sent_titles)[-150:]
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                for t in all_titles:
                    f.write(f"{t}\n")


# =========================
# 程式進入點
# =========================
if __name__ == "__main__":
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)

    if 6 <= now.hour < 17:
        get_market_news("TW")
    else:
        get_market_news("US")

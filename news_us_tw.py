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
# Discord Embed 邊框顏色
# =========================
def get_embed_color_by_pct(pct):
    if pct <= -2:
        return 0xE74C3C  # 紅色：高風險 / 異常
    elif -2 < pct < 1:
        return 0x95A5A6  # 灰色：觀望 / 平穩
    return 0x2ECC71      # 綠色：正常 / 穩定

# =========================
# 顯示排版（完全照你的範例）
# =========================
def format_description(market, price, change, headline, time):
    return (
        f"市場表現：{market}\n"
        f"💵 當前報價\n"
        f"{price} ({change})\n"
        f"🗞️ 焦點頭條\n"
        f"{headline}\n"
        f"(🕒 來源發布時間: {time})"
    )

# =========================
# 取得市場指數（僅用於顏色）
# =========================
def get_market_index(market_type="TW"):
    try:
        symbol = "^TWII" if market_type == "TW" else "ES=F"
        ticker = yf.Ticker(symbol)
        data = ticker.fast_info

        current = data.last_price
        prev = data.previous_close
        pct = (current - prev) / prev * 100

        return {
            "price": f"{current:.2f}",
            "change": f"{pct:+.2f}%",
            "pct": pct
        }
    except Exception:
        return {
            "price": "—",
            "change": "—",
            "pct": 0
        }

# =========================
# 發送 Discord（單一卡片）
# =========================
def send_to_discord(title, description, color):
    if not DISCORD_WEBHOOK_URL:
        return

    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "footer": {
                "text": "Quant Bot Intelligence System"
            }
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

# =========================
# 判斷盤前 / 盤中 / 盤後
# =========================
def get_tw_session(hour):
    if hour < 9:
        return "盤前"
    elif hour >= 14:
        return "盤後"
    return "盤中"

def get_us_session(hour):
    if hour < 21:
        return "盤前"
    elif hour >= 4:
        return "盤後"
    return "盤中"

# =========================
# 抓新聞 + 去重 + 發送
# =========================
def get_market_news(market_type="TW"):
    if not os.path.exists("data"):
        os.makedirs("data")

    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = {line.strip() for line in f.readlines()}

    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)

    index = get_market_index(market_type)
    embed_color = get_embed_color_by_pct(index["pct"])

    if market_type == "TW":
        session = get_tw_session(now.hour)
        queries = ["台股 財經", "ETF 配息", "加權指數"]
        card_title = f"台股{session} | 高股息熱門指標"
        market_text = "⚖️ 平穩"
    else:
        session = get_us_session(now.hour)
        queries = ["美股 盤前", "聯準會 利率", "S&P500"]
        card_title = f"美股{session} | 市場快訊"
        market_text = "⚖️ 平穩"

    for q in queries:
        url = (
            "https://news.google.com/rss/search?"
            f"q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        )
        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:
            title = entry.title.split(" - ")[0]
            if title in sent_titles:
                continue

            pub_time = datetime.datetime(*entry.published_parsed[:6])
            hours_diff = (
                datetime.datetime.utcnow() - pub_time
            ).total_seconds() / 3600

            if hours_diff <= 12:
                time_tw = (
                    pub_time + datetime.timedelta(hours=8)
                ).strftime("%H:%M")

                description = format_description(
                    market=market_text,
                    price=index["price"],
                    change=index["change"],
                    headline=title,
                    time=time_tw
                )

                send_to_discord(card_title, description, embed_color)
                sent_titles.add(title)

    # 更新去重快取
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        for t in list(sent_titles)[-150:]:
            f.write(f"{t}\n")

# =========================
# 主程式入口
# =========================
if __name__ == "__main__":
    tz_tw = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz_tw)

    if 6 <= now.hour < 17:
        get_market_news("TW")
    else:
        get_market_news("US")

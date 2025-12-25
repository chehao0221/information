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

PRICE_CACHE = {}

# =============================
# 股價與指數獲取系統
# =============================
def get_stock_price(sym):
    if sym in PRICE_CACHE:
        return PRICE_CACHE[sym]
    try:
        t = yf.Ticker(sym)
        # 優先使用 fast_info，若失效則嘗試基礎 info
        info = t.fast_info
        price = info.get("last_price") or t.info.get("regularMarketPrice")
        prev = info.get("previous_close") or t.info.get("regularMarketPreviousClose")
        
        if price and prev:
            pct = ((price - prev) / prev) * 100
            PRICE_CACHE[sym] = (price, pct)
            return price, pct
    except Exception:
        pass
    PRICE_CACHE[sym] = (None, None)
    return None, None

def get_market_price(market_type):
    try:
        sym = "^TWII" if market_type == "TW" else "^IXIC"
        name = "加權指數" if market_type == "TW" else "那斯達克"
        t = yf.Ticker(sym)
        info = t.fast_info
        cur = info.get("last_price") or t.info.get("regularMarketPrice")
        prev = info.get("previous_close") or t.info.get("regularMarketPreviousClose")
        
        if not cur or not prev: return "⚠️ 資料讀取中"
        pct = ((cur - prev) / prev) * 100
        emoji = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
        return f"{emoji} {name}: {cur:.2f} ({pct:+.2f}%)"
    except Exception:
        return "⚠️ 指數取得失敗"

# =============================
# 個股對照表與權重判定
# =============================
STOCK_MAP = {
    "台積電": {"sym": "2330.TW", "desc": "AI晶片 / 先進製程"},
    "2330": {"sym": "2330.TW", "desc": "AI晶片 / 先進製程"},
    "鴻海": {"sym": "2317.TW", "desc": "AI伺服器 / 組裝"},
    "聯發科": {"sym": "2454.TW", "desc": "IC設計"},
    "廣達": {"sym": "2382.TW", "desc": "AI伺服器代工"},
    "奇鋐": {"sym": "3017.TW", "desc": "AI散熱龍頭"},
    "雙鴻": {"sym": "3324.TW", "desc": "液冷散熱"},
    "世芯": {"sym": "3661.TW", "desc": "ASIC 設計"},
    "長榮": {"sym": "2603.TW", "desc": "航運龍頭"},
    "00929": {"sym": "00929.TW", "desc": "科技優息"},
    "00919": {"sym": "00919.TW", "desc": "精選高息"},
    "輝達": {"sym": "NVDA", "desc": "NVIDIA / AI龍頭"},
    "NVIDIA": {"sym": "NVDA", "desc": "NVIDIA / AI龍頭"},
    "特斯拉": {"sym": "TSLA", "desc": "Tesla"},
    "TSLA": {"sym": "TSLA", "desc": "Tesla"},
    "蘋果": {"sym": "AAPL", "desc": "Apple"},
    "AAPL": {"sym": "AAPL", "desc": "Apple"},
    "微軟": {"sym": "MSFT", "desc": "Microsoft"},
    "美超微": {"sym": "SMCI", "desc": "SMCI / 伺服器"},
    "PLTR": {"sym": "PLTR", "desc": "AI數據分析"},
}

STOCK_WEIGHT = {
    "2330.TW": 5, "NVDA": 5, "AAPL": 4, "MSFT": 4, 
    "2454.TW": 4, "00929.TW": 4, "2317.TW": 3, "PLTR": 3,
}

def pick_most_important_stock(title):
    hits = []
    title_lower = title.lower()
    seen_sym = set()
    for key, info in STOCK_MAP.items():
        pos = title_lower.find(key.lower())
        if pos >= 0:
            sym = info["sym"]
            if sym in seen_sym: continue
            seen_sym.add(sym)
            weight = STOCK_WEIGHT.get(sym, 1)
            score = weight * 100 - pos
            hits.append((score, info))
    if not hits: return None
    hits.sort(reverse=True, key=lambda x: x[0])
    return hits[0][1]

# =============================
# Embed 生成與主流程
# =============================
def create_news_embed(post, market_type):
    color = 0x3498db if market_type == "TW" else 0xe74c3c
    target = pick_most_important_stock(post["title"])

    if target:
        price, pct = get_stock_price(target["sym"])
        if price is not None:
            trend = "📈 利多" if pct > 0 else "📉 利空" if pct < 0 else "➖ 中性"
            return {
                "title": f"📊 {target['sym']} | {target['desc']}",
                "url": post["link"],
                "color": color,
                "fields": [
                    {"name": "⚖️ 市場判斷", "value": trend, "inline": True},
                    {"name": "💵 即時價格", "value": f"**{price:.2f} ({pct:+.2f}%)**", "inline": True},
                    {"name": "📰 焦點新聞", "value": f"[{post['title']}]({post['link']})\n🕒 {post['time']}", "inline": False},
                ],
                "footer": {"text": "Smart News Radar System"},
            }
    return {
        "title": post["title"],
        "url": post["link"],
        "color": color,
        "fields": [
            {"name": "⚖️ 市場判斷", "value": "➖ 中性", "inline": True},
            {"name": "🕒 發布時間", "value": f"{post['time']} (台北)", "inline": True},
            {"name": "📰 新聞來源", "value": post["source"], "inline": False},
        ],
        "footer": {"text": "Smart News Radar System"},
    }

def get_market_news(market_type):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：未設定 Discord Webhook URL"); return

    os.makedirs("data", exist_ok=True)
    sent_titles = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent_titles = {l.strip() for l in f if l.strip()}

    queries = (
        ["台股 財經", "台積電 鴻海 聯發科", "00929 00919 配息"]
        if market_type == "TW"
        else ["美股 盤前", "輝達 NVIDIA 特斯拉", "PLTR SMCI 財報"]
    )

    label = "🏹 台股市場快訊" if market_type == "TW" else "⚡ 美股市場快訊"
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    collected = {}

    for q in queries:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        for e in feed.entries[:10]:
            title = e.title.split(" - ")[0]
            if title in sent_titles or title in collected: continue
            if not hasattr(e, "published_parsed"): continue
            pub_utc = datetime.datetime(*e.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (now_utc - pub_utc).total_seconds() / 3600 > NEWS_HOURS_LIMIT: continue
            collected[title] = {
                "title": title, "link": e.link, "source": e.title.split(" - ")[-1],
                "time": pub_utc.astimezone(TZ_TW).strftime("%H:%M"), "sort": pub_utc,
            }

    posts = sorted(collected.values(), key=lambda x: x["sort"], reverse=True)[:MAX_EMBEDS]
    if not posts:
        print(f"ℹ️ [{market_type}] 目前無新新聞"); return

    embeds = [create_news_embed(p, market_type) for p in posts]
    payload = {
        "content": f"## {label}\n📅 `{datetime.datetime.now(TZ_TW).strftime('%Y-%m-%d %H:%M')}`\n📊 **{get_market_price(market_type)}**\n────────────────────",
        "embeds": embeds,
    }

    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    if r.status_code in (200, 204):
        sent_titles.update(p["title"] for p in posts)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for t in list(sent_titles)[-300:]: f.write(f"{t}\n")
        print(f"✅ 成功推播 {len(embeds)} 則消息")

if __name__ == "__main__":
    now_tw = datetime.datetime.now(TZ_TW)
    market = "TW" if 6 <= now_tw.hour < 17 else "US"
    print(f"🕒 台北時間: {now_tw.strftime('%H:%M')}, 市場模式: {market}")
    get_market_news(market)

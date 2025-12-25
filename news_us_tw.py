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
# 股價快取 (減少 API 請求)
# =============================
PRICE_CACHE = {}

def get_stock_price(sym):
    if sym in PRICE_CACHE:
        return PRICE_CACHE[sym]
    try:
        t = yf.Ticker(sym)
        info = t.fast_info
        price = info.get("last_price")
        prev = info.get("previous_close")
        if price and prev:
            pct = ((price - prev) / prev) * 100
            PRICE_CACHE[sym] = (price, pct)
            return price, pct
    except Exception:
        pass
    PRICE_CACHE[sym] = (None, None)
    return None, None

# =============================
# 個股 / ETF 關鍵字表（擴充推薦個股）
# =============================
STOCK_MAP = {
    # --- 台股重點權值 ---
    "台積電": {"sym": "2330.TW", "desc": "AI晶片 / 先進製程"},
    "鴻海": {"sym": "2317.TW", "desc": "AI伺服器 / 組裝"},
    "聯發科": {"sym": "2454.TW", "desc": "IC設計"},
    "廣達": {"sym": "2382.TW", "desc": "AI伺服器代工"},
    
    # --- 台股熱門族群 (推薦增加) ---
    "奇鋐": {"sym": "3017.TW", "desc": "AI散熱龍頭"},
    "雙鴻": {"sym": "3324.TW", "desc": "液冷散熱技術"},
    "世芯": {"sym": "3661.TW", "desc": "ASIC 設計"},
    "長榮": {"sym": "2603.TW", "desc": "航運龍頭"},
    "陽明": {"sym": "2609.TW", "desc": "海運市場"},
    
    # --- 台股金融 / ETF ---
    "富邦金": {"sym": "2881.TW", "desc": "金融龍頭"},
    "國泰金": {"sym": "2882.TW", "desc": "金融控股"},
    "0050": {"sym": "0050.TW", "desc": "台灣50 ETF"},
    "00878": {"sym": "00878.TW", "desc": "國泰永續高股息"},
    "00929": {"sym": "00929.TW", "desc": "復華科技優息"},
    "00940": {"sym": "00940.TW", "desc": "元大台灣價值高息"},

    # --- 美股科技巨頭 ---
    "輝達": {"sym": "NVDA", "desc": "NVIDIA / AI龍頭"},
    "NVIDIA": {"sym": "NVDA", "desc": "NVIDIA / AI龍頭"},
    "特斯拉": {"sym": "TSLA", "desc": "Tesla / 電動車"},
    "蘋果": {"sym": "AAPL", "desc": "Apple"},
    "微軟": {"sym": "MSFT", "desc": "Microsoft / AI雲端"},
    "Google": {"sym": "GOOGL", "desc": "Alphabet / AI搜尋"},
    "美超微": {"sym": "SMCI", "desc": "SMCI / 伺服器"},
    "Palantir": {"sym": "PLTR", "desc": "AI數據分析"},

    # --- 美股 ETF ---
    "QQQ": {"sym": "QQQ", "desc": "那斯達克 100 ETF"},
    "SOXX": {"sym": "SOXX", "desc": "半導體 ETF"},
}

# =============================
# 指數摘要
# =============================
def get_market_price(market_type):
    try:
        sym = "^TWII" if market_type == "TW" else "^IXIC"
        name = "加權指數" if market_type == "TW" else "那斯達克"
        t = yf.Ticker(sym)
        info = t.fast_info
        cur = info.get("last_price")
        prev = info.get("previous_close")
        if not cur or not prev: return "⚠️ 指數資料不足"
        pct = ((cur - prev) / prev) * 100
        emoji = "📈" if pct > 0 else "📉" if pct < 0 else "➖"
        return f"{emoji} {name}: {cur:.2f} ({pct:+.2f}%)"
    except Exception:
        return "⚠️ 指數取得失敗"

# =============================
# Embed 生成 (維持您喜歡的好看排版)
# =============================
def create_news_embed(post, market_type):
    color = 0x3498db if market_type == "TW" else 0xe74c3c

    for key, info in STOCK_MAP.items():
        if key in post["title"]:
            price, pct = get_stock_price(info["sym"])
            if price is not None:
                trend = "📈 利多" if pct > 0 else "📉 利空" if pct < 0 else "➖ 中性"
                return {
                    "title": f"📊 {info['sym']} | {info['desc']}",
                    "url": post["link"],
                    "color": color,
                    "fields": [
                        {"name": "⚖️ 市場判斷", "value": trend, "inline": True},
                        {"name": "💵 即時價格", "value": f"**{price:.2f} ({pct:+.2f}%)**", "inline": True},
                        {"name": "📰 焦點新聞", "value": f"[{post['title']}]({post['link']})\n🕒 {post['time']}", "inline": False},
                    ],
                    "footer": {"text": "Quant Bot Intelligence System"},
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
        "footer": {"text": "Quant Bot Intelligence System"},
    }

# =============================
# 主流程 (含防重複機制)
# =============================
def get_market_news(market_type):
    if not DISCORD_WEBHOOK_URL:
        print("❌ 未設定 Webhook URL"); return

    os.makedirs("data", exist_ok=True)
    sent = set()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            sent = {l.strip() for l in f if l.strip()}

    # 擴展搜尋關鍵字以增加個股新聞命中率
    if market_type == "TW":
        queries = ["台股 財經", "台積電 鴻海 聯發科", "散熱 奇鋐 雙鴻", "ETF 配息 00929"]
    else:
        queries = ["美股 盤前", "輝達 NVIDIA 特斯拉", "AI 股票 財報", "PLTR SMCI 走勢"]

    label = "🏹 台股市場快訊 | Morning Brief" if market_type == "TW" else "⚡ 美股市場快訊 | Market Brief"
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    collected = {}

    for q in queries:
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-TW")
        for e in feed.entries[:10]: # 增加單個搜尋的掃描量
            title = e.title.split(" - ")[0]
            # --- 防重複判斷 ---
            if title in sent or title in collected or not hasattr(e, "published_parsed"):
                continue
            pub_utc = datetime.datetime(*e.published_parsed[:6], tzinfo=datetime.timezone.utc)
            if (now_utc - pub_utc).total_seconds() / 3600 > NEWS_HOURS_LIMIT:
                continue
            
            collected[title] = {
                "title": title, "link": e.link,
                "source": e.title.split(" - ")[-1],
                "time": pub_utc.astimezone(TZ_TW).strftime("%H:%M"),
                "sort": pub_utc,
            }

    posts = sorted(collected.values(), key=lambda x: x["sort"], reverse=True)[:MAX_EMBEDS]
    if not posts: return
    
    embeds = [create_news_embed(p, market_type) for p in posts]

    payload = {
        "content": f"## {label}\n📅 `{datetime.datetime.now(TZ_TW).strftime('%Y-%m-%d %H:%M')}`\n📊 **{get_market_price(market_type)}**\n────────────────────",
        "embeds": embeds,
    }

    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    if r.status_code in (200, 204):
        sent.update(p["title"] for p in posts)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            for t in list(sent)[-300:]: f.write(f"{t}\n")
        print(f"✅ 推送成功 {len(embeds)} 則")

if __name__ == "__main__":
    now = datetime.datetime.now(TZ_TW)
    # 判斷時段切換市場：06:00~17:00 跑台股，其餘時間跑美股
    market = "TW" if 6 <= now.hour < 17 else "US"
    get_market_news(market)

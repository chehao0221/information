# -*- coding: utf-8 -*-
"""
Smart News Radar System - TW / US / Crypto market news push to Discord.

顯示方式（照你原本的截圖）：
- 一則新聞 = 一張 Discord Embed 卡片
- 重要性徽章：重大 / 中級 / 一般
- 顏色：重大=紅、中級=黃、一般=綠
- 每次執行：依時段推 台股 or 美股，再另外推 Crypto
- 去重：data/sent_news.txt
"""
from __future__ import annotations

import os
import time
import datetime as dt
from typing import Dict, List, Tuple, Optional
from urllib.parse import quote

import requests
import feedparser
import yfinance as yf

# ----------------------------
# Config
# ----------------------------
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = os.path.join("data", "sent_news.txt")

TZ_TAIPEI = dt.timezone(dt.timedelta(hours=8))

# Google News RSS
RSS_TW = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
RSS_US = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=US&ceid=US:zh-Hant"
RSS_CRYPTO = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

# Queries (可自行調整)
QUERY_TW = quote("台股 OR 加權指數 OR 櫃買 OR 台積電 OR 2330 OR 外資 OR 金管會 when:1d", safe="")
QUERY_US = quote("美股 OR 那斯達克 OR 標普 OR 道瓊 OR Fed OR CPI OR 非農 when:1d", safe="")
QUERY_CRYPTO = quote("比特幣 OR BTC OR 以太幣 OR ETH OR 加密貨幣 OR 幣圈 when:1d", safe="")

# Discord webhook: max 10 embeds per request
MAX_EMBEDS_PER_REQ = 10
MAX_NEWS_PER_MARKET = 9  # 每個市場最多發幾則（避免太多）

COLOR_MAP = {
    "重大": 0xFF0000,  # 紅
    "中級": 0xFFAA00,  # 黃/橘
    "一般": 0x00FF00,  # 綠
}
HEADER_COLOR = 0x2F3136  # 深色 header

# ----------------------------
# Cache
# ----------------------------
def ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

def load_cache() -> set[str]:
    ensure_data_dir()
    if not os.path.exists(CACHE_FILE):
        return set()
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_cache(items: set[str]) -> None:
    ensure_data_dir()
    # 避免檔案無限長：只保留最後 5000 筆
    lines = list(items)
    if len(lines) > 5000:
        lines = lines[-5000:]
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        for x in lines:
            f.write(x + "\n")

# ----------------------------
# Parsing & Scoring
# ----------------------------
def pick_site_from_title(title: str) -> Tuple[str, str]:
    # Google News 常見格式： "標題 - 來源站"
    if " - " in title:
        a, b = title.rsplit(" - ", 1)
        return a.strip(), b.strip()
    return title.strip(), "Google News"

def safe_get_published(entry) -> Optional[str]:
    if getattr(entry, "published", None):
        return str(entry.published)
    if getattr(entry, "updated", None):
        return str(entry.updated)
    return None

def severity_from_text(text: str) -> str:
    t = text.lower()

    major_kw = [
        "崩盤","暴跌","熔斷","破產","違約","倒閉","擠兌","爆雷","清算",
        "駭客","hack","漏洞","資安","凍結","詐騙",
        "急升","暴漲","飆升","破紀錄","歷史新高",
        "升息","降息","cpi","非農","fed","fomc","利率決議",
        "監管","訴訟","sec","禁令","制裁",
    ]
    mid_kw = [
        "大跌","大漲","回檔","反彈","下修","上修","財報","展望","預測","裁員",
        "通膨","景氣","衰退","增長","美元","債券","殖利率","匯率",
        "機會","看好","看壞","利多","利空",
    ]

    score = 0
    for kw in major_kw:
        if kw in t:
            score += 3
    for kw in mid_kw:
        if kw in t:
            score += 1

    if score >= 3:
        return "重大"
    if score >= 1:
        return "中級"
    return "一般"

def sentiment_from_text(text: str) -> Tuple[str, str]:
    t = text.lower()
    bull = ["大漲","暴漲","飆升","反彈","利多","看好","上修","創新高","突破"]
    bear = ["大跌","暴跌","崩盤","回檔","利空","看壞","下修","衰退","跌破"]
    bull_hit = any(k in t for k in bull)
    bear_hit = any(k in t for k in bear)
    if bull_hit and not bear_hit:
        return "利多", "偏多"
    if bear_hit and not bull_hit:
        return "利空", "偏空"
    return "中性", "觀望"

def fetch_rss(url: str, timeout: int = 15) -> List[Dict]:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    posts: List[Dict] = []
    for e in feed.entries:
        raw_title = getattr(e, "title", "").strip()
        if not raw_title:
            continue
        clean_title, source = pick_site_from_title(raw_title)
        link = getattr(e, "link", "").strip()
        published = safe_get_published(e)

        key = link or clean_title  # 用 link 優先去重
        level = severity_from_text(clean_title + " " + (source or ""))

        posts.append({
            "key": key,
            "title": clean_title,
            "link": link,
            "source": source,
            "published": published,
            "level": level,
        })
    return posts

# ----------------------------
# Market snapshot (header)
# ----------------------------
def get_index_snapshot(market: str) -> str:
    try:
        if market == "TW":
            ticker, label = "^TWII", "加權指數"
        elif market == "US":
            ticker, label = "^IXIC", "那斯達克"
        else:
            ticker, label = "BTC-USD", "BTC"

        tk = yf.Ticker(ticker)
        fi = getattr(tk, "fast_info", None)
        price = prev = None
        if fi:
            price = fi.get("last_price") or fi.get("last")
            prev = fi.get("previous_close")
        if price is None or prev is None:
            hist = tk.history(period="2d")
            if len(hist) >= 2:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
        if price is None or prev is None or prev == 0:
            return ""
        pct = ((price - prev) / prev) * 100.0
        sign = "+" if pct >= 0 else ""
        return f"{label}: {price:.2f} ({sign}{pct:.2f}%)"
    except Exception:
        return ""

# ----------------------------
# Embed builders (照你原本卡片風格)
# ----------------------------
def _build_header_embed(title: str, now: dt.datetime, index_line: str) -> Dict:
    desc = f"{now.strftime('%Y-%m-%d %H:%M')}"
    if index_line:
        desc += f"\n📈 {index_line}"
    return {"title": title, "description": desc, "color": HEADER_COLOR}

def _build_news_embed(market_label: str, post: Dict, now: dt.datetime) -> Dict:
    title = post.get("title", "無標題")
    link = post.get("link", "")
    level = post.get("level", "一般")
    color = COLOR_MAP.get(level, COLOR_MAP["一般"])

    tag, judge = sentiment_from_text(title)

    fields = [
        {"name": "🏷️ 重要程度", "value": level, "inline": True},
        {"name": "⚖️ 市場判斷", "value": judge, "inline": True},
        {"name": "📈 訊號", "value": tag, "inline": True},
        {"name": "📰 新聞來源", "value": post.get("source", "Google News"), "inline": True},
    ]

    pub = post.get("published")
    if pub:
        fields.append({"name": "🕒 發布時間", "value": str(pub)[:40], "inline": True})
    else:
        fields.append({"name": "🕒 推播時間", "value": now.strftime("%H:%M (台北)"), "inline": True})

    embed: Dict = {
        "title": f"{market_label}｜{title}",
        "color": color,
        "fields": fields,
        "footer": {"text": "Smart News Radar System"},
    }
    if link:
        embed["url"] = link
    return embed

# ----------------------------
# Discord sending
# ----------------------------
def post_webhook(payload: Dict) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("缺少 NEWS_WEBHOOK_URL（GitHub Secrets / env）")
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=20)
    if r.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {r.status_code} {r.text[:800]}")

def send_embeds_in_batches(embeds: List[Dict]) -> None:
    for i in range(0, len(embeds), MAX_EMBEDS_PER_REQ):
        batch = embeds[i:i + MAX_EMBEDS_PER_REQ]
        post_webhook({"embeds": batch})
        time.sleep(0.6)

# ----------------------------
# Main logic
# ----------------------------
def build_market_embeds(market: str, now: dt.datetime, cache: set[str]) -> Tuple[List[Dict], set[str]]:
    if market == "TW":
        header_title = "🏹 台股市場快訊"
        rss_url = RSS_TW.format(query=QUERY_TW)
        index_line = get_index_snapshot("TW")
        market_label = "台股"
    elif market == "US":
        header_title = "⚡ 美股市場快訊"
        rss_url = RSS_US.format(query=QUERY_US)
        index_line = get_index_snapshot("US")
        market_label = "美股"
    else:
        header_title = "🪙 Crypto 市場快訊"
        rss_url = RSS_CRYPTO.format(query=QUERY_CRYPTO)
        index_line = get_index_snapshot("CRYPTO")
        market_label = "Crypto"

    posts = fetch_rss(rss_url)
    new_posts = [p for p in posts if p["key"] not in cache][:MAX_NEWS_PER_MARKET]

    embeds: List[Dict] = []
    embeds.append(_build_header_embed(header_title, now, index_line))

    if not new_posts:
        embeds.append({
            "title": f"{market_label}｜本次沒有新的更新",
            "description": "（已依 sent_news.txt 去重）",
            "color": COLOR_MAP["一般"],
            "footer": {"text": "Smart News Radar System"},
        })
        return embeds, cache

    for p in new_posts:
        embeds.append(_build_news_embed(market_label, p, now))
        cache.add(p["key"])

    return embeds, cache

def main() -> None:
    now = dt.datetime.now(TZ_TAIPEI)
    cache = load_cache()

    # 依你原本的時段邏輯：白天推台股、晚上推美股
    is_tw_hours = (8 <= now.hour < 17)

    embeds_all: List[Dict] = []
    if is_tw_hours:
        tw_embeds, cache = build_market_embeds("TW", now, cache)
        embeds_all.extend(tw_embeds)
    else:
        us_embeds, cache = build_market_embeds("US", now, cache)
        embeds_all.extend(us_embeds)

    # Crypto 每次都推（你說以台股/美股/Crypto為主）
    crypto_embeds, cache = build_market_embeds("CRYPTO", now, cache)
    embeds_all.extend(crypto_embeds)

    send_embeds_in_batches(embeds_all)
    save_cache(cache)

    print(f"✅ Sent embeds: {len(embeds_all)} | Cache size: {len(cache)}")

if __name__ == "__main__":
    main()

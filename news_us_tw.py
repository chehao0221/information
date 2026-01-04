# -*- coding: utf-8 -*-
"""
Information push bot (TW / US / Crypto) -> Discord

重要：此版本把「顯示方式」恢復成你舊圖的風格：一則新聞一張 Embed 卡片，
並依「重大/中級/一般」套用紅/黃/綠顏色。

由於 Google News RSS 不提供完整欄位（來源/時間/摘要），本腳本用「可解釋」的方式補齊：
- 新聞來源：固定顯示 Google News
- 發布時間：以推播時間（台北）顯示
- 市場判斷/利多利空：用標題關鍵字簡單分類（可自行調整 KEYWORDS_*）
"""

import datetime
import os
import re
import urllib.parse
from typing import Dict, List, Tuple

import feedparser
import requests

# =========================
# 基本設定
# =========================
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "12"))
MAX_ITEMS_PER_MARKET = int(os.getenv("MAX_ITEMS_PER_MARKET", "8"))  # 每個市場最多幾則新聞
# Discord 限制：一次 webhook 最多 10 embeds
MAX_EMBEDS_PER_REQUEST = 10

# =========================
# 重要性分級（可自行微調）
# =========================
# 重大（紅）
KEYWORDS_MAJOR = [
    "暴跌", "崩盤", "熔斷", "緊急", "違約", "破產", "下調評級", "裁員", "制裁",
    "升息", "降息", "利率決議", "FOMC", "CPI", "PCE", "NFP", "非農",
    "地緣", "戰爭", "衝突", "停火", "封鎖",
    "SEC", "訴訟", "判決", "調查",
    "ETF核准", "ETF獲批", "駭客", "被盜", "黑客",
]
# 中級（黃）
KEYWORDS_MEDIUM = [
    "財報", "展望", "指引", "營收", "毛利", "EPS", "獲利", "下修", "上修",
    "併購", "收購", "合作", "投資", "發表", "推出",
    "美元", "美債", "殖利率", "通膨", "油價", "金價",
    "比特幣", "以太坊", "BTC", "ETH", "加密", "幣圈",
]
# 一般（綠）= 其他

COLOR_RED = 0xE74C3C
COLOR_YELLOW = 0xF1C40F
COLOR_GREEN = 0x2ECC71

FOOTER_TEXT = "Smart News Radar System"


# =========================
# 工具函式
# =========================
def _ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)


def _normalize_title(t: str) -> str:
    t = (t or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _load_sent_titles() -> List[str]:
    if not os.path.exists(CACHE_FILE):
        return []
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _save_sent_titles(titles: List[str]) -> None:
    # 去重 + 控制大小（保留最新 1500 筆）
    seen = set()
    out: List[str] = []
    for t in titles:
        nt = _normalize_title(t)
        if not nt or nt in seen:
            continue
        seen.add(nt)
        out.append(nt)
    out = out[:1500]
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + ("\n" if out else ""))


def _fetch_google_news(query: str) -> List[Dict[str, str]]:
    q = urllib.parse.quote_plus(query)
    url = GOOGLE_NEWS_RSS.format(query=q)
    feed = feedparser.parse(url)
    posts: List[Dict[str, str]] = []
    for e in (feed.entries or []):
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        if not title or not link:
            continue
        posts.append({"title": title, "link": link})
    return posts


def _dedupe(posts: List[Dict[str, str]], sent_titles: List[str]) -> List[Dict[str, str]]:
    sent = set(_normalize_title(t) for t in sent_titles)
    out: List[Dict[str, str]] = []
    for p in posts:
        nt = _normalize_title(p.get("title", ""))
        if not nt or nt in sent:
            continue
        out.append(p)
    return out


def _classify_level(title: str) -> Tuple[str, int]:
    """回傳 (等級字串, embed_color)"""
    t = title or ""
    for kw in KEYWORDS_MAJOR:
        if kw and kw in t:
            return "重大", COLOR_RED
    for kw in KEYWORDS_MEDIUM:
        if kw and kw in t:
            return "中級", COLOR_YELLOW
    return "一般", COLOR_GREEN


def _extract_ticker_hint(title: str) -> str:
    """
    嘗試從標題抓出類似：
    - 2330.TW
    - TSLA, AAPL
    - BTC, ETH
    回傳用於卡片標題前綴，抓不到就回空字串。
    """
    if not title:
        return ""
    m = re.search(r"\b(\d{4}\.TW)\b", title)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-Z]{2,6})\b", title)
    if m and m.group(1) not in {"OR", "AND", "THE"}:
        return m.group(1)
    return ""


def _build_header_embed(market_title: str, taipei_now: datetime.datetime) -> Dict:
    return {
        "title": market_title,
        "description": taipei_now.strftime("%Y-%m-%d %H:%M（台北）"),
        "color": 0x95A5A6,  # 灰色做總標題
        "footer": {"text": FOOTER_TEXT},
    }


def _build_news_embed(market: str, post: Dict[str, str], taipei_now: datetime.datetime) -> Dict:
    title = post["title"]
    url = post["link"]
    level, color = _classify_level(title)

    ticker = _extract_ticker_hint(title)
    card_title = f"{ticker} | {title}" if ticker else title
    if len(card_title) > 256:
        card_title = card_title[:253] + "..."

    fields = [
        {"name": "🏷️ 等級", "value": level, "inline": True},
        {"name": "📌 市場", "value": market, "inline": True},
        {"name": "📰 新聞來源", "value": "Google News", "inline": True},
        {"name": "🕒 發布時間", "value": taipei_now.strftime("%H:%M（台北）"), "inline": True},
    ]

    # 你舊圖有「市場判斷 / 利多」等欄位：這裡用簡單可調的規則填入
    # （之後你要完全對齊舊倉庫的規則，可以把舊倉庫那段分類/打分邏輯貼過來，我再直接搬）
    bias = "利多" if level in ("重大", "中級") else "一般"
    judge = "市場波動" if level == "重大" else ("關注事件" if level == "中級" else "例行更新")
    fields.extend(
        [
            {"name": "⚖️ 市場判斷", "value": judge, "inline": True},
            {"name": "📈 利多/利空", "value": bias, "inline": True},
        ]
    )

    return {
        "title": card_title,
        "url": url,
        "color": color,
        "fields": fields,
        "footer": {"text": FOOTER_TEXT},
    }


def _post_webhook(payload: Dict) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ NEWS_WEBHOOK_URL 未設定，跳過推播。")
        return
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=HTTP_TIMEOUT)
    if r.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {r.status_code} {r.text[:500]}")


def send_embeds_in_batches(embeds: List[Dict]) -> None:
    """
    Discord webhook：一次最多 10 embeds
    """
    if not embeds:
        return
    batch: List[Dict] = []
    for e in embeds:
        batch.append(e)
        if len(batch) >= MAX_EMBEDS_PER_REQUEST:
            _post_webhook({"embeds": batch})
            batch = []
    if batch:
        _post_webhook({"embeds": batch})


# =========================
# 主流程
# =========================
def run_push(label: str) -> None:
    """
    以「台股 / 美股 / Crypto」為主。
    顯示方式：每個市場先送一張總標題卡，再「每則新聞一張卡」。
    """
    _ensure_data_dir()
    sent_titles = _load_sent_titles()

    # 主要關鍵字（你可以之後再自行微調）
    tw_query = "台股 OR 台灣 股市 OR 加權指數 OR 台指期 OR 台積電"
    us_query = "美股 OR 美國 股市 OR 道瓊 OR 那斯達克 OR 標普500 OR 聯準會 OR Fed"
    crypto_query = "比特幣 OR 以太坊 OR 加密貨幣 OR Bitcoin OR Ethereum"

    tw_posts = _dedupe(_fetch_google_news(tw_query), sent_titles)[:MAX_ITEMS_PER_MARKET]
    us_posts = _dedupe(_fetch_google_news(us_query), sent_titles)[:MAX_ITEMS_PER_MARKET]
    crypto_posts = _dedupe(_fetch_google_news(crypto_query), sent_titles)[:MAX_ITEMS_PER_MARKET]

    if not (tw_posts or us_posts or crypto_posts):
        print("✅ 無新內容（可能都已推播過），跳過。")
        return

    taipei_tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(taipei_tz)

    embeds: List[Dict] = []

    if tw_posts:
        embeds.append(_build_header_embed("🏹 台股市場快訊", now))
        embeds.extend([_build_news_embed("台股", p, now) for p in tw_posts])

    if us_posts:
        embeds.append(_build_header_embed("⚡ 美股市場快訊", now))
        embeds.extend([_build_news_embed("美股", p, now) for p in us_posts])

    if crypto_posts:
        embeds.append(_build_header_embed("🪙 Crypto 市場快訊", now))
        embeds.extend([_build_news_embed("Crypto", p, now) for p in crypto_posts])

    # 送出（分批）
    send_embeds_in_batches(embeds)

    # 更新快取：把本次新推播的 title 加入（放前面，避免重複）
    new_titles = [p["title"] for p in (tw_posts + us_posts + crypto_posts)]
    _save_sent_titles(new_titles + sent_titles)


def _label_by_time(taipei_now: datetime.datetime) -> str:
    """
    保留你原本的時段標籤（workflow 只是用這個做標題/辨識）
    """
    h = taipei_now.hour
    m = taipei_now.minute

    # 08:30 左右
    if h == 8 and 0 <= m <= 59:
        return "🏹 台股市場快訊"
    # 13:30 左右
    if h == 13 and 0 <= m <= 59:
        return "🏹 台股午盤快訊"
    # 21:30 左右
    if h == 21 and 0 <= m <= 59:
        return "⚡ 美股盤前快訊"
    # 06:00 左右
    if h == 6 and 0 <= m <= 59:
        return "🌙 美股盤後回顧"

    # fallback：手動觸發或不在排程時段
    if 8 <= h < 17:
        return "🏹 台股快訊"
    return "⚡ 美股快訊"


if __name__ == "__main__":
    taipei_tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(taipei_tz)
    label = _label_by_time(now)
    run_push(label)

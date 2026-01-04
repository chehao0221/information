# -*- coding: utf-8 -*-
"""
台股 / 美股 / Crypto 市場快訊（Discord Webhook）

顯示方式：一則新聞一個 embed（卡片），並附市場區塊標題卡。
- 台股：藍色
- 美股：紅色
- Crypto：黃色
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from typing import Dict, List, Optional, Tuple

import feedparser
import requests
import yfinance as yf


# =========================
# 設定
# =========================
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"
HTTP_TIMEOUT = 15

# Discord limits
MAX_EMBEDS_PER_MESSAGE = 10
MAX_TITLE_LEN = 256
MAX_FIELD_VALUE_LEN = 1024
MAX_DESC_LEN = 4096

# Colors (decimal)
COLOR_TW = 0x3498DB   # blue
COLOR_US = 0xE74C3C   # red
COLOR_CRYPTO = 0xF1C40F  # yellow

# Google News RSS endpoint
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


# =========================
# 小工具
# =========================
def _ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)


def _load_sent_keys() -> set:
    if not os.path.exists(CACHE_FILE):
        return set()
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return set([line.strip() for line in f if line.strip()])


def _append_sent_keys(keys: List[str]) -> None:
    if not keys:
        return
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        for k in keys:
            f.write(k + "\n")


def _truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else (s[: max(0, n - 1)] + "…")


def _fmt_taipei_now() -> str:
    # GitHub Actions 預設 UTC，這裡用 UTC+8 顯示（台北）
    now_utc = _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc)
    now_tw = now_utc.astimezone(_dt.timezone(_dt.timedelta(hours=8)))
    return now_tw.strftime("%Y-%m-%d %H:%M")


def _safe_field(name: str, value: str, inline: bool = False) -> Dict:
    name = _truncate(name, MAX_TITLE_LEN)
    value = value if value else "—"
    value = _truncate(value, MAX_FIELD_VALUE_LEN)
    return {"name": name, "value": value, "inline": inline}


def _http_get(url: str, params: Optional[dict] = None) -> str:
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def _fetch_google_news(query: str, lang: str = "zh-TW", region: str = "TW") -> List[dict]:
    """
    回傳 list[{"title": str, "publisher": str, "link": str, "published": str}]
    """
    params = {"q": query, "hl": lang, "gl": region, "ceid": f"{region}:{lang}"}
    rss_text = _http_get(GOOGLE_NEWS_RSS, params=params)
    feed = feedparser.parse(rss_text)

    posts: List[dict] = []
    for e in feed.entries[:50]:
        raw_title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        published = (e.get("published") or e.get("updated") or "").strip()

        # Google News title 常是 "headline - Publisher"
        headline, publisher = _split_headline_publisher(raw_title)
        posts.append(
            {
                "headline": headline,
                "publisher": publisher,
                "title": raw_title,
                "link": link,
                "published": published,
            }
        )
    return posts


def _split_headline_publisher(raw_title: str) -> Tuple[str, str]:
    # 最後一段當 publisher（盡量貼近你舊版）
    parts = [p.strip() for p in raw_title.split(" - ") if p.strip()]
    if len(parts) >= 2:
        return " - ".join(parts[:-1]).strip(), parts[-1].strip()
    return raw_title.strip(), ""


def _make_dedupe_key(post: dict) -> str:
    # 以 link 為主，避免標題微調造成重發
    return post.get("link") or post.get("title") or ""


def _dedupe(posts: List[dict], sent: set) -> Tuple[List[dict], List[str]]:
    new_posts: List[dict] = []
    new_keys: List[str] = []
    for p in posts:
        k = _make_dedupe_key(p)
        if not k or k in sent:
            continue
        new_posts.append(p)
        new_keys.append(k)
    return new_posts, new_keys


_POS_KW = ["大漲", "上漲", "強彈", "創高", "利多", "看好", "買盤", "續強", "反彈", "上攻", "飆", "噴"]
_NEG_KW = ["大跌", "下跌", "崩", "重挫", "利空", "警訊", "恐慌", "回檔", "下修", "走弱", "暴跌"]


def _judge_from_headline(headline: str) -> Tuple[str, str]:
    """
    回傳 (市場判斷, 利多/利空/中性)
    """
    h = headline or ""
    if any(k in h for k in _POS_KW):
        return "偏多", "利多"
    if any(k in h for k in _NEG_KW):
        return "偏空", "利空"
    return "中性", "中性"


_TW_TICKER_RE = re.compile(r"\b(\d{4}\.TW)\b")
_US_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")


def _extract_ticker(headline: str, market: str) -> Optional[str]:
    if market == "TW":
        m = _TW_TICKER_RE.search(headline or "")
        return m.group(1) if m else None
    if market == "US":
        # 避免抓到太多無關大寫詞：只在有「股」或「NYSE/Nasdaq」等線索時才嘗試
        h = headline or ""
        if not any(x in h for x in ["股", "NYSE", "Nasdaq", "NASDAQ", "美股", "美國"]):
            return None
        # 取第一個較像 ticker 的大寫字串（簡單保守）
        for m in _US_TICKER_RE.finditer(h):
            t = m.group(1)
            if t in {"OR", "AND", "THE", "FED", "BTC", "ETH"}:
                continue
            if 1 <= len(t) <= 5:
                return t
        return None
    if market == "CRYPTO":
        if "ETH" in (headline or "").upper() or "以太" in (headline or ""):
            return "ETH-USD"
        if "BTC" in (headline or "").upper() or "比特" in (headline or ""):
            return "BTC-USD"
        return None
    return None


def _get_quote(ticker: str) -> Optional[str]:
    """
    回傳 "1585.00 (+2.26%)" 類型文字（取最近一筆 close & 前一筆 close）
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d", interval="1d")
        if hist is None or hist.empty or len(hist["Close"]) < 2:
            return None
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            return None
        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        chg = last - prev
        pct = (chg / prev) * 100 if prev else 0.0
        sign = "+" if chg >= 0 else ""
        return f"{last:.2f} ({sign}{pct:.2f}%)"
    except Exception:
        return None


def _get_index_line(market: str) -> Optional[str]:
    """
    台股：加權指數 ^TWII
    美股：那斯達克 ^IXIC
    Crypto：BTC-USD
    """
    if market == "TW":
        name, ticker = "加權指數", "^TWII"
    elif market == "US":
        name, ticker = "那斯達克", "^IXIC"
    else:
        name, ticker = "比特幣(BTC)", "BTC-USD"

    q = _get_quote(ticker)
    if not q:
        return None
    return f"{name}: {q}"


def _build_header_embed(market_name: str, market: str) -> dict:
    now = _fmt_taipei_now()
    idx = _get_index_line(market)
    title = f"{market_name}市場快訊"
    desc_lines = [f"📅 {now}"]
    if idx:
        desc_lines.append(f"📊 {idx}")
    description = "\n".join(desc_lines)
    color = COLOR_TW if market == "TW" else COLOR_US if market == "US" else COLOR_CRYPTO
    return {
        "title": _truncate(title, MAX_TITLE_LEN),
        "description": _truncate(description, MAX_DESC_LEN),
        "color": color,
    }


def _build_news_embed(post: dict, market: str) -> dict:
    headline = post.get("headline") or post.get("title") or ""
    publisher = post.get("publisher") or ""
    link = post.get("link") or ""
    published = post.get("published") or ""

    judgement, sentiment = _judge_from_headline(headline)
    ticker = _extract_ticker(headline, market)
    quote = _get_quote(ticker) if ticker else None

    color = COLOR_TW if market == "TW" else COLOR_US if market == "US" else COLOR_CRYPTO

    fields = []
    fields.append(_safe_field("⚖️ 市場判斷", judgement, inline=True))
    fields.append(_safe_field("📈 利多/利空", sentiment, inline=True))
    if quote:
        fields.append(_safe_field("💹 即時價格", quote, inline=True))
    if published:
        # 盡量貼近你舊版「發布時間」呈現（取字串，不硬轉時區）
        fields.append(_safe_field("🕒 發布時間", published, inline=False))
    if publisher:
        fields.append(_safe_field("📰 新聞來源", publisher, inline=True))

    embed = {
        "title": _truncate(headline, MAX_TITLE_LEN),
        "url": link,  # 點標題即可開連結（不會額外 unfurl）
        "color": color,
        "fields": fields,
        "footer": {"text": "Smart News Radar System"},
    }

    return embed


def _post_webhook(embeds: List[dict]) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ NEWS_WEBHOOK_URL 未設定，跳過推播。")
        return
    payload = {
        "embeds": embeds,
    }
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=HTTP_TIMEOUT)
    if r.status_code >= 300:
        raise RuntimeError(f"Discord webhook failed: {r.status_code} {r.text[:800]}")


def _send_market_block(market: str, market_name: str, posts: List[dict]) -> None:
    if not posts:
        return

    header = _build_header_embed(market_name, market)
    news_embeds = [_build_news_embed(p, market) for p in posts]

    # Discord 一次最多 10 個 embeds：header + 9 news
    i = 0
    first = True
    while i < len(news_embeds):
        batch_news = news_embeds[i : i + (MAX_EMBEDS_PER_MESSAGE - 1)]
        embeds = []
        if first:
            embeds.append(header)
            first = False
        else:
            # 續頁也加一個簡短 header，方便閱讀（但保持很短）
            cont_header = dict(header)
            cont_header["title"] = _truncate(f"{market_name}市場快訊（續）", MAX_TITLE_LEN)
            embeds.append(cont_header)

        embeds.extend(batch_news)
        _post_webhook(embeds)
        i += (MAX_EMBEDS_PER_MESSAGE - 1)


def run_push() -> None:
    _ensure_data_dir()
    sent = _load_sent_keys()

    # 主要關鍵字（維持你原本方向：台股 / 美股 / Crypto）
    tw_query = "台股 OR 台灣 股市 OR 加權指數 OR 台指期 OR 台積電"
    us_query = "美股 OR 美國 股市 OR 道瓊 OR 那斯達克 OR 標普500 OR 聯準會 OR Fed"
    crypto_query = "比特幣 OR 以太坊 OR 加密貨幣 OR Bitcoin OR Ethereum"

    tw_posts, tw_keys = _dedupe(_fetch_google_news(tw_query), sent)
    us_posts, us_keys = _dedupe(_fetch_google_news(us_query), sent)
    crypto_posts, crypto_keys = _dedupe(_fetch_google_news(crypto_query), sent)

    any_sent_keys: List[str] = []

    if tw_posts:
        _send_market_block("TW", "台股", tw_posts)
        any_sent_keys += tw_keys
    if us_posts:
        _send_market_block("US", "美股", us_posts)
        any_sent_keys += us_keys
    if crypto_posts:
        _send_market_block("CRYPTO", "Crypto", crypto_posts)
        any_sent_keys += crypto_keys

    if any_sent_keys:
        _append_sent_keys(any_sent_keys)
        print(f"✅ Sent {len(any_sent_keys)} new items.")
    else:
        print("ℹ️ No new items.")


if __name__ == "__main__":
    run_push()

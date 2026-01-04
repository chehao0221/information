import datetime
import os
import re
import urllib.parse
from typing import Dict, List

import feedparser
import requests


# =========================
# 設定
# =========================
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()
CACHE_FILE = "data/sent_news.txt"

# Google News RSS
# 語系：繁中（台灣）
GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"

# 最多推播幾則（每個分類）
MAX_ITEMS_PER_SECTION = 6
# 快取最多保留幾筆（避免 repo 越來越大）
CACHE_KEEP_LIMIT = 300

# Requests timeout
HTTP_TIMEOUT = 12


def _ensure_data_dir() -> None:
    if not os.path.exists("data"):
        os.makedirs("data", exist_ok=True)


def _normalize_title(title: str) -> str:
    # 簡單正規化：去空白、降噪符號、轉小寫
    t = (title or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _load_sent_titles() -> List[str]:
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []


def _save_sent_titles(titles: List[str]) -> None:
    _ensure_data_dir()
    # 去重 + 限制長度
    seen = set()
    cleaned: List[str] = []
    for t in titles:
        nt = _normalize_title(t)
        if not nt or nt in seen:
            continue
        seen.add(nt)
        cleaned.append(t.strip())
    cleaned = cleaned[:CACHE_KEEP_LIMIT]
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        for t in cleaned:
            f.write(f"{t}\n")


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
    sent_norm = set(_normalize_title(t) for t in sent_titles)
    out: List[Dict[str, str]] = []
    for p in posts:
        nt = _normalize_title(p.get("title", ""))
        if not nt or nt in sent_norm:
            continue
        out.append(p)
    return out


def _build_section_lines(posts: List[Dict[str, str]], limit: int) -> str:
    # Discord Embed description 上限 4096，保守截斷
    lines: List[str] = []
    for p in posts[:limit]:
        title = p["title"]
        link = p["link"]
        lines.append(f"• [{title}]({link})")
    text = "\n".join(lines)
    return text[:3900]  # 留 buffer


def send_to_discord(title: str, sections: List[Dict[str, str]]) -> None:
    """
    Send to Discord via webhook.
    Discord limits (rough):
      - embed.description: 4096 chars
      - embeds per message: 10
    sections: [{"name": "台股", "content": "..."} , ...]
    """
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ NEWS_WEBHOOK_URL 未設定，跳過推播。")
        return

    # Build blocks in the same display style: **區塊名** + 內容（多行）
    blocks: List[str] = []
    for s in sections:
        name = (s.get("name") or "").strip()
        content = (s.get("content") or "").strip()
        if not content:
            continue
        if name:
            blocks.append(f"**{name}**\n{content}")
        else:
            blocks.append(content)

    combined = "\n\n".join(blocks).strip()
    if not combined:
        combined = "（本次沒有新的更新）"

    # Split into chunks that fit embed.description
    max_desc = 3900  # leave headroom for safety
    lines = combined.splitlines()
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for line in lines:
        # +1 for newline
        add = len(line) + (1 if buf else 0)
        if size + add > max_desc:
            chunks.append("\n".join(buf).strip())
            buf = [line]
            size = len(line)
        else:
            if buf:
                buf.append(line)
                size += len(line) + 1
            else:
                buf = [line]
                size = len(line)
    if buf:
        chunks.append("\n".join(buf).strip())

    # Discord max 10 embeds per message. If more, merge overflow into the last embed (truncate).
    if len(chunks) > 10:
        head = chunks[:9]
        tail = "\n\n".join(chunks[9:])
        tail = tail[:max_desc]
        chunks = head + [tail]

    embeds = []
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    for i, desc in enumerate(chunks):
        emb = {
            "description": desc or "（空白）",
            "timestamp": now,
        }
        if i == 0:
            emb["title"] = (title or "News")[:256]
        embeds.append(emb)

    payload = {"embeds": embeds}

    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=HTTP_TIMEOUT)
    except Exception as e:
        print(f"❌ Discord webhook request error: {e}")
        return

    if r.status_code >= 300:
        # Don't hard-fail the whole workflow; log details for debugging.
        print(f"❌ Discord webhook failed: {r.status_code} {r.text[:500]}")
        return

def run_push(label: str) -> None:
    """
    以「台股 / 美股 / Crypto」為主，每次推播固定三段（內容不足就略過）。
    """
    _ensure_data_dir()
    sent_titles = _load_sent_titles()

    # 主要關鍵字（你可以之後再自行微調）
    tw_query = "台股 OR 台灣 股市 OR 加權指數 OR 台指期 OR 台積電"
    us_query = "美股 OR 美國 股市 OR 道瓊 OR 那斯達克 OR 標普500 OR 聯準會 OR Fed"
    crypto_query = "比特幣 OR 以太坊 OR 加密貨幣 OR Bitcoin OR Ethereum"

    tw_posts = _dedupe(_fetch_google_news(tw_query), sent_titles)
    us_posts = _dedupe(_fetch_google_news(us_query), sent_titles)
    crypto_posts = _dedupe(_fetch_google_news(crypto_query), sent_titles)

    sections = []
    if tw_posts:
        sections.append({"name": "🏹 台股", "content": _build_section_lines(tw_posts, MAX_ITEMS_PER_SECTION)})
    if us_posts:
        sections.append({"name": "⚡ 美股", "content": _build_section_lines(us_posts, MAX_ITEMS_PER_SECTION)})
    if crypto_posts:
        sections.append({"name": "🪙 Crypto", "content": _build_section_lines(crypto_posts, MAX_ITEMS_PER_SECTION)})

    if not sections:
        print("✅ 無新內容（可能都已推播過），跳過。")
        return

    send_to_discord(label, sections)

    # 更新快取：把本次新推播的 title 加入
    new_titles = [p["title"] for p in (tw_posts[:MAX_ITEMS_PER_SECTION] + us_posts[:MAX_ITEMS_PER_SECTION] + crypto_posts[:MAX_ITEMS_PER_SECTION])]
    _save_sent_titles(new_titles + sent_titles)


def _label_by_time(taipei_now: datetime.datetime) -> str:
    """
    依照你的 workflow 時段給固定標題（顯示方式保持你原本「時段標籤」邏輯）。
    """
    h = taipei_now.hour
    m = taipei_now.minute

    # 08:30 左右
    if h == 8 and 0 <= m <= 59:
        return "🏹 台股開盤預報"
    # 15:30 左右
    if h == 15 and 0 <= m <= 59:
        return "📊 台股盤後總結"
    # 21:30 左右
    if h == 21 and 0 <= m <= 59:
        return "⚡ 美股開盤前夕"
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

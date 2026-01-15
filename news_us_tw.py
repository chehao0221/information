import os
import time
import hashlib
import datetime
from typing import Dict, List, Optional

import requests
import feedparser

# ======================
# 基本設定
# ======================
TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(TZ)

DATA_DIR = "data"
CACHE_FILE = os.path.join(DATA_DIR, "sent_news.txt")

FEEDS = {
    "TW": "https://news.google.com/rss/search?q=台股&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
    "US": "https://news.google.com/rss/search?q=US+stock+market&hl=en-US&gl=US&ceid=US:en",
    "CRYPTO": "https://news.google.com/rss/search?q=cryptocurrency+bitcoin+ethereum&hl=en&gl=US&ceid=US:en",
}

WEBHOOKS = {
    "TW": os.getenv("NEWS_WEBHOOK_TW", ""),
    "US": os.getenv("NEWS_WEBHOOK_US", ""),
    "CRYPTO": os.getenv("NEWS_WEBHOOK_CRYPTO", ""),
}

COLOR_MAP = {
    "重大": 0xFF0000,
    "中級": 0xFFAA00,
    "一般": 0x00FF00,
}

# Discord Embed limits (https://discord.com/developers/docs/resources/channel#embed-object-embed-limits)
_EMBED_TITLE_MAX = 256
_EMBED_DESC_MAX = 4096
_EMBED_FIELD_NAME_MAX = 256
_EMBED_FIELD_VALUE_MAX = 1024
_EMBED_COUNT_MAX_PER_MESSAGE = 10

# ======================
# 工具函式
# ======================
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        open(CACHE_FILE, "w", encoding="utf-8").close()

def load_sent_ids() -> set:
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_ids(ids: List[str]):
    if not ids:
        return
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        for i in ids:
            f.write(i + "\n")

def hash_post(title: str, link: str) -> str:
    return hashlib.md5(f"{title}|{link}".encode("utf-8")).hexdigest()

def judge_level(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["崩盤", "暴跌", "crash", "fed", "cpi", "利率"]):
        return "重大"
    if any(k in t for k in ["財報", "展望", "反彈", "回檔"]):
        return "中級"
    return "一般"


def _clean_text(s: str) -> str:
    """Remove control chars that Discord may reject."""
    if not s:
        return ""
    # keep common whitespace; drop other C0 controls
    return "".join(ch for ch in str(s) if (ch == "\n" or ch == "\t" or ord(ch) >= 32))


def _truncate(s: str, max_len: int) -> str:
    s = _clean_text(s).strip()
    if len(s) <= max_len:
        return s
    # Use a single unicode ellipsis; keep within max_len
    return s[: max(0, max_len - 1)].rstrip() + "…"


def _safe_url(url: str) -> str:
    url = _clean_text(url).strip()
    # Discord requires either http(s) or omission
    if not (url.startswith("http://") or url.startswith("https://")):
        return ""
    # practical safety cap
    return url[:2048]

# ======================
# Embed 建立（關鍵）
# ======================
def build_header_embed(title: str) -> Dict:
    return {
        "title": _truncate(f"📊 {title}", _EMBED_TITLE_MAX),
        "description": _truncate(
            f"更新時間：{NOW.strftime('%Y-%m-%d %H:%M')}", _EMBED_DESC_MAX
        ),
        "color": 0x2F3136,
    }

def build_news_embed(market: str, title: str, link: str, level: str) -> Optional[Dict]:
    title = _clean_text(title).strip()
    link = _safe_url(link)

    # ❗最重要的防呆：沒有標題或連結，直接丟棄
    if not title or not link:
        return None

    embed_title = _truncate(f"[{market}] {title}", _EMBED_TITLE_MAX)
    return {
        "title": embed_title,
        "url": link,
        "color": COLOR_MAP.get(level, 0x00FF00),
        "fields": [
            {
                "name": _truncate("重要程度", _EMBED_FIELD_NAME_MAX),
                "value": _truncate(level, _EMBED_FIELD_VALUE_MAX),
                "inline": True,
            },
            {
                "name": _truncate("來源", _EMBED_FIELD_NAME_MAX),
                "value": _truncate("Google News", _EMBED_FIELD_VALUE_MAX),
                "inline": True,
            },
            {
                "name": _truncate("時間", _EMBED_FIELD_NAME_MAX),
                "value": _truncate(NOW.strftime("%H:%M"), _EMBED_FIELD_VALUE_MAX),
                "inline": True,
            },
        ],
        "footer": {"text": "Smart News Radar System"},
    }

# ======================
# Discord 發送
# ======================
def send_embeds(webhook: str, embeds: List[Dict]):
    if not webhook or not embeds:
        return

    # Discord 限制：一次最多 10 個 embeds
    for i in range(0, len(embeds), _EMBED_COUNT_MAX_PER_MESSAGE):
        batch = embeds[i : i + _EMBED_COUNT_MAX_PER_MESSAGE]
        payload = {"embeds": batch}
        r = requests.post(webhook, json=payload, timeout=10)
        if r.status_code < 300:
            continue

        # 如果某個 embed 壞掉，Discord 會回 400 embeds:["N"]。
        # 為了避免整個 job 失敗，改成逐條送並略過壞的那一條。
        if r.status_code == 400:
            bad_count = 0
            for idx, one in enumerate(batch):
                rr = requests.post(webhook, json={"embeds": [one]}, timeout=10)
                if rr.status_code >= 300:
                    bad_count += 1
                    print(
                        f"⚠️ skip bad embed (batch_index={i}, idx={idx}): {rr.status_code} {rr.text[:200]}"
                    )
            if bad_count > 0:
                continue

        raise RuntimeError(f"Discord webhook failed: {r.status_code} {r.text[:300]}")

# ======================
# 主流程（單一市場）
# ======================
def run_market(market: str, title: str):
    webhook = WEBHOOKS.get(market)
    if not webhook:
        print(f"⚠️ {market} webhook not set, skip")
        return

    feed = feedparser.parse(FEEDS[market])
    sent_ids = load_sent_ids()
    new_ids: List[str] = []

    embeds: List[Dict] = []
    embeds.append(build_header_embed(title))

    for entry in feed.entries[:10]:
        t = entry.get("title", "")
        l = entry.get("link", "")
        hid = hash_post(t, l)

        if hid in sent_ids:
            continue

        level = judge_level(t)
        embed = build_news_embed(market, t, l, level)

        # ❗第二層防呆：embed 無效就不加
        if not embed:
            continue

        embeds.append(embed)
        new_ids.append(hid)

    # 只有 header + 新聞 才送
    if len(embeds) > 1:
        send_embeds(webhook, embeds)
        save_sent_ids(new_ids)
        print(f"✅ {market} sent {len(new_ids)} news")
    else:
        print(f"ℹ️ {market} no new news")

# ======================
# main
# ======================
def main():
    ensure_data_dir()

    run_market("TW", "台股市場快訊")
    time.sleep(1)

    run_market("US", "美股市場快訊")
    time.sleep(1)

    run_market("CRYPTO", "Crypto 市場快訊")

if __name__ == "__main__":
    main()

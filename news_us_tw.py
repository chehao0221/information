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

# ======================
# Embed 建立（關鍵）
# ======================
def build_header_embed(title: str) -> Dict:
    return {
        "title": f"📊 {title}",
        "description": f"更新時間：{NOW.strftime('%Y-%m-%d %H:%M')}",
        "color": 0x2F3136,
    }

def build_news_embed(market: str, title: str, link: str, level: str) -> Optional[Dict]:
    title = title.strip()
    link = link.strip()

    # ❗最重要的防呆：沒有標題或連結，直接丟棄
    if not title or not link:
        return None

    return {
        "title": f"[{market}] {title}",
        "url": link,
        "color": COLOR_MAP.get(level, 0x00FF00),
        "fields": [
            {"name": "重要程度", "value": level, "inline": True},
            {"name": "來源", "value": "Google News", "inline": True},
            {"name": "時間", "value": NOW.strftime("%H:%M"), "inline": True},
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
    for i in range(0, len(embeds), 10):
        payload = {"embeds": embeds[i : i + 10]}
        r = requests.post(webhook, json=payload, timeout=10)
        if r.status_code >= 300:
            raise RuntimeError(
                f"Discord webhook failed: {r.status_code} {r.text[:300]}"
            )

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

    # --- 新增：安靜時間檢查 ---
    if _is_quiet_hours():
        print(f"🌙 目前時間 {NOW.strftime('%H:%M')} 屬於安靜時段 (23:00-05:00)，停止發送。")
        return  # 直接結束程式，後續的抓取與發送都不會執行
    # -----------------------

    run_market("TW", "台股市場快訊")
    time.sleep(1)

    run_market("US", "美股市場快訊")
    time.sleep(1)

    run_market("CRYPTO", "Crypto 市場快訊")

if __name__ == "__main__":
    main()

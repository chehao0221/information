import yfinance as yf
import pandas as pd
import numpy as np
import requests
import datetime
import os
import feedparser
import urllib.parse
from xgboost import XGBRegressor
import warnings

warnings.filterwarnings("ignore")

# 讀取 Webhook
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

def get_live_news(query):
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        # 每次執行只抓取最最新的一則新聞，避免洗版
        if feed.entries:
            entry = feed.entries[0]
            clean_title = entry.title.split(" - ")[0]
            return {"title": clean_title, "link": entry.link}
        return None
    except:
        return None

def compute_features(df):
    df = df.copy()
    df["mom20"] = df["Close"].pct_change(20)
    df["mom60"] = df["Close"].pct_change(60)
    delta = df["Close"].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + up / (down + 1e-9)))
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    df["volatility"] = df["Close"].pct_change().rolling(20).std()
    return df

def run():
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：找不到 Webhook URL")
        return

    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 發送當次執行的小標題
    send_msg = f"🛰️ **AI 盤前快訊** ({now_time})\n━━━━━━━━━━━━━━━━━━"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": send_msg})

    for sym in must_watch:
        try:
            # 1. AI 分析
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2y")
            if df.empty: continue
            
            ai_status = "📈 分析中"
            if len(df) > 60:
                df_feat = compute_features(df)
                df_feat["target"] = df_feat["Close"].shift(-5) / df_feat["Close"] - 1
                features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
                train_df = df_feat.dropna(subset=features + ["target"])
                model = XGBRegressor(n_estimators=50, max_depth=3)
                model.fit(train_df[features], train_df["target"])
                pred = float(model.predict(df_feat[features].iloc[-1:])[0])
                emoji = "🚀" if pred > 0.01 else "📈" if pred > 0 else "☁️"
                ai_status = f"{emoji} 5日預估: `{pred:+.2%}`"

            # 2. 抓取最新一則新聞
            news = get_live_news(sym.split('.')[0])
            curr_price = float(df['Close'].iloc[-1])

            # 3. 組合訊息
            report = f"**{sym}** | {ai_status}\n💰 現價: `{curr_price:.2f}`"
            if news:
                report += f"\n📰 {news['title']}\n🔗 <{news['link']}>"
            
            requests.post(DISCORD_WEBHOOK_URL, json={"content": report})
        except Exception as e:
            print(f"跳過 {sym}: {e}")

if __name__ == "__main__":
    run()

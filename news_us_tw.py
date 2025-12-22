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

# 讀取 Webhook 網址並清理空格
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

def get_live_news(query):
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        news_items = []
        for entry in feed.entries[:2]:
            clean_title = entry.title.split(" - ")[0]
            news_items.append(f"  - {clean_title}\n    <{entry.link}>")
        return "\n".join(news_items) if news_items else "  (無近期新聞)"
    except:
        return "  (新聞抓取失敗)"

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

def send_to_discord(text):
    """安全發送訊息函數"""
    if DISCORD_WEBHOOK_URL and text.strip():
        res = requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=15)
        print(f"📡 Discord 回傳狀態: {res.status_code}")
        if res.status_code >= 400:
            print(f"❌ 錯誤原因: {res.text}")

def run():
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：找不到 Webhook URL")
        return
    
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    
    # 發送標題
    header = f"🤖 **AI 投資情報站** ({today})\n━━━━━━━━━━━━━━━━━━"
    send_to_discord(header)

    for sym in must_watch:
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2y")
            if df.empty: continue

            # AI 預測
            ai_info = "📈 分析中"
            if len(df) > 60:
                try:
                    df_feat = compute_features(df)
                    df_feat["target"] = df_feat["Close"].shift(-5) / df_feat["Close"] - 1
                    features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
                    train_df = df_feat.dropna(subset=features + ["target"])
                    model = XGBRegressor(n_estimators=50, max_depth=3)
                    model.fit(train_df[features], train_df["target"])
                    pred = float(model.predict(df_feat[features].iloc[-1:])[0])
                    status = "🚀" if pred > 0.01 else "📈" if pred > 0 else "☁️"
                    ai_info = f"{status} 5日預估: `{pred:+.2%}`"
                except: pass

            curr_price = float(df['Close'].iloc[-1])
            news_content = get_live_news(sym.split('.')[0])
            
            # 每個標的一則訊息，確保不爆字數
            item_msg = f"**{sym}** | {ai_info}\n  - 現價: {curr_price:.2f}\n{news_content}"
            send_to_discord(item_msg)
            
        except Exception as e:
            print(f"跳過 {sym}: {e}")

    send_to_discord("━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    run()

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import datetime
import os
import feedparser
import urllib.parse
import time
from xgboost import XGBRegressor
import warnings

warnings.filterwarnings("ignore")

# 讀取 Webhook
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

# 儲存已發送過的新聞標題，避免重複發送
sent_news_titles = set()

def get_live_news(query):
    try:
        safe_query = urllib.parse.quote(query)
        # 抓取 Google News RSS
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        
        new_items = []
        for entry in feed.entries[:3]: # 每次檢查最新的 3 則
            clean_title = entry.title.split(" - ")[0]
            
            # 如果這則新聞沒發送過，就加入待發送清單
            if clean_title not in sent_news_titles:
                new_items.append({
                    "title": clean_title,
                    "link": entry.link
                })
                sent_news_titles.add(clean_title) # 標記為已發送
        
        # 保持集合大小，避免記憶體佔用過大 (只留最新 100 則)
        if len(sent_news_titles) > 100:
            list_titles = list(sent_news_titles)
            sent_news_titles.clear()
            for t in list_titles[-50:]:
                sent_news_titles.add(t)
                
        return new_items
    except:
        return []

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
    if DISCORD_WEBHOOK_URL and text.strip():
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text}, timeout=15)

def analyze_and_report(sym):
    """分析特定股票並回傳 AI 狀態"""
    try:
        ticker = yf.Ticker(sym)
        df = ticker.history(period="2y")
        if df.empty: return "📊 無法取得資料", 0
        
        curr_price = float(df['Close'].iloc[-1])
        if len(df) > 60:
            df_feat = compute_features(df)
            df_feat["target"] = df_feat["Close"].shift(-5) / df_feat["Close"] - 1
            features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
            train_df = df_feat.dropna(subset=features + ["target"])
            model = XGBRegressor(n_estimators=50, max_depth=3)
            model.fit(train_df[features], train_df["target"])
            pred = float(model.predict(df_feat[features].iloc[-1:])[0])
            
            status = "🚀" if pred > 0.01 else "📈" if pred > 0 else "☁️"
            return f"{status} 5日預估: `{pred:+.2%}` (現價: {curr_price:.2f})", curr_price
    except:
        pass
    return "📈 分析中", 0

def monitor():
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：找不到 Webhook URL")
        return

    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA"]
    print(f"🚀 AI 監聽啟動，監控對象: {must_watch}")
    
    # 啟動時先報個平安
    send_to_discord("🛰️ **AI 實時新聞監控系統已上線**\n*當有相關重大新聞時，我會自動通知您。*")

    while True:
        for sym in must_watch:
            # 1. 抓取新新聞
            news_items = get_live_news(sym.split('.')[0])
            
            # 2. 如果有新新聞，才進行 AI 分析並發送
            if news_items:
                ai_report, _ = analyze_and_report(sym)
                
                for item in news_items:
                    msg = f"🔔 **【重大新聞動態】{sym}**\n{ai_report}\n📰 {item['title']}\n🔗 <{item['link']}>"
                    send_to_discord(msg)
                    print(f"✅ 已發送: {item['title']}")
                    time.sleep(2) # 稍微延遲避免觸發 Discord 限制

        # 3. 休息時間 (每 10 分鐘檢查一次)
        # 改成 600 秒，避免被 Google News 封鎖 IP
        time.sleep(600)

if __name__ == "__main__":
    monitor()

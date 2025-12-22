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

# 讀取 Webhook 網址
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL", "").strip()

def get_live_news(query):
    """抓取最新一則新聞"""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        if feed.entries:
            entry = feed.entries[0]
            clean_title = entry.title.split(" - ")[0]
            return {"title": clean_title, "link": entry.link}
        return None
    except:
        return None

def compute_features(df):
    """計算 AI 所需的技術指標"""
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

    # 設定監控清單
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 1. 發送標題
    header_msg = f"🛰️ **AI 盤前快訊** ({now_time})\n━━━━━━━━━━━━━━━━━━"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": header_msg})

    for sym in must_watch:
        try:
            # 2. 抓取股價資料 (增加重試與超時設定)
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2y", timeout=25) 
            
            if df.empty:
                # 如果抓不到資料，發送警告到 Discord 幫助除錯
                requests.post(DISCORD_WEBHOOK_URL, json={"content": f"⚠️ {sym}: 無法從 Yahoo Finance 取得資料"})
                continue

            # 3. AI 預測模型
            ai_status = "📈 分析中"
            if len(df) > 60:
                try:
                    df_feat = compute_features(df)
                    df_feat["target"] = df_feat["Close"].shift(-5) / df_feat["Close"] - 1
                    features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
                    train_df = df_feat.dropna(subset=features + ["target"])
                    
                    model = XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1)
                    model.fit(train_df[features], train_df["target"])
                    
                    # 預測最後一筆數據
                    last_features = df_feat[features].iloc[-1:].values
                    pred = float(model.predict(last_features)[0])
                    
                    emoji = "🚀" if pred > 0.015 else "📈" if pred > 0 else "☁️"
                    ai_status = f"{emoji} 5日預估: `{pred:+.2%}`"
                except Exception as e:
                    ai_status = f"⚠️ AI 分析失敗: {str(e)[:30]}"

            # 4. 抓取最新新聞
            news = get_live_news(sym.split('.')[0])
            curr_price = float(df['Close'].iloc[-1])

            # 5. 組合訊息並發送
            report = f"**{sym}** | {ai_status}\n💰 現價: `{curr_price:.2f}`"
            if news:
                report += f"\n📰 {news['title']}\n🔗 <{news['link']}>"
            
            res = requests.post(DISCORD_WEBHOOK_URL, json={"content": report})
            print(f"✅ {sym} 發送狀態: {res.status_code}")

        except Exception as e:
            error_msg = f"❌ 處理 {sym} 時發生系統錯誤: {str(e)}"
            print(error_msg)
            requests.post(DISCORD_WEBHOOK_URL, json={"content": error_msg})

    # 結尾分隔線
    requests.post(DISCORD_WEBHOOK_URL, json={"content": "━━━━━━━━━━━━━━━━━━"})

if __name__ == "__main__":
    run()

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

DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL")

def get_live_news(query):
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        news_items = []
        for entry in feed.entries[:2]:
            clean_title = entry.title.split(" - ")[0]
            news_items.append(f"  - {clean_title}\n    <{entry.link}>")
        return "\n".join(news_items) if news_items else "  (無近期相關新聞)"
    except:
        return "  (新聞抓取失敗)"

def compute_features(df):
    df = df.copy()
    # 確保欄位名稱正確
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
    if not DISCORD_WEBHOOK_URL: return
    
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    
    # 穩定抓取數據
    report = f"🤖 **AI 投資情報站** ({today})\n━━━━━━━━━━━━━━━━━━\n\n"

    for sym in must_watch:
        try:
            # 逐一抓取標的，避免 MultiIndex 造成解析錯誤
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2y")
            
            if df.empty:
                report += f"⚠️ **{sym}** | 無法獲取行情數據\n\n"
                continue

            # 抓取新聞
            news_query = sym.split('.')[0]
            news_content = get_live_news(news_query)
            
            # AI 預測邏輯
            ai_info = "(計算中)"
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
                    ai_info = f"{status} 預估: `{pred:+.2%}`"
                except:
                    ai_info = "📈 分析完畢"

            curr_price = float(df['Close'].iloc[-1])
            report += f"**{sym}** | {ai_info}\n"
            report += f"  - 現價: {curr_price:.2f}\n"
            report += f"{news_content}\n\n"
            
        except Exception as e:
            print(f"Error processing {sym}: {e}")
            report += f"⚠️ **{sym}** | 數據解析異常\n\n"

    report += "━━━━━━━━━━━━━━━━━━"
    requests.post(DISCORD_WEBHOOK_URL, json={"content": report})

if __name__ == "__main__":
    run()

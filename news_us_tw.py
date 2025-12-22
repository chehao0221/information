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
    df["mom20"] = df["Close"].pct_change(20)
    df["mom60"] = df["Close"].pct_change(60)
    delta = df["Close"].diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - (100 / (1 + up / (down + 1e-9)))
    df["vol_ratio"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-9)
    df["volatility"] = df["Close"].pct_change().rolling(20).std()
    return df

def send_split_msg(content):
    if not DISCORD_WEBHOOK_URL: return
    # 簡單發送，確保訊息不為空
    if content.strip():
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})

def run():
    # 增加更多標的測試
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    
    print(f"📡 啟動數據下載...")
    data = yf.download(must_watch, period="2y", progress=False, auto_adjust=True)
    
    report = f"🤖 **AI 投資情報站** ({today})\n━━━━━━━━━━━━━━━━━━\n\n"

    for sym in must_watch:
        try:
            # 兼容單檔與多檔數據格式
            if isinstance(data.columns, pd.MultiIndex):
                df = data.xs(sym, axis=1, level=1).dropna()
            else:
                df = data.dropna()

            news_content = get_live_news(sym.split('.')[0])
            
            if len(df) > 50:
                df_feat = compute_features(df)
                df_feat["target"] = df_feat["Close"].shift(-5) / df_feat["Close"] - 1
                features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
                train_df = df_feat.dropna(subset=features + ["target"])
                
                model = XGBRegressor(n_estimators=50, max_depth=3)
                model.fit(train_df[features], train_df["target"])
                pred = float(model.predict(df_feat[features].iloc[-1:])[0])
                
                curr_price = float(df['Close'].iloc[-1])
                status = "🚀" if pred > 0.01 else "📈" if pred > 0 else "☁️"
                report += f"{status} **{sym}** | 預估: `{pred:+.2%}`\n"
                report += f"  - 現價: {curr_price:.1f}\n"
            else:
                report += f"⚪ **{sym}** | (數據不足，暫無AI預測)\n"
            
            report += f"{news_content}\n\n"
            
        except Exception as e:
            report += f"⚠️ **{sym}** | 處理時發生錯誤\n\n"

    report += "━━━━━━━━━━━━━━━━━━"
    send_split_msg(report)

if __name__ == "__main__":
    run()

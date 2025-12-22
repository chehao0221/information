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
    """抓取最新新聞，並過濾掉超過 12 小時的舊聞"""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        
        if feed.entries:
            entry = feed.entries[0]
            
            # --- 時間過濾邏輯 ---
            # 將新聞發布時間轉為 datetime 物件 (UTC)
            pub_time = datetime.datetime(*entry.published_parsed[:6])
            now_time = datetime.datetime.utcnow()
            
            # 計算時差（小時）
            diff_hours = (now_time - pub_time).total_seconds() / 3600
            
            # 如果新聞超過 12 小時，視為舊聞不顯示
            if diff_hours > 12:
                print(f"跳過舊聞: {entry.title} ({int(diff_hours)}小時前)")
                return None
            
            clean_title = entry.title.split(" - ")[0]
            return {"title": clean_title, "link": entry.link}
        return None
    except Exception as e:
        print(f"新聞抓取失敗: {e}")
        return None

def compute_features(df):
    """計算 AI 量化指標"""
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

    # 監控清單
    must_watch = ["2330.TW", "2317.TW", "0050.TW", "AAPL", "NVDA", "TSLA"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now_time = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    # 1. 發送精美標題
    header_msg = (
        f"🛰️ **AI 投資情報站 - 盤前快訊**\n"
        f"📅 報告時間：`{now_time}` (台北)\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"content": header_msg})

    for sym in must_watch:
        try:
            # 2. 數據抓取
            ticker = yf.Ticker(sym)
            df = ticker.history(period="2y", timeout=25) 
            if df.empty: continue

            # 3. AI 預測核心 (XGBoost)
            ai_status = "📉 數據不足"
            pred_val = 0
            if len(df) > 60:
                try:
                    df_feat = compute_features(df)
                    df_feat["target"] = df_feat["Close"].shift(-5) / df_feat["Close"] - 1
                    features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
                    train_df = df_feat.dropna(subset=features + ["target"])
                    
                    model = XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1)
                    model.fit(train_df[features], train_df["target"])
                    
                    last_features = df_feat[features].iloc[-1:].values
                    pred_val = float(model.predict(last_features)[0])
                    
                    if pred_val > 0.08: emoji = "💥 **極度看多**"
                    elif pred_val > 0.03: emoji = "🔥 **強勢看多**"
                    elif pred_val > 0.01: emoji = "🚀 **穩定偏多**"
                    elif pred_val > 0: emoji = "📈 **微幅看多**"
                    else: emoji = "☁️ **中性觀望**"
                    
                    ai_status = f"{emoji} (`{pred_val:+.2%}`)"
                except:
                    ai_status = "⚠️ 分析異常"

            # 4. 新聞抓取 (含 12 小時去重過濾)
            news = get_live_news(sym.split('.')[0])
            curr_price = float(df['Close'].iloc[-1])

            # 5. 訊息格式化
            is_hot = "⭐️" if pred_val > 0.05 else ""
            
            report = (
                f"{is_hot} **標的：{sym}** {is_hot}\n"
                f"💰 現價：`{curr_price:.2f}`\n"
                f"🤖 AI 預估：{ai_status}\n"
            )
            
            if news:
                report += f"📰 頭條：{news['title']}\n🔗 <{news['link']}>\n"
            else:
                report += f"ℹ️ 近 12 小時無重大相關新聞\n"
            
            requests.post(DISCORD_WEBHOOK_URL, json={"content": report})
            print(f"✅ {sym} 處理完成")

        except Exception as e:
            print(f"❌ {sym} 錯誤: {e}")

    # 結尾聲明
    footer = (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 *對帳提示：本預測為 5 個交易日目標，請於一週後回測。*\n"
        f"⚠️ *投資盈虧自負，AI 僅供策略參考。*"
    )
    requests.post(DISCORD_WEBHOOK_URL, json={"content": footer})

if __name__ == "__main__":
    run()

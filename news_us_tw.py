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

# 已修改：對應您 GitHub Secrets 裡存的名字
DISCORD_WEBHOOK_URL = os.getenv("NEWS_WEBHOOK_URL")

def get_live_news(query):
    """抓取 Google News 並回傳精簡格式"""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={safe_query}&hl=zh-TW&gl=TW&ceid=TW:zh-TW"
        feed = feedparser.parse(url)
        news_items = []
        for entry in feed.entries[:2]:
            # 移除新聞標題中的來源後綴
            clean_title = entry.title.split(" - ")[0]
            # 使用 < > 屏蔽預覽，確保發送穩定性
            news_items.append(f"  - {clean_title}\n    <{entry.link}>")
        return "\n".join(news_items) if news_items else "  (無近期相關新聞)"
    except:
        return "  (新聞抓取失敗)"

def compute_features(df):
    """計算技術指標特徵"""
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
    """處理 Discord 分段發送"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ 錯誤：未設定 NEWS_WEBHOOK_URL")
        return

    if len(content) <= 2000:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    else:
        parts = content.split('\n\n')
        current_msg = ""
        for part in parts:
            if len(current_msg) + len(part) < 1900:
                current_msg += part + '\n\n'
            else:
                requests.post(DISCORD_WEBHOOK_URL, json={"content": current_msg})
                current_msg = part + '\n\n'
        if current_msg:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": current_msg})

def run():
    # 1. 定義標的
    must_watch = ["2330.TW", "2317.TW", "2454.TW", "0050.TW"]
    tz = datetime.timezone(datetime.timedelta(hours=8))
    today = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    
    print(f"📡 正在下載股市數據...")
    # 下載數據 (調整為 2y 確保訓練穩定)
    data = yf.download(must_watch, period="2y", progress=False, auto_adjust=True)
    
    if data.empty:
        print("❌ 錯誤：無法從 yfinance 取得數據")
        return

    report = f"🤖 **AI 投資情報站 - 綜合分析報告** ({today})\n"
    report += "━━━━━━━━━━━━━━━━━━\n\n"

    for sym in must_watch:
        try:
            # 處理 yfinance 多檔標的的 DataFrame 結構
            if len(must_watch) > 1:
                df = data.iloc[:, data.columns.get_level_values(1) == sym].copy()
                df.columns = df.columns.get_level_values(0)
            else:
                df = data.copy()

            df = df.dropna()
            if len(df) < 100: continue
            
            # 2. AI 預測邏輯
            df = compute_features(df)
            df["future_return"] = df["Close"].shift(-5) / df["Close"] - 1
            
            features = ["mom20", "mom60", "rsi", "vol_ratio", "volatility"]
            train_df = df.dropna(subset=features + ["future_return"])
            current_feat = df[features].iloc[-1:]
            
            if train_df.empty: continue

            # 初始化並訓練模型
            model = XGBRegressor(n_estimators=100, max_depth=3, learning_rate=0.07, random_state=42)
            model.fit(train_df[features], train_df["future_return"])
            pred = float(model.predict(current_feat)[0])
            
            # 3. 技術面計算
            curr_price = float(df['Close'].iloc[-1])
            hist_20 = df.tail(20)
            resistance = float(hist_20['High'].max())
            support = float(hist_20['Low'].min())
            upside = (resistance - curr_price) / curr_price
            
            # 4. 消息面
            search_query = sym.split(".")[0]
            news_content = get_live_news(search_query)
            
            # 5. 組裝單檔報告
            status_icon = "🚀" if pred > 0.015 else "📈" if pred > 0 else "☁️"
            report += f"{status_icon} **{sym}** | 5日預估: `{pred:+.2%}`\n"
            report += f"  - 現價: {curr_price:.1f} (支撐: {support:.1f} / 壓力: `{resistance:.1f}`)\n"
            report += f"  - 距離壓力空間: `{upside:+.2%}`\n"
            report += f"  - 最新動態:\n{news_content}\n\n"
            
        except Exception as e:
            print(f"解析 {sym} 時出錯: {e}")

    report += "━━━━━━━━━━━━━━━━━━"
    
    # 執行分段發送
    send_split_msg(report)
    print("✅ 綜合分析報告已發送")

if __name__ == "__main__":
    run()

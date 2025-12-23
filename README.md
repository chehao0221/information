📰 Daily Market News AI (台美股每日新聞摘要)
本專案利用 Python 爬蟲技術，每日定時從 Yahoo Finance 抓取台股與美股的最新財經新聞。結合 GitHub Actions 自動化排程，將海量的市場資訊過濾並整理成精簡的摘要報告，直接推播至你的 Discord 頻道。

🌟 核心功能
跨市場追蹤：同時監控美股（如 AAPL, NVDA）與台股（如 2330.TW, 2317.TW）的主要標的新聞。

多來源整合：自動解析 Yahoo Finance 提供的各類財經新聞標題與連結。

全自動排程：每日固定時間自動運行，無需手動啟動腳本。

Discord 即時推播：支援 Webhook 功能，讓你在手機上就能掌握盤前/盤後的大事紀。

🛠️ 技術細節
自動化工具: GitHub Actions。

主要腳本: news_us_tw.py (負責爬取與整理新聞數據)。

環境配置: 使用 python-version: '3.10' 環境運行。

關鍵套件: requests, beautifulsoup4, yfinance。

🚀 設定步驟
1. 配置 Discord Webhook
在你的 Discord 伺服器中建立 Webhook，並取得 URL。

前往 GitHub 儲存庫的 Settings -> Secrets and variables -> Actions。

新增一個 Secret，名稱為 DISCORD_WEBHOOK_URL，值為你的 Webhook 網址。

2. 調整新聞觀察清單
在 news_us_tw.py 中，你可以自定義 watch_list 變數，加入你感興趣的股票代號（例如 TSLA, 2454.TW）。

3. 排程設定
目前 GitHub Actions 設定為每日定時觸發 0 0 * * *（可依需求在 .github/workflows/daily_news.yml 中修改 cron 數值）。

📋 報告範例
🔔 今日美股重要新聞

AAPL: Apple 宣布最新的 AI 發展計畫... [連結]

NVDA: 輝達財報亮眼，盤後股價大漲... [連結]

🔔 今日台股重要新聞

2330.TW: 台積電法說會重點摘要... [連結]

📂 檔案架構
news_us_tw.py: 新聞爬蟲與格式化邏輯核心。

.github/workflows/daily_news.yml: 定義自動化執行流程與環境變數注入。

🏹 全球金融快訊雷達系統（Smart News Radar）

Smart News Radar 是一套基於 GitHub Actions + Python 的自動化金融資訊彙整系統，專注於 台股與美股市場的總體經濟與大盤新聞監控。
系統以「穩定、去重、不中斷」為設計核心，提供即時且不重複的市場快訊推播。

本專案為資訊彙整與推播工具，不涉及投資預測、交易決策或任何形式的投資建議。

🌟 核心特性（Core Features）
✅ 跨市場監控（台股 / 美股）

自動依據台北時間（GMT+8）判斷當前市場時段

動態切換台股與美股新聞來源與搜尋關鍵字

避免跨市場資訊混發

✅ 智能新聞去重機制（De-duplication）

內建持久化快取（sent_news.txt）

已推播過的新聞標題不會重複發送

去重狀態透過 Git Commit 保存，無需資料庫

✅ 關鍵時段推播

支援盤前 / 盤中 / 盤後資訊彙整

適合開盤前快速掌握市場氛圍

避免無意義的高頻洗版推播

✅ 完全解耦設計

獨立於任何交易或 AI 預測系統

單一節點故障不影響其他系統運作

可安全長期自動執行

⏳ 自動化執行時間線（Workflow Timeline）

系統透過 GitHub Actions 於關鍵金融時刻自動執行：

台北時間 (GMT+8)	主題	任務內容
08:30	🏹 台股盤前情報	彙整美股收盤、台股盤前重要消息
15:30	📊 台股盤後總結	台股當日表現與盤後重大事件
21:30	⚡ 美股盤前情報	美股盤前異動、Fed 動態、總經數據
06:00	📈 美股盤後總結	美股收盤概況與重要財經新聞
🛠️ 技術架構（Technical Stack）

資料來源

Yahoo Finance (yfinance)：大盤即時數據

Google News RSS：新聞資訊來源

自動化引擎

GitHub Actions（Cron Schedule）

狀態管理

Git Commit 持久化快取（免資料庫）

通知管道

Discord Webhook（Embed 格式化推播）

📂 專案結構
information-main/
├── .github/workflows/
│   └── daily_news.yml      # GitHub Actions 自動化排程
├── data/
│   └── sent_news.txt       # 新聞去重快取（自動生成）
├── news_us_tw.py           # 核心邏輯：新聞抓取 / 去重 / 推播
└── requirements.txt        # 相依套件（feedparser, requests, yfinance）

⚠️ Disclaimer

本系統提供之資訊僅供參考，不構成任何形式的投資建議。
投資人應自行判斷並承擔相關風險。

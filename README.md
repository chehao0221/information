🏹 全球金融快訊雷達系統 (Smart News Radar)
本系統是一個基於 GitHub Actions 與 Python 驅動的自動化金融情報中心。系統具備「跨市場監控」、「新聞去重快取」以及「關鍵時段推播」三大核心功能，旨在為投資者提供最即時、精確且不重複的台美股市場動態。

🌟 核心特性 (Core Features)
完全解耦設計：獨立於 AI 預測倉庫運行，專注於市場總體經濟與大盤消息，確保單一節點故障不會影響整體運作。
智能去重機制 (De-duplication)：內建持久化快取技術，自動記錄已推播的新聞標題，確保 Discord 頻道不會出現重複訊息。
動態時段偵測：系統會自動根據台北時間判斷當前市場（台股或美股），並動態調整搜尋關鍵字。
盤前預報功能：特別強化「台股開盤前」與「美股開盤前」的情報彙整，助您掌握第一手盤勢脈動。

⏳ 自動化執行時間線 (Workflow Timeline)
系統透過 GitHub Actions 每日於關鍵金融時刻自動執行：

台北時間 (GMT+8),執行主題,任務描述
08:30,🏹 台股開盤預報,整理美股收盤概況、台指期變動及今日台股重大消息。
15:30,📊 台股盤後總結,整理台股當日表現、盤後重大事件與關鍵個股新聞。
21:30,⚡ 美股開盤前夕,聚焦美股盤前異動、聯準會(Fed)動態及全球總經數據。
06:00,📈 美股收盤總結,整理美股當日走勢、S&P 500 表現與科技巨頭財報新聞。

🛠️ 技術架構說明 (Technical Stack)
資料來源：yfinance (大盤即時數據)、Google News RSS (新聞源)。

自動化引擎：GitHub Actions (Cron Schedule)。
數據持久化：利用 Git Commit 將 sent_news.txt 狀態回傳至倉庫，實現免資料庫的快取管理。
通知中心：Discord Webhook (Embed 格式化推播)。

📂 檔案結構管理
information-main/
├── .github/workflows/
│   └── daily_news.yml    # 自動化排程設定
├── data/
│   └── sent_news.txt     # (自動生成) 紀錄已發送過的新聞標題，防止重複
├── news_us_tw.py         # 核心邏輯腳本：新聞抓取、去重與 Discord 發送
└── requirements.txt      # 函式庫依賴：feedparser, requests, yfinance

Disclaimer: 本系統提供之資訊僅供參考，不構成任何形式的投資建議。投資人應獨立判斷並自負投資風險。

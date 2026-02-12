import main_engine
import plugin_czbooks as current_plugin

# ================= 🔧 執行配置微調 =================
if __name__ == "__main__":
    # 1. 設定小說名稱
    main_engine.NOVEL_NAME = "CZBooks_測試小說"

    # 2. 針對此網站的微調
    main_engine.USE_COOKIES = False          # 不需要 Cookie
    main_engine.ENABLE_SMART_FORMAT = False  # CZBooks 排版通常還行，先關閉智慧清洗試試
    main_engine.DELAY_RANGE = (2, 5)         # 速度可以稍微快一點

    # 3. 啟動引擎
    print(f"🚀 正在啟動 CZBooks 採集任務...")
    engine = main_engine.ScraperEngine(current_plugin)
    engine.run()

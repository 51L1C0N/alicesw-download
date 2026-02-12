import requests
from bs4 import BeautifulSoup
import time
import random
import json
import os
import re
import sys
from urllib.parse import urljoin

# ================= 🎛️ 用戶中央配置區 (User Config) =================

# [1. 檔案與目標]
NOVEL_NAME = "我的小說下載"        # 存檔檔名
COOKIE_FILE = "cookie.json"      # Cookie 檔案路徑

# [2. 行為控制]
USE_COOKIES = True               # 是否掛載 Cookie
USER_AGENT_TYPE = "PC"           # "PC" 或 "MOBILE"
ENABLE_SMART_FORMAT = True       # 是否啟用智慧排版清洗
SKIP_EXISTING = True             # 斷點續傳：跳過已下載的章節

# [3. 網絡防護 (反爬蟲核心)]
DELAY_RANGE = (3, 6)             # 正常隨機延遲 (秒)
MAX_RETRIES = 20                 # 單章最大重試次數 (-1 為無限)
RETRY_CYCLE = [5, 10, 30, 60]    # 循環退避策略 (秒)

# ===================================================================

class ScraperEngine:
    def __init__(self, plugin):
        self.plugin = plugin
        self.headers = self._get_headers()
        self.existing_chapters = set()
        self.session = requests.Session() # 使用 Session 保持連線

    def _get_headers(self):
        """組裝 Headers"""
        if USER_AGENT_TYPE == "MOBILE":
            ua = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        else:
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

        headers = {"User-Agent": ua}

        # 載入 Cookie
        if USE_COOKIES and os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 兼容 Cookie-Editor 的 JSON 格式
                if isinstance(data, list):
                    cookie_str = "; ".join([f"{i['name']}={i['value']}" for i in data if 'name' in i])
                    headers["Cookie"] = cookie_str
                    print("✅ Cookie 載入成功")
            except Exception as e:
                print(f"⚠️ Cookie 讀取失敗: {e} (將以遊客身份訪問)")
        return headers

    def _smart_request(self, url):
        """
        核心請求函數：包含「循環指數退避」機制
        """
        retry_idx = 0
        while True:
            try:
                resp = self.session.get(url, headers=self.headers, timeout=20)

                # 自動處理編碼
                if resp.encoding == 'ISO-8859-1':
                    resp.encoding = resp.apparent_encoding

                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, 'html.parser')
                elif resp.status_code == 404:
                    print(f"❌ 404 頁面不存在: {url}")
                    return None
                elif resp.status_code == 403:
                    print(f"🚫 403 禁止訪問 (可能需要更新 Cookie)")
                    raise Exception("403 Forbidden")
                else:
                    raise Exception(f"Status {resp.status_code}")

            except Exception as e:
                # 達到最大重試次數
                if MAX_RETRIES != -1 and retry_idx >= MAX_RETRIES:
                    print(f"❌ 達到最大重試次數，放棄此章。")
                    return None

                # 計算等待時間 (循環策略)
                wait_time = RETRY_CYCLE[retry_idx % len(RETRY_CYCLE)]
                print(f"⚠️ 請求失敗: {e}")
                print(f"⏳ 觸發退避機制: 等待 {wait_time} 秒後重試... (第 {retry_idx+1} 次)")

                time.sleep(wait_time)
                retry_idx += 1

    def _clean_text(self, text):
        """智慧排版清洗"""
        if not ENABLE_SMART_FORMAT:
            return text

        # 1. 去除干擾碼
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)

        # 2. 智慧合併斷行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        cleaned_lines = []
        buffer = ""

        for line in lines:
            if not buffer:
                buffer = line
            else:
                last_char = buffer[-1]
                first_char = line[0]
                # 判斷邏輯：結尾非標點 + 開頭非引號 = 應合併
                is_end = last_char in "。！？!?…」”"
                is_start = first_char in "【[(「“"

                if not is_end and not is_start:
                    buffer += line
                else:
                    cleaned_lines.append(buffer)
                    buffer = line
        if buffer: cleaned_lines.append(buffer)

        return "\n\n".join(cleaned_lines)

    def _load_existing_chapters(self, filename):
        """斷點續傳：讀取已存在的章節標題"""
        if not os.path.exists(filename):
            return
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            # 假設章節標題被 === 包圍
            titles = re.findall(r'={20}\n(.*?)\n={20}', content)
            self.existing_chapters = set(t.strip() for t in titles)
            print(f"📂 檢測到已下載 {len(self.existing_chapters)} 章，將自動跳過。")
        except Exception:
            pass

    def run(self):
        print("🚀 啟動通用採集引擎...")

        # 1. 獲取目錄
        catalog_url = self.plugin.CATALOG_URL
        print(f"🔍 正在解析目錄: {catalog_url}")

        soup = self._smart_request(catalog_url)
        if not soup:
            print("❌ 無法讀取目錄，程式終止。")
            return

        # 調用插件解析目錄
        chapters = self.plugin.parse_catalog(soup, catalog_url)

        if not chapters:
            print("❌ 找不到任何章節，請檢查插件選擇器。")
            return

        # 處理倒序 (如果插件指定了 REVERSE=True)
        if getattr(self.plugin, 'REVERSE_ORDER', False):
            print("🔄 執行倒序排列...")
            chapters.reverse()

        total = len(chapters)
        print(f"📖 發現 {total} 章，準備下載...")

        # 2. 準備存檔
        filename = f"{NOVEL_NAME}.txt"
        if SKIP_EXISTING:
            self._load_existing_chapters(filename)

        with open(filename, "a", encoding="utf-8") as f:
            for index, (title, url) in enumerate(chapters):
                # 斷點續傳檢查
                if SKIP_EXISTING and title in self.existing_chapters:
                    print(f"⏩ [跳過] {title} (已存在)")
                    continue

                print(f"⬇️ [{index+1}/{total}] 下載: {title}")

                # 請求章節內容
                page_soup = self._smart_request(url)
                if page_soup:
                    # 調用插件解析內文
                    raw_text = self.plugin.parse_content(page_soup)

                    if raw_text:
                        final_text = self._clean_text(raw_text)

                        # 寫入
                        f.write(f"\n\n{'='*20}\n{title}\n{'='*20}\n\n")
                        f.write(final_text)
                        f.flush() # 強制存檔
                    else:
                        print(f"   ⚠️ 內容解析為空")
                        f.write(f"\n\n[章節 {title} 讀取失敗]\n\n")

                # 正常隨機延遲
                delay = random.uniform(*DELAY_RANGE)
                print(f"   💤 休息 {delay:.1f} 秒...")
                time.sleep(delay)

        print(f"\n✅ 全部完成！檔案: {filename}")

if __name__ == "__main__":
    print("⚠️ 請不要直接運行此檔案，請運行 `run_task.py`")

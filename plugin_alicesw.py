from urllib.parse import urljoin

# ================= 🔌 插件配置區 =================
# 請填入您要下載的小說目錄網址
CATALOG_URL = "https://www.alicesw.com/other/chapters/id/49606.html"

# 網站特性
REVERSE_ORDER = False   # 正序
NEED_LOGIN = True       # 需要 Cookie

def parse_catalog(soup, base_url):
    """
    解析目錄頁：復刻原版邏輯，搜尋所有含 /book/ 的連結
    """
    chapters = []

    # 原版邏輯：抓取所有連結，透過關鍵字過濾
    links = soup.select("a")

    seen = set()
    for link in links:
        title = link.get_text().strip()
        href = link.get('href')

        # 過濾條件：
        # 1. 連結必須包含 '/book/' (這是閱讀頁特徵)
        # 2. 標題長度 > 1
        if href and "/book/" in href and len(title) > 1:
            full_url = urljoin(base_url, href)

            if full_url not in seen:
                chapters.append((title, full_url))
                seen.add(full_url)

    return chapters

def parse_content(soup):
    """
    解析內文頁：復刻原版邏輯
    """
    # 嘗試多種常見 ID/Class
    content = soup.select_one("#content") or \
              soup.select_one(".read-content") or \
              soup.select_one(".chapter-content") or \
              soup.select_one(".novelcontent")

    if content:
        # 清洗：移除多餘標籤 (保留排版結構)
        for trash in content(["script", "style", "div", "iframe", "a", "ins"]):
            trash.decompose()

        # 關鍵：使用 "\n\n" 作為分隔符，這樣 HTML 裡的換行/段落會被保留
        # 這比主程序的 Smart Format 更適合正規網站
        return content.get_text("\n\n", strip=True)

    return None

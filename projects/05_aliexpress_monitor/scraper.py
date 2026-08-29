"""AliExpressと一般サイトの価格スクレイピング。"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

def _extract_number(text: str) -> float | None:
    """文字列から数値を抽出する。"""
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None

def get_aliexpress_price(url: str) -> float:
    """AliExpressの価格を取得する。"""
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    html = response.text

    # JSONデータから価格を探す（埋め込みデータ形式）
    patterns = [
        r'"discountPrice"\s*:\s*"([^"]+)"',
        r'"formatedPrice"\s*:\s*"([^"]+)"',
        r'"salePrice"\s*:\s*"([^"]+)"',
        r'"minActivityAmount"\s*:\s*\{\s*"value"\s*:\s*"([^"]+)"',
        r'"minAmount"\s*:\s*\{\s*"value"\s*:\s*"([^"]+)"',
        r'"minPrice"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        m = re.search(pattern, html)
        if m:
            price = _extract_number(m.group(1))
            if price and price > 0:
                return price

    # HTMLタグから直接探す
    soup = BeautifulSoup(html, "lxml")
    for selector in [
        "[class*='product-price']",
        "[class*='price-current']",
        "[class*='uniform-banner-box-price']",
        "span.product-price-value",
    ]:
        el = soup.select_one(selector)
        if el:
            price = _extract_number(el.get_text())
            if price and price > 0:
                return price

    raise ValueError(
        "価格を取得できませんでした。\n"
        "AliExpressのBot対策により取得できない場合があります。\n"
        "「手動入力」で直接価格を入力してください。"
    )

def fetch_price(url: str) -> float:
    """URLに応じてスクレイパーを切り替える。"""
    if "aliexpress.com" in url:
        return get_aliexpress_price(url)
    # 汎用スクレイパー（楽天・Amazon等）
    response = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(response.text, "lxml")
    for selector in [
        "[id*='priceblock']", "[class*='price']",
        "span.a-price-whole", "[class*='kakaku']"
    ]:
        el = soup.select_one(selector)
        if el:
            price = _extract_number(el.get_text())
            if price and price > 0:
                return price
    raise ValueError("価格を取得できませんでした。")

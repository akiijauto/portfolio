import os
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REMOVE_TAGS = ["script", "style", "nav", "header", "footer",
               "aside", "advertisement", "noscript", "iframe"]

def fetch_article(url: str) -> tuple[str, str]:
    """URLから記事テキストとタイトルを取得する。(text, title) を返す。"""
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.encoding = response.apparent_encoding

    soup = BeautifulSoup(response.text, "lxml")

    # タイトル取得
    title = soup.title.string.strip() if soup.title else ""

    # 不要タグ削除
    for tag in soup(REMOVE_TAGS):
        tag.decompose()

    # 本文抽出（article > main > body の優先順）
    body = (
        soup.find("article") or
        soup.find("main")    or
        soup.find("div", class_=lambda c: c and "content" in c.lower()) or
        soup.body
    )
    if not body:
        body = soup

    lines = [l.strip() for l in body.get_text(separator="\n").splitlines() if l.strip()]
    text  = "\n".join(lines)

    return text, title


def search_articles(keyword: str, max_results: int = 5) -> list[dict]:
    """キーワードでWeb記事を検索し、[{title, url, snippet}] を返す。

    TAVILY_API_KEYが設定されている場合のみ利用可能（Project 13と同じTavily Search API）。
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY未設定")

    resp = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"query": keyword, "max_results": max_results},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [
        {
            "title": r.get("title") or r.get("url", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content") or "")[:200],
        }
        for r in results if r.get("url")
    ][:max_results]

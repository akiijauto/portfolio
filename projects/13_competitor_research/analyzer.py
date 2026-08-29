import os
import sys
import logging
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse, unquote
import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_text, TRANSIENT_ANTHROPIC_ERRORS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def search_competitors(keyword: str, max_results: int = 5) -> list[str]:
    """競合ページのURLを検索する。

    TAVILY_API_KEYが設定されていればTavily Search APIを使用する
    （DuckDuckGoはRenderなどクラウドIPからの接続がブロックされやすいため）。
    未設定時はDuckDuckGoのHTML検索にフォールバックする（ローカル開発用）。
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if api_key:
        return _search_tavily(keyword, api_key, max_results)
    return _search_duckduckgo(keyword, max_results)


def _search_tavily(keyword: str, api_key: str, max_results: int) -> list[str]:
    resp = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"query": keyword, "max_results": max_results},
        timeout=15
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [r["url"] for r in results if r.get("url")][:max_results]


def _search_duckduckgo(keyword: str, max_results: int = 5) -> list[str]:
    resp = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": keyword},
        headers=HEADERS,
        timeout=15
    )
    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []
    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        # DDG wraps URLs as //duckduckgo.com/l/?uddg=<encoded-url>
        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            real = qs.get("uddg", [""])[0]
            if real.startswith("http") and "duckduckgo.com" not in real:
                urls.append(real)
        elif href.startswith("http") and "duckduckgo.com" not in href:
            urls.append(href)
        if len(urls) >= max_results:
            break
    return urls


def scrape_page(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True,
                            verify=False)
        # prefer charset from Content-Type header; fall back to apparent encoding
        if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "windows-1252"):
            resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "aside"]):
            tag.decompose()

        title = (soup.title.string or "").strip()[:120] if soup.title else url
        meta = (soup.find("meta", attrs={"name": "description"}) or
                soup.find("meta", attrs={"property": "og:description"}))
        meta_desc = (meta.get("content") or "")[:200] if meta else ""
        h1s = [h.get_text(strip=True)[:100] for h in soup.find_all("h1")][:2]
        h2s = [h.get_text(strip=True)[:80]  for h in soup.find_all("h2")][:6]
        h3s = [h.get_text(strip=True)[:60]  for h in soup.find_all("h3")][:6]
        char_count = len(soup.get_text(separator=" ", strip=True))
        domain = resp.url.split("/")[2] if "/" in resp.url else url

        return {
            "url": url, "domain": domain, "title": title,
            "meta_desc": meta_desc, "h1": h1s, "h2": h2s, "h3": h3s,
            "char_count": char_count, "ok": True
        }
    except Exception as e:
        logger.warning("scrape failed %s: %s", url, e)
        return {"url": url, "ok": False, "error": str(e)[:120]}


def analyze_with_claude(keyword: str, pages: list[dict]) -> str:
    ok = [p for p in pages if p.get("ok")]
    if not ok:
        return "スクレイプに成功したページがありません。"

    summaries = []
    for i, p in enumerate(ok, 1):
        h2_str = "、".join(p.get("h2", [])[:4]) or "（なし）"
        summaries.append(
            f"【競合{i}】{p['domain']}\n"
            f"タイトル: {p['title']}\n"
            f"メタ説明: {p.get('meta_desc') or '（なし）'}\n"
            f"H1: {', '.join(p.get('h1', [])) or '（なし）'}\n"
            f"H2主要見出し: {h2_str}\n"
            f"推定文字数: {p['char_count']:,}文字"
        )

    prompt = f"""キーワード「{keyword}」の上位{len(ok)}ページを分析しました。

{chr(10).join(summaries)}

以下の観点で競合分析レポートを作成してください（日本語・Markdown形式）：

## 1. 競合の共通パターン
タイトル構成・文字数・見出しの傾向など上位ページに共通する特徴

## 2. コンテンツギャップ（競合の弱点）
競合が取り上げていない視点・情報・切り口

## 3. 差別化コンテンツ案（2〜3案）
コンテンツギャップを活かした、勝てる記事の方向性を具体的に

## 4. 推奨タイトル案（3案）
検索意図に合い、クリックされやすいタイトル。32文字前後を目安に"""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return call_claude_text(client, "claude-haiku-4-5-20251001", 1800, prompt)

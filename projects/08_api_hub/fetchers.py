"""外部API呼び出し + TTLキャッシュ。"""
import sys
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_text

TIMEOUT = 5  # 秒

# ── TTLキャッシュ ─────────────────────────────────────────
_cache: dict = {}  # key -> {"value": ..., "at": timestamp}

TTL = {
    "weather":  600,   # 10分
    "exchange": 3600,  # 1時間
    "news":     1800,  # 30分
}


def _get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["at"] < TTL.get(key.split(":")[0], 600):
        return entry["value"]
    return None


def _set(key: str, value):
    _cache[key] = {"value": value, "at": time.time()}


# ── 天気（Open-Meteo） ───────────────────────────────────
WEATHER_CODES = {
    0: "快晴", 1: "晴れ", 2: "一部曇り", 3: "曇り",
    45: "霧", 48: "霧氷",
    51: "小雨", 53: "雨", 55: "強い雨",
    61: "小雨", 63: "雨", 65: "大雨",
    71: "小雪", 73: "雪", 75: "大雪",
    80: "にわか雨", 81: "にわか雨", 82: "激しいにわか雨",
    95: "雷雨", 96: "雷雨（ひょう）", 99: "激しい雷雨",
}


def fetch_weather(city: str) -> dict:
    key = f"weather:{city.lower()}"
    cached = _get(key)
    if cached:
        return cached

    # ジオコーディング
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "ja", "format": "json"},
            timeout=TIMEOUT,
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return {"ok": False, "error": f"「{city}」という都市が見つかりませんでした。"}
        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        display_name = loc.get("name", city)
    except requests.Timeout:
        return {"ok": False, "error": "天気APIがタイムアウトしました。しばらく待ってから再試行してください。"}
    except requests.RequestException as e:
        return {"ok": False, "error": f"天気APIへの接続に失敗しました。（{e}）"}

    # 気象データ取得（503など一時エラーは最大2回リトライ）
    for attempt in range(3):
        try:
            w = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat, "longitude": lon,
                    "current": "temperature_2m,wind_speed_10m,weather_code",
                    "timezone": "auto",
                },
                timeout=TIMEOUT,
            )
            w.raise_for_status()
            cur = w.json()["current"]
            break
        except requests.Timeout:
            return {"ok": False, "error": "天気APIがタイムアウトしました。"}
        except requests.HTTPError as e:
            if w.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            return {"ok": False, "error": f"天気データの取得に失敗しました。（{e}）"}
        except (requests.RequestException, KeyError) as e:
            return {"ok": False, "error": f"天気データの取得に失敗しました。（{e}）"}

    result = {
        "ok": True,
        "city": display_name,
        "temp": cur["temperature_2m"],
        "wind": cur["wind_speed_10m"],
        "weather": WEATHER_CODES.get(cur["weather_code"], f"不明（コード{cur['weather_code']}）"),
    }
    _set(key, result)
    return result


# ── 為替（Frankfurter） ──────────────────────────────────
CURRENCIES = ["USD", "JPY", "EUR", "GBP", "AUD", "CAD", "CHF", "CNY", "KRW", "SGD"]


def fetch_exchange(from_: str, to: str, amount: float) -> dict:
    key = f"exchange:{from_}:{to}"
    cached = _get(key)
    if cached:
        rate = cached["rate"]
    else:
        try:
            r = requests.get(
                f"https://api.frankfurter.app/latest",
                params={"from": from_, "to": to},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            rate = data["rates"].get(to)
            if rate is None:
                return {"ok": False, "error": f"{from_} → {to} のレートが取得できませんでした。"}
            _set(key, {"rate": rate, "date": data.get("date", "")})
            cached = _get(key)
        except requests.Timeout:
            return {"ok": False, "error": "為替APIがタイムアウトしました。しばらく待ってから再試行してください。"}
        except requests.RequestException as e:
            return {"ok": False, "error": f"為替APIへの接続に失敗しました。（{e}）"}
        except (KeyError, ValueError) as e:
            return {"ok": False, "error": f"為替データの解析に失敗しました。（{e}）"}

    return {
        "ok": True,
        "from": from_,
        "to": to,
        "rate": rate,
        "amount": amount,
        "converted": round(rate * amount, 4),
        "date": cached.get("date", "") if cached else "",
    }


# ── ニュース要約（NHK RSS + Gemini） ──────────────────────
NHK_RSS = "https://www3.nhk.or.jp/rss/news/cat0.xml"


def fetch_news() -> dict:
    key = "news:nhk"
    cached = _get(key)
    if cached:
        return cached

    # RSSフェッチ
    try:
        r = requests.get(NHK_RSS, timeout=TIMEOUT)
        r.raise_for_status()
        r.encoding = "utf-8"
    except requests.Timeout:
        return {"ok": False, "error": "NHK RSSがタイムアウトしました。"}
    except requests.RequestException as e:
        return {"ok": False, "error": f"NHK RSSへの接続に失敗しました。（{e}）"}

    # XMLパース
    try:
        soup = BeautifulSoup(r.text, "lxml-xml")
        items = soup.find_all("item")[:5]
        headlines = [
            f"・{item.find('title').get_text(strip=True)}：{item.find('description').get_text(strip=True)}"
            for item in items
            if item.find("title") and item.find("description")
        ]
        if not headlines:
            return {"ok": False, "error": "ニュース記事が取得できませんでした。"}
    except Exception as e:
        return {"ok": False, "error": f"RSSの解析に失敗しました。（{e}）"}

    # 共通のGeminiクライアントで要約する。
    try:
        prompt = (
            "以下はNHKニュースの最新見出しです。全体のトレンドを踏まえて、"
            "「今日のポイント」として3行（箇条書き）でまとめてください。\n\n"
            + "\n".join(headlines)
        )
        summary = call_claude_text(
            None, "claude-haiku-4-5-20251001", 300, prompt,
        )
    except Exception as e:
        return {"ok": False, "error": f"AI要約の生成に失敗しました。（{e}）"}

    result = {"ok": True, "headlines": headlines, "summary": summary}
    _set(key, result)
    return result

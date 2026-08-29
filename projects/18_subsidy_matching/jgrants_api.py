"""
jGrants（補助金・助成金情報のオープンAPI）連携モジュール。
デジタル庁が提供する公開API（認証不要）から補助金情報を取得する。
https://api.jgrants-portal.go.jp/
"""
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

API_BASE = "https://api.jgrants-portal.go.jp/exp/v1/public"

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


class JGrantsError(Exception):
    """jGrants APIとの通信に失敗した場合の例外。"""


def search_subsidies(keyword: str, prefecture: str = "", only_open: bool = True) -> list[dict]:
    """補助金・助成金を検索し、一覧表示用に整形して返す。"""
    params = {
        "keyword": keyword,
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": "1" if only_open else "0",
    }
    if prefecture:
        params["target_area_search"] = prefecture

    try:
        resp = requests.get(f"{API_BASE}/subsidies", params=params, timeout=15)
        resp.encoding = "utf-8"
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("jGrants検索に失敗: %s", e)
        raise JGrantsError("jGrants APIへの接続に失敗しました") from e

    data = resp.json()
    items = []
    for r in data.get("result", []):
        items.append({
            "id": r.get("id"),
            "title": r.get("title", ""),
            "area": r.get("target_area_search", ""),
            "max_limit": r.get("subsidy_max_limit"),
            "acceptance_start": (r.get("acceptance_start_datetime") or "")[:10],
            "acceptance_end": (r.get("acceptance_end_datetime") or "")[:10],
            "target_employees": r.get("target_number_of_employees", ""),
        })
    return items


def get_subsidy_detail(subsidy_id: str) -> dict:
    """補助金IDから詳細情報を取得し、整形して返す。"""
    try:
        resp = requests.get(f"{API_BASE}/subsidies/id/{subsidy_id}", timeout=15)
        resp.encoding = "utf-8"
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("jGrants詳細取得に失敗: %s", e)
        raise JGrantsError("jGrants APIへの接続に失敗しました") from e

    data = resp.json()
    results = data.get("result", [])
    if not results:
        raise JGrantsError("指定された補助金情報が見つかりませんでした")

    r = results[0]
    detail_html = r.get("detail") or ""
    detail_text = BeautifulSoup(detail_html, "lxml").get_text("\n").strip()

    return {
        "id": r.get("id"),
        "title": r.get("title", ""),
        "detail_text": detail_text[:4000],
        "use_purpose": r.get("use_purpose", ""),
        "industry": r.get("industry", ""),
        "target_area_detail": r.get("target_area_detail") or r.get("target_area_search", ""),
        "target_number_of_employees": r.get("target_number_of_employees", ""),
        "subsidy_max_limit": r.get("subsidy_max_limit"),
        "subsidy_rate": r.get("subsidy_rate"),
        "acceptance_start": (r.get("acceptance_start_datetime") or "")[:10],
        "acceptance_end": (r.get("acceptance_end_datetime") or "")[:10],
        "detail_page_url": r.get("front_subsidy_detail_page_url", ""),
    }

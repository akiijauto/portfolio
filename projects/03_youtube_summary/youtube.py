import os
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi

_api = YouTubeTranscriptApi()

def extract_video_id(url: str) -> str:
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"(?:v=|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    raise ValueError(
        "YouTube URLが認識できませんでした。\n"
        "例: https://www.youtube.com/watch?v=xxxxx または https://youtu.be/xxxxx"
    )

def get_video_title(url: str) -> str:
    try:
        r = requests.get("https://www.youtube.com/oembed",
                         params={"url": url, "format": "json"}, timeout=10)
        return r.json().get("title", "")
    except Exception:
        return ""

def get_transcript(video_id: str) -> str:
    """字幕テキストを取得する。日本語→英語→利用可能な言語の順で試みる。"""
    # まず優先言語で取得
    try:
        fetched = _api.fetch(video_id, languages=["ja", "en", "a.ja", "a.en"])
        return " ".join(s.text for s in fetched)
    except Exception:
        pass

    # 利用可能な言語を全て試す
    try:
        transcript_list = _api.list(video_id)
        for t in transcript_list:
            try:
                fetched = t.fetch()
                return " ".join(s.text for s in fetched)
            except Exception:
                continue
        raise ValueError("この動画には取得できる字幕がありませんでした。字幕付きの動画を試してください。")
    except ValueError:
        raise
    except Exception:
        raise ValueError(
            "字幕を取得できませんでした。\n"
            "・この動画は字幕が無効になっている可能性があります\n"
            "・非公開動画・年齢制限動画は取得できません"
        )

def fetch_video(url: str) -> tuple[str, str, str]:
    video_id   = extract_video_id(url)
    title      = get_video_title(url)
    transcript = get_transcript(video_id)
    return video_id, title, transcript

def has_captions(video_id: str) -> bool:
    """字幕（自動生成含む）が取得可能かどうかを軽量に確認する。"""
    try:
        _api.list(video_id)
        return True
    except Exception:
        return False

def search_videos(keyword: str, max_results: int = 5) -> list[dict]:
    """キーワードで字幕付きのYouTube動画を検索し、[{video_id, title, url, thumbnail}] を返す。

    TAVILY_API_KEYが設定されている場合のみ利用可能（Project 02/13と同じTavily Search API）。
    検索結果のうち字幕が取得可能な動画のみ最大max_results件を返す。
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY未設定")

    resp = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "query": keyword,
            "max_results": max_results * 3,
            "include_domains": ["youtube.com", "youtu.be"],
        },
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    videos = []
    seen = set()
    for r in results:
        url = r.get("url", "")
        try:
            video_id = extract_video_id(url)
        except ValueError:
            continue
        if video_id in seen or not has_captions(video_id):
            continue
        seen.add(video_id)
        videos.append({
            "video_id": video_id,
            "title": r.get("title") or get_video_title(url),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
        })
        if len(videos) >= max_results:
            break
    return videos

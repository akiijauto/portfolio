"""投稿効果データの記録・分析（SQLite）。"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "engagement.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS engagements (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                topic       TEXT    NOT NULL,
                sns_type    TEXT    NOT NULL,
                likes       INTEGER DEFAULT 0,
                comments    INTEGER DEFAULT 0,
                reach       INTEGER DEFAULT 0,
                recorded_at TEXT    DEFAULT (date('now'))
            )
        """)


def record(topic: str, sns_type: str, likes: int, comments: int, reach: int) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO engagements (topic, sns_type, likes, comments, reach) VALUES (?,?,?,?,?)",
            (topic, sns_type, likes, comments, reach),
        )


def top_topics(limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT
                topic, sns_type,
                ROUND(AVG(likes),    1) AS avg_likes,
                ROUND(AVG(comments), 1) AS avg_comments,
                ROUND(AVG(reach),    0) AS avg_reach,
                COUNT(*)               AS posts,
                ROUND(AVG(likes) + AVG(comments) * 3, 1) AS score
            FROM engagements
            GROUP BY topic, sns_type
            ORDER BY score DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def hot_topics(threshold: float = 30.0) -> set[str]:
    """スコアが閾値以上のトピック名セットを返す（テーマ提案時のバッジ判定用）。"""
    return {r["topic"] for r in top_topics(20) if (r["score"] or 0) >= threshold}

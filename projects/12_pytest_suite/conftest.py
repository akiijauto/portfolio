"""pytest共有フィクスチャ — sys.path セットアップのみ。"""
import os
import sys
from pathlib import Path

# shared.utils は AI_PROVIDER (デフォルト gemini) で呼び出し先を切り替えるが、
# このテストスイートは Anthropic クライアントを直接モックして call_claude_json() の
# リトライ・キャッシュ等のロジックを検証する設計のため、claude 分岐に固定する。
# (shared.utils のインポート前に設定する必要がある)
os.environ.setdefault('AI_PROVIDER', 'claude')

ROOT = Path(__file__).parents[2]

# 各プロジェクトのパスを追加
for project in ("11_webhook_relay", "10_budget_tracker", "09_daily_bot", "08_api_hub",
                 "13_competitor_research", "14_seo_article_generator",
                 "15_sns_management_hub", "16_ad_copy_generator", "17_inquiry_crm"):
    p = str(ROOT / "projects" / project)
    if p not in sys.path:
        sys.path.insert(0, p)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

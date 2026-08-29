"""
全サービスを一括起動するスクリプト。

使い方:
    python start_all.py

起動後、ポータル（portal/index.html）をブラウザで開きます。
停止するには Ctrl+C を押してください。
"""
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# Windowsのコンソールがcp932の場合、絵文字や記号(—など)でUnicodeEncodeErrorになるためUTF-8に固定
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent

PROJECTS = [
    ("02_web_article_summary","app.py",     5002, "Web記事要約"),
    ("03_youtube_summary",    "app.py",     5003, "YouTube要約"),
    ("04_mercari_listing",    "app.py",     5004, "メルカリ出品文"),
    ("05_aliexpress_monitor", "app.py",     5005, "価格監視"),
    ("07_memo_app",           "app.py",     5007, "メモアプリ（認証付き）"),
    ("08_api_hub",            "app.py",     5008, "外部API連携ハブ"),
    ("09_daily_bot",          "app.py",     5009, "毎朝Discordお知らせBot"),
    ("10_budget_tracker",     "app.py",     5010, "家計簿ダッシュボード"),
    ("11_webhook_relay",      "app.py",     5011, "GitHub→Discord Webhook中継"),
    ("13_competitor_research","app.py",     5013, "競合調査ツール"),
    ("14_seo_article_generator","app.py",  5014, "SEO記事生成"),
    ("15_sns_management_hub",   "app.py",  5015, "SNS管理ハブ"),
    ("16_ad_copy_generator",     "app.py",  5016, "広告文生成"),
    ("17_inquiry_crm",           "app.py",  5017, "問い合わせ管理CRM"),
    ("18_subsidy_matching",      "app.py",  5018, "補助金マッチング"),
    ("19_roleplay_training",     "app.py",  5019, "接客ロールプレイ"),
    ("20_voice_report",          "app.py",  5020, "音声日報整形"),
    ("21_haccp_inspection",       "app.py",  5021, "衛生点検HACCP"),
    ("22_contact_form",           "app.py",  5022, "お問い合わせフォーム"),
    ("23_store_insight_dashboard", "app.py", 5023, "店舗改善インサイトダッシュボード"),
    ("24_shift_scheduler",        "app.py", 5024, "シフト作成アシスタントAI"),
    ("25_sop_generator",          "app.py", 5025, "業務マニュアル・SOP自動生成"),
    ("26_inventory_predictor",    "app.py", 5026, "在庫発注タイミング予測AI"),
    ("27_recruitment_generator",  "app.py", 5027, "求人原稿・面接質問自動生成"),
]

# 仮想環境のPythonを使用
venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
python      = str(venv_python) if venv_python.exists() else sys.executable

print("=" * 45)
print("  AI開発ポータル — 全サービス起動")
print("=" * 45)

processes = []
for project, script, port, name in PROJECTS:
    cwd = ROOT / "projects" / project
    p   = subprocess.Popen(
        [python, script],
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    processes.append(p)
    print(f"  ✅ {name:<14} http://127.0.0.1:{port}")
    time.sleep(0.4)

print()
print("全サービスが起動しました。")
print("ポータルをブラウザで開きます...")
time.sleep(1)
webbrowser.open(str(ROOT / "portal" / "index.html"))

print("\n停止するには Ctrl+C を押してください。")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nサービスを停止しています...")
    for p in processes:
        p.terminate()
    print("全サービスを停止しました。")

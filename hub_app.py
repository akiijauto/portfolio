"""
複数アプリを1つのプロセスにまとめて配信するハブ。
（VPSメモリ不足対策。個別gunicornプロセスを集約して省メモリ化する）

各アプリのapp.pyは module-level に `app = create_app()` を持つ前提（systemdの
`gunicorn app:app` と同じ規約）。そのFlaskアプリ全体をwerkzeugの
DispatcherMiddlewareでパスプレフィックスにマウントする。Blueprintだけを
取り出して1つのFlaskアプリに merge する方式は、各アプリが自前のcreate_app()内で
初期化しているFlask拡張（Flask-Login・Flask-SQLAlchemyなど）が宙に浮いて
壊れるため採用しない。各アプリを丸ごと別個のWSGIアプリとして扱うことで、
拡張機能の初期化はアプリ自身のcreate_app()にそのまま任せられる。

各プロジェクトのapp.pyはサブモジュール（scraper/summarizer等）を裸の名前で
importしているため、複数プロジェクトを同一プロセスにロードすると名前衝突の
危険がある。そのためproject_dirをsys.pathに入れてexecした直後にヘルパーモジュールの
sys.modulesエントリを破棄し、次のプロジェクトの読み込みに影響しないようにしている。
"""
import sys
import importlib.util
from pathlib import Path

from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# (プロジェクトディレクトリ名, nginxのパスプレフィックス, ユニークなモジュール名)
# 09_daily_bot, 05_aliexpress_monitor, 15_sns_management_hub は
# モジュールレベルでスケジューラ/バックグラウンドスレッドを起動するため、
# 多重起動の危険を避けてhub化対象から除外している。
APPS = [
    ("02_web_article_summary", "web-article-summary", "hubmod_02"),
    ("03_youtube_summary", "youtube-summary", "hubmod_03"),
    ("11_webhook_relay", "webhook-relay", "hubmod_11"),
    ("04_mercari_listing", "mercari-listing", "hubmod_04"),
    ("07_memo_app", "memo-app", "hubmod_07"),
    ("08_api_hub", "api-hub", "hubmod_08"),
    ("10_budget_tracker", "budget-tracker", "hubmod_10"),
    ("13_competitor_research", "competitor-research", "hubmod_13"),
    ("14_seo_article_generator", "seo-article-generator", "hubmod_14"),
    ("16_ad_copy_generator", "ad-copy-generator", "hubmod_16"),
    ("17_inquiry_crm", "inquiry-crm", "hubmod_17"),
    ("18_subsidy_matching", "subsidy-matching", "hubmod_18"),
    ("19_roleplay_training", "roleplay-training", "hubmod_19"),
    ("20_voice_report", "voice-report", "hubmod_20"),
    ("21_haccp_inspection", "haccp-inspection", "hubmod_21"),
    ("22_contact_form", "contact-form", "hubmod_22"),
    ("23_store_insight_dashboard", "store-insight-dashboard", "hubmod_23"),
    ("24_shift_scheduler", "shift-scheduler", "hubmod_24"),
    ("25_sop_generator", "sop-generator", "hubmod_25"),
    ("26_inventory_predictor", "inventory-predictor", "hubmod_26"),
    ("27_recruitment_generator", "recruitment-generator", "hubmod_27"),
    # Project28-37（新規10アプリ）。30_realtime_marketはeventlet/SocketIOで
    # 同期WSGI dispatcherと相性が悪いため、32_gcal_summary_bot/37_line_task_bot
    # はモジュールレベルでAPScheduler起動するため、いずれもhub対象外で個別プロセス。
    ("28_qr_meishi", "qr-meishi", "hubmod_28"),
    ("29_form_notion_bot", "form-notion-bot", "hubmod_29"),  # SMTP未設定でも_send_emailは無効化されて安全に動作
    ("31_ocr_tool", "ocr-tool", "hubmod_31"),
    ("33_md_slide_gen", "md-slide-gen", "hubmod_33"),
    ("34_realtime_translate", "realtime-translate", "hubmod_34"),
    ("35_csv_analytics", "csv-analytics", "hubmod_35"),
    ("36_clipboard_formatter", "clipboard-formatter", "hubmod_36"),
]


def _load_wsgi_app(project_dir: Path, mod_name: str):
    before = set(sys.modules)
    sys.path.insert(0, str(project_dir))
    try:
        spec = importlib.util.spec_from_file_location(mod_name, project_dir / "app.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        return module.app
    finally:
        sys.path.remove(str(project_dir))
        # numpy/matplotlib等のC拡張は一度sys.modulesから破棄すると同一プロセス内で
        # 再import不可（"cannot load module more than once per process"）になるため、
        # project_dir配下のローカルヘルパーモジュールだけを破棄対象にする。
        # サイトパッケージ（venv配下）は次のアプリとも安全に共有できるため残す。
        project_dir_str = str(project_dir)
        for name in set(sys.modules) - before - {mod_name}:
            mod = sys.modules.get(name)
            mod_file = getattr(mod, "__file__", None)
            if mod_file and mod_file.startswith(project_dir_str):
                del sys.modules[name]


def create_app():
    default_app = Flask(__name__)

    @default_app.route("/")
    def root():
        return "AI Dev Hub", 200

    mounts = {
        f"/{slug}": _load_wsgi_app(ROOT / "projects" / project, mod_name)
        for project, slug, mod_name in APPS
    }
    default_app.wsgi_app = DispatcherMiddleware(default_app.wsgi_app, mounts)
    return default_app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=8100)

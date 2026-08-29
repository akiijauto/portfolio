import io
import os
import sys
import uuid
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# VPS(Linux)にはMeiryo/Yu Gothic等の日本語フォントが入っておらず、デフォルトの
# DejaVu Sansは日本語グリフを持たないためグラフの日本語ラベルが文字化け（豆腐表示）する。
# OS環境に依存せず確実に表示できるよう、同梱のNoto Sans JPを明示的に登録して使う。
_NOTO_SANS_JP_PATH = Path(__file__).parents[2] / "shared" / "fonts" / "NotoSansJP-Regular.ttf"
if _NOTO_SANS_JP_PATH.exists():
    matplotlib.font_manager.fontManager.addfont(str(_NOTO_SANS_JP_PATH))
    matplotlib.rcParams["font.family"] = matplotlib.font_manager.FontProperties(
        fname=str(_NOTO_SANS_JP_PATH)
    ).get_name()
else:
    for _font in ("Meiryo", "Yu Gothic", "Noto Sans CJK JP", "IPAexGothic"):
        if _font in {f.name for f in matplotlib.font_manager.fontManager.ttflist}:
            matplotlib.rcParams["font.family"] = _font
            break
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, render_template, request, session, flash, redirect, url_for, send_file

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import call_claude_json, call_claude_text

load_dotenv()

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "instance" / "csv_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AGG = {"sum", "mean", "max", "min", "count", "median"}
ALLOWED_CHART = {"bar", "line"}

SUMMARY_INDEX_JA = {
    "count": "件数", "unique": "ユニーク数", "top": "最頻値", "freq": "最頻値の件数",
    "mean": "平均", "std": "標準偏差", "min": "最小値",
    "25%": "25パーセンタイル", "50%": "中央値", "75%": "75パーセンタイル", "max": "最大値",
}


def _describe_html(df: pd.DataFrame) -> str:
    summary = df.describe(include="all").fillna("")
    summary.index = [SUMMARY_INDEX_JA.get(i, i) for i in summary.index]
    return summary.to_html(classes="data-table")


ANALYZE_PROMPT_TEMPLATE = (
    "あなたはデータ分析アシスタントです。次のCSVの列情報と、ユーザーの質問から、"
    "集計方法をJSON形式だけで出力してください。コードは書かないでください。\n\n"
    "列情報: {columns}\n"
    "文字列列の値の例: {sample_values}\n"
    "質問: {question}\n\n"
    "出力は必ず単一のJSONオブジェクトにまとめてください（配列にしない）。"
    "groupby_column・value_columnは必ず1つの列名の文字列で指定してください（配列は不可）。\n"
    "質問が特定の商品名・カテゴリ名など個別の項目に言及している場合は、"
    "上記の値の例を参考に、実際のデータに含まれる値（部分一致でよい）をもとに"
    "filter_valuesにそのgroupby_column上の値を文字列の配列で指定してください"
    "（実際の集計結果はこちらで正確に計算するので、answer_summaryは"
    "「〜について集計しました」程度の一言で構いません。具体的な数値は書かないでください）。"
    "質問が全体・カテゴリ横断的な内容の場合はfilter_valuesを省略してください。\n\n"
    "出力JSON形式（単一オブジェクトのみ、配列は不可）:\n"
    '{{"groupby_column": "<集計の軸にする列名（文字列1つ）>", '
    '"value_column": "<集計対象の列名（文字列1つ）>", '
    '"agg": "<sum|mean|max|min|count|medianのいずれか>", "chart_type": "<bar|lineのいずれか>", '
    '"filter_values": ["<groupby_column上で絞り込みたい値（任意、省略可）>"], '
    '"answer_summary": "<質問への一言回答（日本語、具体的な数値は書かない）>"}}'
)

INSIGHT_PROMPT_TEMPLATE = (
    "次のCSVデータの統計サマリーを見て、データ分析の観点で気になる点・追加で調べると"
    "良さそうな点を日本語で3点、箇条書きで提案してください。\n\n{summary}"
)


def _read_csv_any_encoding(file_or_path) -> pd.DataFrame:
    """UTF-8優先で読み込み、ExcelのCSV出力で多いShift-JIS(CP932)にもフォールバックする。"""
    try:
        return pd.read_csv(file_or_path)
    except UnicodeDecodeError:
        if hasattr(file_or_path, "seek"):
            file_or_path.seek(0)
        return pd.read_csv(file_or_path, encoding="cp932")


def _csv_path_for_session():
    csv_id = session.get("csv_id")
    if not csv_id:
        return None
    path = UPLOAD_DIR / f"{csv_id}.csv"
    return path if path.exists() else None


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB
    # hub_appの全アプリが同じCookie名"session"を共有すると、別アプリへの訪問で
    # セッションが上書きされCSRFトークンが消える問題があるため、一意な名前にする。
    app.config["SESSION_COOKIE_NAME"] = "session_35_csv_analytics"
    init_csrf(app)

    @app.route("/", methods=["GET"])
    def index():
        preview_html = None
        summary_html = None
        if (csv_path := _csv_path_for_session()) is not None:
            df = pd.read_csv(csv_path)
            preview_html = df.head(5).to_html(classes="data-table", index=False)
            summary_html = _describe_html(df)
        return render_template("index.html", preview_html=preview_html, summary_html=summary_html)

    @app.route("/upload", methods=["POST"])
    def upload():
        file = request.files.get("csv_file")
        if not file or not file.filename.lower().endswith(".csv"):
            flash("CSVファイルを選択してください。", "error")
            return redirect(url_for("index"))

        try:
            df = _read_csv_any_encoding(file)
        except Exception:
            flash("CSVの読み込みに失敗しました。形式を確認してください。", "error")
            return redirect(url_for("index"))

        csv_id = uuid.uuid4().hex
        df.to_csv(UPLOAD_DIR / f"{csv_id}.csv", index=False)
        session["csv_id"] = csv_id
        flash("CSVを読み込みました。", "success")
        return redirect(url_for("index"))

    @app.route("/ask", methods=["POST"])
    def ask():
        csv_path = _csv_path_for_session()
        if csv_path is None:
            flash("先にCSVをアップロードしてください。", "error")
            return redirect(url_for("index"))

        question = request.form.get("question", "").strip()
        if not question:
            flash("質問を入力してください。", "error")
            return redirect(url_for("index"))

        df = pd.read_csv(csv_path)
        columns = ", ".join(f"{c}({df[c].dtype})" for c in df.columns)
        sample_values = ", ".join(
            f"{c}の例: {list(df[c].astype(str).unique()[:8])}"
            for c in df.columns if df[c].dtype == object
        )

        answer_summary = None
        chart_data_url = None
        error_message = None

        try:
            spec = call_claude_json(
                None, "claude-haiku-4-5-20251001", 500,
                ANALYZE_PROMPT_TEMPLATE.format(
                    columns=columns, question=question, sample_values=sample_values,
                ),
            )
            if isinstance(spec, list):
                spec = spec[0] if spec else {}
            groupby_column = spec.get("groupby_column")
            value_column = spec.get("value_column")
            agg = spec.get("agg")
            chart_type = spec.get("chart_type", "bar")
            filter_values = spec.get("filter_values")
            answer_summary = spec.get("answer_summary", "")

            # AIが配列で返してしまうことがある（列名は本来1つの文字列のはず）ため、
            # 先頭要素を使うことで「unhashable type: 'list'」での異常終了を防ぐ。
            if isinstance(groupby_column, list):
                groupby_column = groupby_column[0] if groupby_column else None
            if isinstance(value_column, list):
                value_column = value_column[0] if value_column else None
            if not isinstance(filter_values, list):
                filter_values = None

            if groupby_column not in df.columns or value_column not in df.columns:
                raise ValueError("AIが指定した列がCSVに存在しません。")
            if agg not in ALLOWED_AGG:
                raise ValueError("未対応の集計方法です。")
            if chart_type not in ALLOWED_CHART:
                chart_type = "bar"

            target_df = df
            if filter_values:
                col_str = df[groupby_column].astype(str)
                mask = col_str.apply(
                    lambda v: any(str(fv).lower() in v.lower() or v.lower() in str(fv).lower() for fv in filter_values)
                )
                target_df = df[mask]
                if target_df.empty:
                    raise ValueError("質問で指定された項目がCSV内に見つかりません。")

            grouped = target_df.groupby(groupby_column)[value_column].agg(agg)

            # 質問が特定の項目を指している場合、AIに数値を推測させず、
            # 実際にpandasで集計した値から正確な回答文を組み立てる。
            if filter_values:
                parts = [f"{label}: {value:,.0f}" for label, value in grouped.items()]
                answer_summary = f"{'・'.join(str(v) for v in filter_values)}の{value_column}（{agg}）は、" + "、".join(parts) + "でした。"

            fig, ax = plt.subplots(figsize=(7, 4))
            if chart_type == "line":
                grouped.plot.line(ax=ax, marker="o")
            else:
                grouped.plot.bar(ax=ax)
            ax.set_xlabel(groupby_column)
            ax.set_ylabel(f"{value_column}（{agg}）")
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            plt.close(fig)
            buf.seek(0)
            import base64
            chart_data_url = "data:image/png;base64," + base64.b64encode(buf.read()).decode()
        except Exception as e:
            error_message = f"分析に失敗しました: {e}"

        preview_html = df.head(5).to_html(classes="data-table", index=False)
        summary_html = _describe_html(df)
        return render_template(
            "index.html",
            preview_html=preview_html,
            summary_html=summary_html,
            question=question,
            answer_summary=answer_summary,
            chart_data_url=chart_data_url,
            error_message=error_message,
        )

    @app.route("/insight", methods=["POST"])
    def insight():
        csv_path = _csv_path_for_session()
        if csv_path is None:
            flash("先にCSVをアップロードしてください。", "error")
            return redirect(url_for("index"))

        df = pd.read_csv(csv_path)
        summary = df.describe(include="all").fillna("").to_string()

        insight_text = None
        try:
            insight_text = call_claude_text(
                None, "claude-haiku-4-5-20251001", 500,
                INSIGHT_PROMPT_TEMPLATE.format(summary=summary),
            )
        except Exception as e:
            flash(f"インサイト生成に失敗しました: {e}", "error")

        preview_html = df.head(5).to_html(classes="data-table", index=False)
        summary_html = _describe_html(df)
        return render_template(
            "index.html",
            preview_html=preview_html,
            summary_html=summary_html,
            insight_text=insight_text,
        )

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5035)

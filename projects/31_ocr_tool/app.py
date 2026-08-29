import io
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from dotenv import load_dotenv
from flask import Flask, render_template, request, flash, redirect, url_for, Response
from PIL import Image

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import call_claude_text

load_dotenv()

BASE_DIR = Path(__file__).parent
LOCAL_TESSDATA = BASE_DIR / "tessdata"

if LOCAL_TESSDATA.exists():
    # Windowsローカル開発時、Tesseract本体に日本語データ(jpn.traineddata)が
    # 入っていない場合があるため、プロジェクト内のtessdata/を明示的に指定する。
    # Render本番ではbuildCommandのapt-getで入るため、このブロックは通らない。
    os.environ["TESSDATA_PREFIX"] = str(LOCAL_TESSDATA)

_DEFAULT_WINDOWS_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if tesseract_cmd := os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
elif not shutil.which("tesseract") and os.path.exists(_DEFAULT_WINDOWS_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = _DEFAULT_WINDOWS_TESSERACT

CORRECTION_PROMPT_TEMPLATE = (
    "次はOCR（光学文字認識）で抽出したテキストです。誤字脱字を補正し、"
    "段落・改行を整えて自然な日本語の文章に整形してください。"
    "本文の内容を要約・省略せず、補正後のテキストだけを出力してください。\n\n{ocr_text}"
)


def _preprocess_image(image: Image.Image) -> np.ndarray:
    """OCR精度向上のため、グレースケール化とコントラスト調整を行う。"""
    array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    array = cv2.equalizeHist(array)
    _, array = cv2.threshold(array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return array


def _ocr_image(image: Image.Image) -> str:
    processed = _preprocess_image(image)
    return pytesseract.image_to_string(processed, lang="jpn+eng").strip()


def _load_pages(file) -> list[Image.Image]:
    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        from pdf2image import convert_from_bytes
        return convert_from_bytes(file.read())
    return [Image.open(file.stream)]


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB
    # hub_appの全アプリが同じCookie名"session"を共有すると、別アプリへの訪問で
    # セッションが上書きされCSRFトークンが消える問題があるため、一意な名前にする。
    app.config["SESSION_COOKIE_NAME"] = "session_31_ocr_tool"
    init_csrf(app)

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/ocr", methods=["POST"])
    def ocr():
        file = request.files.get("image_file")
        allowed_ext = (".jpg", ".jpeg", ".png", ".pdf")
        if not file or not file.filename.lower().endswith(allowed_ext):
            flash("JPG・PNG・PDFファイルを選択してください。", "error")
            return redirect(url_for("index"))

        proofread = request.form.get("proofread") == "on"

        try:
            pages = _load_pages(file)
        except Exception:
            flash("ファイルの読み込みに失敗しました。形式を確認してください。", "error")
            return redirect(url_for("index"))

        raw_texts = [_ocr_image(page) for page in pages]
        raw_text = "\n\n--- 次のページ ---\n\n".join(raw_texts)

        result_text = raw_text
        if proofread and raw_text and os.environ.get("GEMINI_API_KEY"):
            try:
                result_text = call_claude_text(
                    None, "claude-haiku-4-5-20251001", 4000,
                    CORRECTION_PROMPT_TEMPLATE.format(ocr_text=raw_text),
                ).strip()
            except Exception:
                flash("AIによる誤字補正に失敗したため、OCR結果をそのまま表示します。", "error")

        return render_template(
            "index.html",
            raw_text=raw_text,
            result_text=result_text,
            page_count=len(pages),
        )

    @app.route("/download", methods=["POST"])
    def download():
        text = request.form.get("text", "")
        return Response(
            text,
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=ocr_result.txt"},
        )

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5031)

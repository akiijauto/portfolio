import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from PIL import Image, ImageDraw, ImageFont
import qrcode
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import call_claude_text

load_dotenv()

BASE_DIR = Path(__file__).parent

# 名刺サイズ91mm×55mm。300dpiでピクセル換算。
CARD_DPI = 300
CARD_W_PX = int(91 / 25.4 * CARD_DPI)
CARD_H_PX = int(55 / 25.4 * CARD_DPI)


def _build_vcard(name, title, company, email, phone, url):
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
    if company:
        lines.append(f"ORG:{company}")
    if title:
        lines.append(f"TITLE:{title}")
    if phone:
        lines.append(f"TEL:{phone}")
    if email:
        lines.append(f"EMAIL:{email}")
    if url:
        lines.append(f"URL:{url}")
    lines.append("END:VCARD")
    return "\n".join(lines)


def _wrap_to_width(draw, text, font, max_width):
    lines = []
    current = ""
    for ch in text:
        if draw.textlength(current + ch, font=font) > max_width and current:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines


def _build_card_image(name, title, company, email, phone, url, catchphrase):
    vcard = _build_vcard(name, title, company, email, phone, url)
    qr_size = 220
    qr_img = qrcode.make(vcard).convert("RGB")
    qr_img = qr_img.resize((qr_size, qr_size))

    card = Image.new("RGB", (CARD_W_PX, CARD_H_PX), "white")
    draw = ImageDraw.Draw(card)

    # OS標準フォント(Meiryo等)はVPS(Linux)に存在せず文字化け・極小フォールバックの原因になるため、
    # 日本語グリフを同梱したNoto Sans JPをBASE_DIRから絶対パスで読み込む。
    # サイズは視認性向上のため元の約2倍(40/26/22→80/52/44)。
    font_bold_path = BASE_DIR / "assets" / "NotoSansJP-Bold.ttf"
    font_regular_path = BASE_DIR / "assets" / "NotoSansJP-Regular.ttf"
    try:
        font_bold = ImageFont.truetype(str(font_bold_path), 80)
        font_regular = ImageFont.truetype(str(font_regular_path), 52)
        font_small = ImageFont.truetype(str(font_regular_path), 44)
    except OSError:
        font_bold = font_regular = font_small = ImageFont.load_default()

    text_x = 30
    text_y = 30
    full_width = CARD_W_PX - text_x - 40
    narrow_width = CARD_W_PX - qr_size - 40 - text_x
    qr_top = CARD_H_PX - qr_size - 20
    bottom_limit = CARD_H_PX - 20

    def draw_field(text, font, line_height, color):
        nonlocal text_y
        for line in _wrap_to_width(draw, text, font, full_width):
            if text_y + line_height > bottom_limit:
                return
            max_width = narrow_width if text_y + line_height > qr_top else full_width
            line = _wrap_to_width(draw, line, font, max_width)[0]
            draw.text((text_x, text_y), line, fill=color, font=font)
            text_y += line_height

    draw_field(name, font_bold, 110, "black")
    if title or company:
        draw_field(f"{title}　{company}".strip("　"), font_regular, 80, "#333333")
    for value in (phone, email, url):
        if value:
            draw_field(value, font_small, 64, "#555555")
    if catchphrase:
        draw_field(catchphrase, font_small, 64, "#888888")

    card.paste(qr_img, (CARD_W_PX - qr_size - 20, CARD_H_PX - qr_size - 20))
    return card


def _image_to_pdf_bytes(card_image):
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(91 * mm, 55 * mm))
    pdf.drawImage(ImageReader(card_image), 0, 0, width=91 * mm, height=55 * mm)
    pdf.showPage()
    pdf.save()
    buf.seek(0)
    return buf


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    # hub_app(複数アプリを1プロセスにマウントする方式)では全アプリが同じドメイン・
    # 同じCookie名"session"を使うと、別アプリへの訪問でセッションが上書きされ
    # CSRFトークンが消えてしまう("The CSRF session token is missing.")。
    # アプリごとに一意なCookie名にして衝突を防ぐ。
    app.config["SESSION_COOKIE_NAME"] = "session_28_qr_meishi"
    init_csrf(app)

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/generate", methods=["POST"])
    def generate():
        name = request.form.get("name", "").strip()
        title = request.form.get("title", "").strip()
        company = request.form.get("company", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        url = request.form.get("url", "").strip()
        want_catchphrase = request.form.get("want_catchphrase") == "on"

        if not name:
            flash("名前を入力してください。", "error")
            return redirect(url_for("index"))

        catchphrase = ""
        if want_catchphrase and os.environ.get("GEMINI_API_KEY"):
            try:
                prompt = (
                    f"次の人物のデジタル名刺に添える、印象的な一言キャッチコピーを"
                    f"日本語で15文字以内、1行だけ出力してください。\n"
                    f"名前: {name} / 肩書き: {title} / 会社: {company}"
                )
                catchphrase = call_claude_text(None, "claude-haiku-4-5-20251001", 100, prompt).strip()
            except Exception:
                catchphrase = ""

        card_image = _build_card_image(name, title, company, email, phone, url, catchphrase)
        pdf_buf = _image_to_pdf_bytes(card_image)

        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{name}_meishi.pdf",
        )

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5028)

# 画像→テキスト OCR変換ツール

写真・スキャン画像・PDFをアップロードすると文字起こしを行い、AIで誤字補正・整形して
出力するWebアプリです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. 画像（JPG/PNG）またはPDFをアップロードする
2. OpenCVによる前処理（グレースケール化・二値化）の後、Tesseract OCRで文字起こしする
3. チェックボックスをONにすると、Gemini APIが誤字補正・文章整形を行う
4. 整形済みテキストをワンクリックでコピー、またはTXTファイルとしてダウンロードできる
5. 複数ページのPDFも一括で文字起こしできる

## 事前準備（ローカル開発・Windows）

このアプリはpipパッケージだけでなく、OS側にOCRエンジンが必要です。

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
winget install --id oschwartz10612.Poppler -e
```

日本語データは標準インストールに含まれないため、別途取得して配置します。

```bash
# tesseract-ocr/tessdata公式リポジトリからjpn.traineddataを取得し、
# projects/31_ocr_tool/tessdata/ に配置する（Program Filesへの書き込み権限が
# ない環境でも動くよう、アプリ側でこのフォルダを優先的に読む）
curl -L -o tessdata/jpn.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/jpn.traineddata
```

`tessdata/`はリポジトリには含めません（`.gitignore`対象、約35MBの言語データのため）。

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 任意 | AIによる誤字補正・文章整形を使う場合のみ必要 |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |
| `TESSERACT_CMD` | 任意 | tesseract.exeが標準パスに無い場合のみフルパスを指定 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 必要に応じてGEMINI_API_KEYを設定
python app.py
```

ブラウザで `http://localhost:5031/` を開きます。

## テスト

```bash
python -m pytest projects/31_ocr_tool/tests/test_app.py -v
```

テストではOCRエンジン自体はモックしており、Tesseractの実行環境が無くても通過します。

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project31-ocr-tool` として
個別デプロイします。`buildCommand`で`apt-get install tesseract-ocr tesseract-ocr-jpn poppler-utils`
を実行するため、ローカルのような手動セットアップは不要です。

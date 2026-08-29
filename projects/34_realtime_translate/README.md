# 多言語リアルタイム翻訳チャット

テキストを入力すると、日・英・中・韓の4言語へリアルタイムにストリーミング翻訳する
チャットWebアプリです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. チャット欄にテキストを入力して送信する
2. Gemini APIのストリーミングモードで4言語に同時翻訳し、生成中の文字がその場で
   画面に追加されていく
3. 翻訳結果をワンクリックでコピーできる
4. 翻訳履歴がSQLiteに保存され、画面下部に一覧表示される

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | 翻訳に使用 |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # GEMINI_API_KEYを設定
python app.py
```

ブラウザで `http://localhost:5034/` を開きます。

## テスト

```bash
python -m pytest projects/34_realtime_translate/tests/test_app.py -v
```

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project34-realtime-translate` として
個別デプロイします。SSEストリーミングを安定動作させるため、gunicornは
`--worker-class gthread --threads 4` で起動します。環境変数 `GEMINI_API_KEY` を
Renderのダッシュボードで設定してください。

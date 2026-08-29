# Markdown→スライド自動生成

Markdownテキストを入力するだけで、HTMLプレゼンテーション（reveal.js）とPowerPoint
ファイルの両方を自動生成できるWebアプリです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. テキストエリアにMarkdownを入力する（`---` でスライドを区切る）
2. テーマカラーを選んで「プレビューを生成」を押すと、reveal.jsスライドがその場で表示される
3. プレビュー画面から「PPTXをダウンロード」を押すと、同内容のPowerPointファイルが落ちる
4. チェックボックスをONにすると、Gemini APIが章立て・スライド構成を自動整理する（任意）

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 任意 | AIによるスライド構成最適化を使う場合のみ必要 |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 必要に応じてGEMINI_API_KEYを設定
python app.py
```

ブラウザで `http://localhost:5033/` を開きます。

## テスト

```bash
python -m pytest projects/33_md_slide_gen/tests/test_app.py -v
```

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project33-md-slide-gen` として
個別デプロイします。環境変数 `GEMINI_API_KEY` をRenderのダッシュボードで設定してください。

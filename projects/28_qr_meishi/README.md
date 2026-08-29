# QRコード名刺メーカー

名前・肩書き・連絡先を入力するだけで、QRコード（vCard）付きのデジタル名刺PDFを
生成・ダウンロードできるWebアプリです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. フォームに名前・肩書き・会社名・メール・電話・URLを入力する
2. 「名刺PDFを生成」を押すと、QRコード付きの名刺PDF（91mm×55mm）がダウンロードされる
3. QRコードをスマホで読み取ると連絡先（vCard）として取り込める
4. チェックボックスをONにすると、Gemini APIが名刺用キャッチコピーを1行生成する（任意）

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 任意 | キャッチコピー自動生成を使う場合のみ必要 |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 必要に応じてGEMINI_API_KEYを設定
python app.py
```

ブラウザで `http://localhost:5028/` を開きます。

## テスト

```bash
python -m pytest projects/28_qr_meishi/tests/test_app.py -v
```

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project28-qr-meishi` として
個別デプロイします。環境変数 `GEMINI_API_KEY` をRenderのダッシュボードで設定してください。

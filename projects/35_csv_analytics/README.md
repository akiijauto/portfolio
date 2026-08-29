# CSVデータ 対話型分析ツール

CSVをアップロードして自然言語で質問すると、AIがグラフ＋テキストで回答する
対話型データ分析Webアプリです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. CSVファイルをアップロードする
2. 先頭5行のプレビューと統計サマリー（`describe()`）を確認する
3. 「月別の売上合計は？」のように自然言語で質問すると、AIが集計内容を解釈し
   グラフと一言回答を表示する
4. 「このデータで他に気になる点は？」ボタンで、AIが追加の気づきを提案する

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | 質問解釈・インサイト生成に使用 |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # GEMINI_API_KEYを設定
python app.py
```

ブラウザで `http://localhost:5035/` を開きます。

## テスト

```bash
python -m pytest projects/35_csv_analytics/tests/test_app.py -v
```

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project35-csv-analytics` として
個別デプロイします。環境変数 `GEMINI_API_KEY` をRenderのダッシュボードで設定してください。

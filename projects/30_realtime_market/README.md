# リアルタイム為替・株価モニター

WebSocketで為替・株価データをリアルタイムにプッシュし、ライブグラフで表示する
Webアプリです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. ページを開くと、USD/JPY・EUR/JPY・日経225・S&P500の価格が5秒ごとに自動更新される
2. USD/JPYのライブグラフがChart.jsでリアルタイムに更新される
3. 今日の相場に関するAIの一言コメントが表示される（1日1回生成）
4. USD/JPYのアラート閾値を設定すると、超えた時点でブラウザ通知が届く

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 任意 | 今日の一言コメント生成に使用。未設定時はコメント欄が空になる |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 必要に応じてGEMINI_API_KEYを設定
python app.py
```

ブラウザで `http://localhost:5030/` を開きます。

## テスト

```bash
python -m pytest projects/30_realtime_market/tests/test_app.py -v
```

テストでは`create_app(start_background=False)`を使い、yfinanceへの実通信を伴う
バックグラウンドループを起動しません。

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project30-realtime-market` として
個別デプロイします。WebSocketを安定動作させるため、本番は`gunicorn --worker-class eventlet -w 1`
で起動します。環境変数 `GEMINI_API_KEY` をRenderのダッシュボードで設定してください。

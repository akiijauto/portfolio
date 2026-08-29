# LINE Bot → タスク管理連携

LINEで送ったメッセージをAIが解析してタスクとして自動登録し、期限前にLINEで
リマインダーを送るタスク管理Botです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. LINEでメッセージ（例: 「明日までに資料を提出する」）を送るとタスクとして登録される
2. 「一覧」と送ると未完了タスクの一覧が返信される
3. 期限が翌日のタスクには毎朝9時に自動でリマインダーが届く
4. Webダッシュボードでタスクの一覧確認・完了チェックができる

## 事前準備（LINE Developers）

1. [LINE Developers](https://developers.line.biz/)でMessaging APIチャネルを作成する
2. チャネルアクセストークン・チャネルシークレットを取得する
3. **本番デプロイ後**、チャネルの「Messaging API設定」でWebhook URLに
   `https://<本番ドメイン>/webhook` を設定し、Webhookの利用をONにする
   （LINEはHTTPSの公開URLを要求するため、ローカル開発中は設定できない）

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | タスク名・期限・カテゴリの抽出に使用 |
| `LINE_CHANNEL_ACCESS_TOKEN` | 必須 | LINE Messaging APIの返信・プッシュ送信に使用 |
| `LINE_CHANNEL_SECRET` | 必須 | Webhookの署名検証に使用 |
| `SECRET_KEY` | 任意 | Flaskセッション用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 各APIキー・LINEチャネル情報を設定
python app.py
```

ブラウザで `http://localhost:5037/` を開くとダッシュボードが表示されます。

## テスト

```bash
python -m pytest projects/37_line_task_bot/tests/test_app.py -v
```

テストではLINEチャネルシークレットを使って実際にHMAC-SHA256署名を計算し、
Webhookの署名検証ロジックそのものを検証しています（LINE API呼び出し自体はモック）。

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project37-line-task-bot` として
個別デプロイします。デプロイ後、LINE Developersコンソールで本番URLをWebhook URLに
設定してください（この手順はユーザー自身で行う必要があります）。

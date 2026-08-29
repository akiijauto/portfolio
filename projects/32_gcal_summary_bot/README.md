# Googleカレンダー連携 予定要約Bot

Googleカレンダーの今週の予定をAIが要約し、毎朝Discord・メールへ自動送信するBotです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. 「Googleでログイン」から初回のみOAuth2認証を行う
2. ダッシュボードで今週の予定一覧とAI要約（重要度順）を確認できる
3. 毎朝8時（JST）に自動でDiscord・メールへ要約が送られる
4. 「今すぐ要約を送信する」ボタンで手動実行もできる

## 事前準備（Google Cloud Console）

1. Google Cloud ConsoleでOAuth2クライアントID（種類: ウェブアプリケーション）を作成する
2. 承認済みのリダイレクトURIに以下を追加する
   - ローカル開発: `http://localhost:5032/auth/callback`
   - Render本番: `https://<本番ドメイン>/auth/callback`
3. Google Calendar APIを有効化する

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | 予定の要約・優先度ランク付けに使用 |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | 必須 | Google Cloud ConsoleのOAuth2クライアント情報 |
| `DISCORD_WEBHOOK_URL` | 任意 | 未設定時はDiscord送信をスキップ |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | 任意 | 未設定時はメール送信をスキップ |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 各APIキー・OAuth2情報を設定
python app.py
```

ブラウザで `http://localhost:5032/` を開き、「Googleでログイン」から認証してください。
（この同意操作はユーザー本人のGoogleアカウントでのログインが必要で、自動化できません）

## テスト

```bash
python -m pytest projects/32_gcal_summary_bot/tests/test_app.py -v
```

テストではOAuth認証・Calendar API・Gemini API・Discord・SMTPをすべてモックしています。
OAuth2の認可URL生成（`/auth/login`）はダミーのクライアントIDを使って実機確認済みです
（client_id・scope・redirect_uri・PKCEパラメータが正しく付与されることを確認）。

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project32-gcal-summary-bot` として
個別デプロイします。Render上のドメインが確定したら、Google Cloud Consoleの
承認済みリダイレクトURIに本番URLを追加してください。

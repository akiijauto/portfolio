# Webフォーム→Notion自動転記Bot

Webフォームの問い合わせ内容をAIで要約・分類し、Notion DBへ自動保存。管理者への
通知メールと送信者への自動返信メールも送るBotです。

> 詳細な仕様は [要件定義.md](要件定義.md) を参照してください。

## できること

1. 名前・メール・用件・詳細を入力してフォームを送信する
2. Gemini APIが内容を要約し、5カテゴリのいずれかに自動分類する
3. Notion DBに日時・名前・メール・用件・カテゴリ・要約・ステータス（初期値「新規」）が
   自動で1行追加される
4. 管理者（`ADMIN_EMAIL`）へ通知メールが送られる
5. 送信者へ自動返信メールが送られる

## 環境変数

`.env.example` をコピーして `.env` を作成し、値を設定してください。

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | 必須 | 要約・カテゴリ分類に使用 |
| `NOTION_API_KEY` | 必須 | Notion APIトークン |
| `NOTION_DATABASE_ID` | 必須 | 保存先データベースのID |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | 任意 | メール送信に使用。未設定時はメール送信をスキップする |
| `ADMIN_EMAIL` | 任意 | 管理者通知メールの宛先 |
| `SECRET_KEY` | 任意 | Flaskセッション・CSRF用。未設定時は起動ごとに自動生成 |

## Notion DBの準備

「名前」（title）「メール」（email）「用件」（rich_text）「カテゴリ」（select:
新規お問い合わせ／サポート依頼／申込み／クレーム／その他）「要約」（rich_text）
「ステータス」（select: 新規／対応中／完了）「日時」（date）のプロパティを持つ
データベースを用意してください。

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env  # 各APIキー・SMTP情報を設定
python app.py
```

ブラウザで `http://localhost:5029/` を開きます。

## テスト

```bash
python -m pytest projects/29_form_notion_bot/tests/test_app.py -v
```

テストではNotion API・Gemini API・SMTP送信をすべてモックしています。
（実機でのNotion書き込みは開発時に別途確認済み）

## デプロイ（Render）

このフォルダの `render.yaml` を使い、Renderサービス名 `project29-form-notion-bot` として
個別デプロイします。各環境変数をRenderのダッシュボードで設定してください。

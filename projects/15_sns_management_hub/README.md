# SNS統合管理ツール

テーマ提案・ハッシュタグ最適化・投稿バリエーション生成・画像プロンプト生成・予約投稿カレンダー（Notion連携）・
Discord/Twitter自動投稿・効果分析までを1画面にまとめた、SNS運用のためのオールインワンツールです。
旧Project 01（SNS投稿文自動生成ツール）・旧Project 06（SNS半自動運用システム）の機能を統合し、本ツールに一本化しました。

## できること

1. **①テーマ提案** — 業界・ターゲットを入力するとAIが投稿テーマを提案。過去の効果分析データから人気テーマには🔥バッジが付く
2. **②ハッシュタグ最適化** — テーマとSNS種別（Instagram/Twitter/LINE）に合わせて、最適な個数・傾向のハッシュタグセットと選定戦略を生成
3. **③投稿文生成・画像プロンプト** — 同じテーマから「問題提起型」「メリット提示型」「ストーリー型」の3パターンの投稿文を生成し、選択した投稿文に合うMidjourney/DALL-E向け画像プロンプト（英語）も生成。②のハッシュタグと合わせて投稿カレンダーに保存可能
4. **④投稿カレンダー** — Notion DB上の投稿を一覧表示し、下書き→承認→予約→投稿済みのステータス管理。予約日時の編集・取消、Discordへの投稿通知、Twitterへの自動投稿、投稿の削除を行える
5. **⑤効果分析** — 投稿後のいいね・コメント・リーチ数を記録し、トピック別の人気度ランキングとハッシュタグ利用ランキングを表示

バックグラウンドではAPSchedulerが1分間隔で動作し、予約時刻になった投稿を自動投稿（LINE/Twitterは自動投稿、それ以外はDiscordへリマインド通知）、
予約15分前にもDiscordへリマインド通知します。

## 使い方

1. 「①テーマ提案」タブで業界・ターゲット・提案数を入力してテーマを生成し、使いたいテーマをクリックすると「③投稿文生成」のテーマ欄に反映される
2. 「②ハッシュタグ最適化」タブでテーマ・SNS・業界（任意）を入力して生成し、使いたいハッシュタグをクリックして選択
3. 「③投稿文生成」タブでテーマ・SNS・トーンを入力して3案を生成し、使いたい1案をクリックして選択。必要なら「🎨画像プロンプトを生成」で画像生成プロンプトを取得
4. （任意）投稿日時を入力し、「📅 投稿カレンダーに保存」を押すと、選択した投稿文＋②で選択中のハッシュタグが投稿カレンダー（Notion DB）に「下書き」として保存される
5. 「④投稿カレンダー」タブで投稿を承認・予約・編集・取消・削除し、Discord/Twitterへの投稿を行う
6. 「⑤効果分析」タブで投稿後のいいね・コメント・リーチを記録し、人気トピック・ハッシュタグランキングを確認する

## ディレクトリ構成

```
15_sns_management_hub/
├── app.py        … Flaskアプリ本体（ルーティング、APScheduler）
├── generator.py  … テーマ提案・ハッシュタグ・バリエーション・画像プロンプト生成、Notionカレンダー操作
├── engagement.py … 効果分析（SQLiteによるエンゲージメント記録・集計）
├── notifier.py   … Discord Webhook通知
├── templates/
│   └── index.html
└── static/
    ├── app.js
    ├── base.css
    └── style.css
```

## セットアップ・起動

```bash
# リポジトリのルートで依存パッケージをインストール
pip install -r requirements.txt

# .env に以下を設定
#   ANTHROPIC_API_KEY
#   NOTION_TOKEN（任意・カレンダー機能を使う場合）
#   NOTION_DATABASE_ID（任意・投稿カレンダーDB ID）
#   DISCORD_WEBHOOK_URL（任意・Discord通知を使う場合）
#   TWITTER_API_KEY / TWITTER_API_SECRET / TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_TOKEN_SECRET（任意・Twitter自動投稿を使う場合）

# このプロジェクトディレクトリで起動
cd projects/15_sns_management_hub
python app.py
```

ブラウザで http://127.0.0.1:5015 を開いて利用します。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask（Flask-WTF CSRF）+ APScheduler |
| AI生成 | Anthropic Claude API（claude-haiku-4-5） — テーマ提案・ハッシュタグ生成・バリエーション生成・画像プロンプト生成（JSON構文エラー時は自動リトライ） |
| カレンダー連携 | Notion API（`notion_client`） |
| 通知 | Discord Webhook |
| 自動投稿 | Twitter API（`tweepy`） |
| 効果分析 | SQLite（`engagement.db`） |

## 注意事項

- `NOTION_TOKEN` / `NOTION_DATABASE_ID` が未設定の場合、投稿カレンダーは「Notion未設定」の警告のみ表示し、エラーにはなりません
- `DISCORD_WEBHOOK_URL` が未設定の場合、Discordへの投稿・通知は行われません
- `TWITTER_API_KEY`等が未設定の場合、Twitterへの自動投稿はスキップされ、Discordへのリマインド通知のみ行われます
- Notionデータベースのプロパティ名（`名前`/`SNS種別`/`投稿文`/`状態`/`作成日`/`投稿日時`）に依存します
- AI呼び出し時にAnthropicのクレジット残高不足エラーが発生した場合、利用者には「一時的にサービス提供を中断している」旨を表示し、管理者へ自動通知（メール／Discord）します

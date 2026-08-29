# Web記事要約ツール

URLを入力するだけで、記事を「3行要約」「5行要約」「SNS投稿用」の3パターンに自動要約します。
キーワード検索から記事を探して要約することもできます。

## できること

1. **URL要約** — 記事URLを入力すると、本文を取得してClaudeが3行要約・5行要約・SNS投稿用テキストを生成
2. **キーワード検索→要約** — 調べたいキーワードを入力すると検索結果（タイトル・URL・概要）の一覧が表示され、気になる記事を選んでそのまま要約できる

## 使い方

### URLを直接要約する
1. 「記事URLを入力」欄にURLを入力し「要約する」を押す
2. 3行要約・5行要約・SNS投稿用テキストが表示される（各カードからコピー、または全体をテキストファイルでダウンロード可能）

### キーワードで検索して要約する
1. 「キーワードで記事を検索」欄に調べたいキーワードを入力し「検索する」を押す
2. 検索結果一覧からタイトル・概要を見て気になる記事の「このURLを要約する」を押す
3. 自動的にURL欄にセットされ、要約が実行される

## ディレクトリ構成

```
02_web_article_summary/
├── app.py          … Flaskアプリ本体（/search, /summarize ルーティング）
├── scraper.py      … 記事本文取得（fetch_article）、キーワード検索（search_articles）
├── summarizer.py   … Claudeによる要約生成
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## セットアップ・起動

```bash
# リポジトリのルートで依存パッケージをインストール
pip install -r requirements.txt

# .env に以下を設定
#   ANTHROPIC_API_KEY
#   TAVILY_API_KEY（任意・キーワード検索機能を使う場合。Project 13と共通）

# このプロジェクトディレクトリで起動
cd projects/02_web_article_summary
python app.py
```

ブラウザで http://127.0.0.1:5002 を開いて利用します。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask（Flask-WTF CSRF） |
| 記事取得 | requests + BeautifulSoup |
| AI要約 | Anthropic Claude API（claude-haiku-4-5）— `shared.call_claude_json` でJSON抽出・自動リトライ |
| 検索 | Tavily Search API（`TAVILY_API_KEY`、Project 13と同じ） |

## 注意事項

- `TAVILY_API_KEY` が未設定の場合、キーワード検索は利用できません（503エラーで案内文を表示。URL直接入力は引き続き利用可能）
- JavaScriptで動的にコンテンツを描画するサイトは本文を取得できない場合があります
- AI呼び出し時にAnthropicのクレジット残高不足エラーが発生した場合、利用者には「一時的にサービス提供を中断している」旨を表示し、管理者へ自動通知（メール／Discord）します

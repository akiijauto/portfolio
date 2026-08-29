# YouTube要約ツール

YouTube URLを入力するだけで、動画を「動画要約」「主要ポイント5選」「SNS投稿用」に自動要約します。
キーワードから字幕付き動画を検索して要約することもできます。

## できること

1. **URL要約** — YouTube URLを入力すると、字幕を取得してClaudeが動画要約・主要ポイント5選・SNS投稿用テキスト・カテゴリを生成
2. **キーワード検索→要約** — 調べたいキーワードを入力すると、字幕付き動画の検索結果（サムネイル・タイトル）の一覧が表示され、気になる動画を選んでそのまま要約できる

## 使い方

### URLを直接要約する
1. 「YouTube URLを入力」欄にURLを入力し「要約する」を押す
2. 動画要約・主要ポイント5選・SNS投稿用テキストが表示される（各カードからコピー、または全体をテキストファイルでダウンロード可能）

### キーワードで検索して要約する
1. 「キーワードで字幕付き動画を検索」欄に調べたいキーワードを入力し「検索する」を押す
2. 検索結果一覧（サムネイル・タイトル）から気になる動画をクリックする
3. 自動的にURL欄にセットされ、要約が実行される

## ディレクトリ構成

```
03_youtube_summary/
├── app.py          … Flaskアプリ本体（/search, /summarize ルーティング）
├── youtube.py      … 字幕・タイトル取得（fetch_video）、字幕付き動画検索（search_videos）
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
#   TAVILY_API_KEY（任意・キーワード検索機能を使う場合。Project 02/13と共通）

# このプロジェクトディレクトリで起動
cd projects/03_youtube_summary
python app.py
```

ブラウザで http://127.0.0.1:5003 を開いて利用します。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask（Flask-WTF CSRF） |
| 字幕取得 | youtube-transcript-api（日本語→英語→利用可能な言語の順に取得） |
| AI要約 | Anthropic Claude API（claude-haiku-4-5）— `shared.call_claude_json` でJSON抽出・自動リトライ |
| 動画検索 | Tavily Search API（`TAVILY_API_KEY`、Project 02/13と同じ）で候補を取得後、字幕の有無を確認 |

## 注意事項

- `TAVILY_API_KEY` が未設定の場合、キーワード検索は利用できません（503エラーで案内文を表示。URL直接入力は引き続き利用可能）
- 字幕が無効・非公開・年齢制限の動画は要約できません
- キーワード検索は字幕が取得可能な動画のみを表示するため、候補数によっては検索結果が少なくなる・0件になることがあります

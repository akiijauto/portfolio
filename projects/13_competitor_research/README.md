# 競合調査ツール

キーワードを入力するだけで検索上位の競合ページを自動スクレイピングし、Claude AIが「コンテンツギャップ」「差別化案」「推奨タイトル」を提案します。
SEO記事を書く前に「勝てる切り口」を見つけるためのツールです。

## できること

1. **競合ページ検索** — キーワードでTavily Search API（未設定時はDuckDuckGo検索）を行い、上位5件のURLを取得
2. **自動スクレイピング** — タイトル・メタディスクリプション・H1〜H3見出し・本文文字数を抽出
3. **AI競合分析** — Claudeが「共通パターン／コンテンツギャップ／差別化コンテンツ案／推奨タイトル案」をMarkdownレポートとして生成
4. **レポートのコピー** — 生成結果をワンクリックでコピー

## 使い方

1. 「①キーワード検索」タブでキーワードを入力し検索
2. 表示されたURL一覧から分析したいページにチェック（最大5件）
3. 「②分析結果」タブで分析を実行し、AIレポートを確認・コピー

## ディレクトリ構成

```
13_competitor_research/
├── app.py        … Flaskアプリ本体（ルーティング）
├── analyzer.py   … DuckDuckGo検索・スクレイピング・Claude分析
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
#   TAVILY_API_KEY（任意・未設定時はDuckDuckGoにフォールバック。https://tavily.com で無料登録）

# このプロジェクトディレクトリで起動
cd projects/13_competitor_research
python app.py
```

ブラウザで http://127.0.0.1:5013 を開いて利用します。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask（Flask-WTF CSRF） |
| 検索 | Tavily Search API（`TAVILY_API_KEY`設定時）／DuckDuckGo HTML検索（フォールバック） |
| スクレイピング | BeautifulSoup4 |
| AI分析 | Anthropic Claude API（claude-haiku-4-5、一時エラー時は自動リトライ） |

## 注意事項

- DuckDuckGo検索はRenderなどクラウドIPからの接続がブロックされ、本番環境で動作しない場合があります。`TAVILY_API_KEY`を設定することで安定して動作します（無料枠：月1,000件・カード不要）
- DuckDuckGoのHTML検索結果ページ構造に依存しているため、サイト側の仕様変更で検索結果が取得できなくなる可能性があります
- スクレイピング先サイトのbot対策・SSL証明書エラーにより、一部ページは取得できない場合があります（その場合はエラー扱いとして分析対象から除外）

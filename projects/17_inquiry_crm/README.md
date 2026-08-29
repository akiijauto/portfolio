# 問い合わせ管理CRM

問い合わせから成約まで、案件の進捗をステータス管理できるCRMです。
登録した問い合わせ内容に対して、Claude AIが返信メールの下書きも生成します。

## できること

1. **問い合わせ登録** — 会社名・担当者・連絡先・流入経路・問い合わせ内容を登録
2. **進捗管理** — ステータス（新規／連絡済み／商談中／成約／失注）でフィルタ・変更
3. **メモ機能** — 各案件に対応状況などのメモを保存
4. **AI返信文生成** — 案件を選択し、トーンと伝えたい内容を指定すると返信メールの下書きを生成
5. **件数サマリー** — 案件総数・新規・対応中・成約の件数を画面上部に表示

## 使い方

1. 「①新規登録」タブで問い合わせ情報を入力し「＋ 案件を登録」
2. 「②案件一覧・進捗管理」タブでステータスを絞り込み、案件ごとにステータス変更・メモ記入・削除
3. 「③AI返信文生成」タブで案件を選び、トーンと伝えたいことを指定して返信文を生成・コピー

## ディレクトリ構成

```
17_inquiry_crm/
├── app.py        … Flaskアプリ本体（ルーティング・SQLAlchemy初期化）
├── models.py     … Inquiryモデル定義（STATUSES/SOURCES）
├── generator.py  … Claudeへの返信文生成プロンプト
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

# このプロジェクトディレクトリで起動
cd projects/17_inquiry_crm
python app.py
```

ブラウザで http://127.0.0.1:5017 を開いて利用します。
初回起動時に `instance/inquiries.db`（SQLite）が自動作成されます。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask（Flask-WTF CSRF） |
| データ永続化 | Flask-SQLAlchemy + SQLite（`instance/inquiries.db`） |
| AI生成 | Anthropic Claude API（claude-haiku-4-5） — 返信文生成 |

## 注意事項

- `instance/inquiries.db` はGit管理対象外（`.gitignore`）です。環境ごとにデータは別管理になります
- 会社名・お名前は必須項目です。未入力では登録できません
- 問い合わせ内容・メモは2000文字以内に制限されています

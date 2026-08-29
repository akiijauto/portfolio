# 10. 家計簿ダッシュボード

認証付きの個人家計簿アプリ。支出を登録し、カテゴリ別ドーナツグラフと月別棒グラフでダッシュボード表示する。

## 機能

| 機能 | 詳細 |
| --- | --- |
| ユーザー認証 | 登録・ログイン・ログアウト。自分のデータのみ参照可能 |
| 支出登録 | 日付・金額・カテゴリ・メモを入力して登録 |
| ダッシュボード | 当月合計・カテゴリ別ドーナツ・月別棒グラフを一覧表示 |
| カテゴリ管理 | カテゴリの追加・削除（色付き）。登録時に5カテゴリを自動生成 |
| 最新20件表示 | 支出一覧を日付降順で表示・削除可能 |

## アーキテクチャ

```
Flask (port 5010)
├── / → ダッシュボード（集計グラフ + 最新取引）
├── /register, /login, /logout → 認証
├── /transactions/new, /transactions/<id>/delete → 支出CRUD
├── /categories, /categories/<id>/delete → カテゴリ管理
├── /api/chart/donut → カテゴリ別集計 JSON（Chart.js用）
└── /api/chart/bar → 月別集計 JSON（Chart.js用）

models.py（SQLAlchemy 3テーブル設計）
├── User（id, email, password_hash）
├── Category（id, user_id FK, name, color）
└── Transaction（id, user_id FK, category_id FK, amount, date, memo）
```

## 新技術（Sprint #4 習得）

| 技術 | 用途 |
| --- | --- |
| `SQLAlchemy func.sum + group_by` | カテゴリ別・月別の集計クエリ |
| 3テーブルFK設計 | User → Category → Transaction の階層リレーション |
| Chart.js 4.x | ドーナツグラフ・棒グラフのブラウザ描画 |

## ローカル起動

```bash
pip install -r requirements.txt  # ルートで実行

python projects/10_budget_tracker/app.py
# → http://localhost:5010
```

## データモデル

```python
User          # id / email / password_hash / created_at
  └── Category  # id / user_id / name / color(hex)
        └── Transaction  # id / user_id / category_id / amount / date / memo
```

## 技術スタック

- **Flask** + **Flask-Login** + **Flask-WTF** — Web / 認証 / CSRF
- **Flask-SQLAlchemy** — ORM（SQLite）
- **SQLAlchemy func.sum / group_by** — 集計クエリ
- **Chart.js 4.x** — グラフ描画（CDN）

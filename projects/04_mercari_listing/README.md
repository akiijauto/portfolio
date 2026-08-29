# 04_mercari_listing — メルカリ出品文生成ツール

## セットアップ

```bash
cd projects/04_mercari_listing
pip install flask anthropic
```

## 環境変数

`.env` に設定：

```
ANTHROPIC_API_KEY=your_key_here
```

## 起動コマンド

```bash
python app.py
```

ポート: **5004**

## 使い方

1. http://localhost:5004 を開く
2. 商品名・状態・カテゴリを入力して送信
3. タイトル・説明文・価格帯・出品コツが表示される

## ファイル構成

```
04_mercari_listing/
├── app.py          # Flask本体（41行）
├── generator.py    # Claudeプロンプト＆API呼び出し
├── templates/
│   └── index.html
└── static/
```

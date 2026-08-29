# 外部API連携ハブ

天気・為替・ニュース要約の3機能をまとめたWebアプリです。
「外部APIを `requests` で叩く・エラーハンドリングする・TTLキャッシュで無駄なAPI呼び出しを防ぐ」を学ぶ学習用ミニプロジェクトとして作成しました。

> 詳細な仕様は [要件定義書](要件定義書.md) を参照してください。

## できること

1. **天気検索** — 都市名を入力すると現在の気温・天気・風速を表示（Open-Meteo API、APIキー不要、10分キャッシュ）
2. **為替換算** — 通貨ペアと金額を選ぶと最新レートで換算（Frankfurter API、APIキー不要、1時間キャッシュ）
3. **ニュース要約** — NHKの最新ニュース5件をClaudeが3行で要約（30分キャッシュ）

## ディレクトリ構成

```
08_api_hub/
├── app.py          … Flaskアプリ本体（ルーティング）
├── fetchers.py     … 外部API呼び出し・TTLキャッシュ・エラーハンドリング
├── templates/
│   └── index.html  … 3タブ構成のUI
├── static/
│   ├── base.css
│   └── style.css
├── README.md
├── DEPLOY.md
└── 要件定義書.md
```

## セットアップ

### 必要要件
- Python 3.x
- Anthropic APIキー（ニュース要約機能のみ）

### 手順

```bash
# リポジトリルートで依存パッケージをインストール
pip install -r requirements.txt

# .env.example を参考に .env を作成し、以下を設定
#   ANTHROPIC_API_KEY（ニュース要約に使用）

# このプロジェクトで起動
cd projects/08_api_hub
python app.py
```

ブラウザで http://127.0.0.1:5008 を開いて利用します。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask |
| 外部API | Open-Meteo（天気）/ Frankfurter（為替）/ NHK RSS（ニュース） |
| AI要約 | Anthropic Claude API（claude-haiku-4-5） |
| キャッシュ | インメモリTTLキャッシュ（dict + timestamp）|
| フロントエンド | HTML / CSS / JavaScript（AJAX + タブ切替UI） |

## デプロイ

[Render](https://render.com/) への公開手順は [DEPLOY.md](DEPLOY.md) にまとめています。

## 今後の予定

- 天気の3時間ごと予報表示
- 為替レートの推移グラフ（Chart.js等）
- ニュースソースの追加（朝日・読売等のRSS）
- `functools.lru_cache` や `cachetools` への移行

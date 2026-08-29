# お問い合わせフォーム

ポートフォリオ(portal/index.html)からのお問い合わせを受け付ける軽量なフォームです。
送信内容はDiscordに通知され、メールアプリの起動なしに相談を送ることができます。

## できること

1. **お問い合わせ送信** — お名前・会社名・メールアドレス・ご相談のツール・ご相談内容を入力して送信
2. **ツールの事前選択** — `?tool=...` のクエリパラメータでご相談のツールを事前選択（portal/index.html の各CTAから利用）
3. **Discord通知** — 送信内容が即座にDiscordチャンネルへ通知される

## 使い方

1. フォームに必要事項を入力
2. 「送信する」をクリック
3. 「お問い合わせを受け付けました」と表示されれば完了

## ディレクトリ構成

```
22_contact_form/
├── app.py            … Flaskアプリ本体（ルーティング・送信処理・Discord通知）
├── _shared/          … csrf_setup.py・errors.py（app.pyが直接importする現行の依存。
│                        ルートのshared/から複製したもの）
├── requirements.txt  … このプロジェクト用の依存パッケージ
├── templates/
│   └── contact_form/
│       └── index.html
└── static/
    ├── app.js        … 文字数カウント・送信処理
    ├── base.css      … 全アプリ共通のベーススタイル
    └── style.css
```

## セットアップ・起動（ローカル）

```bash
# このプロジェクトディレクトリで依存パッケージをインストール
cd projects/22_contact_form
pip install -r requirements.txt

# .env に以下を設定
#   DISCORD_WEBHOOK_URL

python app.py
```

ブラウザで http://127.0.0.1:5022 を開いて利用します。

## 本番環境

https://ai-l-a-b-o.com/contact-form/ （Xserver VPS / hub_app 経由）

portal/index.html の各CTA・連絡先リンクはこの本番URLを参照しています。スマートフォンなど
ローカル環境外からも問い合わせ可能です。

配信経路: nginx（`location ~ ^/(...|contact-form|...)$` → 127.0.0.1:8100）
→ `hub_app.py` が `/contact-form` にこのアプリをマウント（hub_app.py の APPS を参照）。

環境変数（`DISCORD_WEBHOOK_URL` / `SECRET_KEY`）はVPS側で設定する。

※ 旧Vercelデプロイ（contact-form-gamma-tan.vercel.app）は停止済み（2026-08-24時点で404）。
   名残の `vercel.json` / `api/index.py` は参照元が無いことを確認のうえ2026-08-24に削除した
   （hub_app.py・start_all.py はいずれも `app.py` を直接ロードする）。

## 技術構成

| 項目 | 内容 |
| --- | --- |
| バックエンド | Flask（Flask-WTF CSRF） |
| 通知 | Discord Webhook — 問い合わせ内容をEmbed形式で送信 |
| ホスティング | Xserver VPS（nginx → hub_app.py の DispatcherMiddleware でマウント） |

## 注意事項

- メールアドレスは形式チェックのみ行い、実際に到達可能かは確認しません
- ご相談内容は1000文字以内です

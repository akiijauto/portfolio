# 11. GitHub → Discord Webhook中継サーバー

GitHubからWebhookを受信し、HMAC-SHA256署名を検証してDiscordにEmbed通知を送信する中継サーバー。

## 機能

| 機能 | 詳細 |
| --- | --- |
| HMAC-SHA256署名検証 | `X-Hub-Signature-256` ヘッダーを検証。不一致は403で拒否 |
| push通知 | ブランチ名・コミット数・最新コミットメッセージをDiscord Embedで送信 |
| pull_request通知 | PR番号・タイトル・アクション（opened/closed/merged）をEmbed送信 |
| issues通知 | Issue番号・タイトル・アクションをEmbed送信 |
| ping対応 | GitHub疎通確認に200 pongで応答 |
| 受信ログ | 直近50件の受信履歴をUIとAPIで確認可能（30秒自動更新） |

## アーキテクチャ

```
GitHub → POST /webhook/github
  └── verify_signature()  HMAC-SHA256 検証（失敗→403）
      └── handle_event()  イベント別ルーティング
          └── _send_discord_embed()  Discord Webhook POST
              └── _add_log()  スレッド安全なメモリログ

Flask (port 5011)
├── GET  /             → 管理UI（ログ一覧・設定手順）
├── POST /webhook/github → GitHub Webhook受信
└── GET  /api/logs     → ログJSON（30秒ポーリング用）
```

## 新技術（Sprint #5 習得）

| 技術 | 用途 |
| --- | --- |
| `hmac.compare_digest` + `hashlib.sha256` | タイミング攻撃耐性のあるHMAC検証 |
| `X-GitHub-Event` ヘッダールーティング | イベント種別に応じたEmbed生成 |
| Discord Embed API (`embeds` フィールド) | タイトル・本文・色・URLをもつリッチカード通知 |

## ローカル起動

```bash
pip install -r requirements.txt

# .env に設定
GITHUB_WEBHOOK_SECRET=your-webhook-secret  # GitHubのWebhook設定と同じ値
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

python projects/11_webhook_relay/app.py
# → http://localhost:5011
```

## 環境変数

| 変数名 | 必須 | 説明 |
| --- | --- | --- |
| `GITHUB_WEBHOOK_SECRET` | 推奨 | GitHub Webhookのシークレット。未設定時は署名検証をスキップ |
| `DISCORD_WEBHOOK_URL` | ✅ | DiscordチャンネルのWebhook URL |
| `SECRET_KEY` | 本番のみ | Flaskセッション署名用 |

## curlでのローカルテスト

```bash
# pushイベントをシミュレート（シークレットなし）
curl -X POST http://localhost:5011/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{"ref":"refs/heads/main","commits":[{"message":"test"}],"repository":{"full_name":"owner/repo"},"pusher":{"name":"you"},"compare":"https://github.com"}'
```

## 技術スタック

- **Flask** — Web サーバー
- **hmac + hashlib** — HMAC-SHA256署名検証（標準ライブラリ）
- **requests** — Discord Embed POST
- **threading.Lock** — ログリストのスレッド安全保護
- **pytz** — JSTタイムスタンプ

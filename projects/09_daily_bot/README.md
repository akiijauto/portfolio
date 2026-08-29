# 09. 毎朝Discordお知らせbot

APSchedulerで定期実行し、天気・為替をまとめてDiscordに自動配信するWebアプリ。

## 機能

| 機能 | 詳細 |
| --- | --- |
| 毎朝自動配信 | APScheduler（CronTrigger）で指定時刻にDiscordへ投稿 |
| 天気取得 | Open-Meteo API（東京、APIキー不要） |
| 為替取得 | Frankfurter API（USD/JPY、APIキー不要） |
| 手動送信 | ブラウザUIから「今すぐ送信」ボタンで即時配信 |
| 配信時刻変更 | UIから時刻を入力して保存（即時反映） |
| 実行ログ | 直近5件の成否をUI上に表示 |

## アーキテクチャ

```
Flask (port 5009)
├── / → index.html（ステータス・手動実行・スケジュール設定）
├── /api/run  POST  → run_digest() を即時実行
├── /api/schedule POST/DELETE → スケジュール変更・削除
└── /api/status GET → ジョブ状態 + ログ返却

scheduler.py（バックグラウンドスレッド）
├── BackgroundScheduler（APScheduler）+ CronTrigger（JST）
├── run_digest() → _build_message() → Discord Webhook POST
└── threading.Lock() でログリストを保護

外部依存（projects/08_api_hub/fetchers.py を再利用）
├── fetch_weather("Tokyo")
├── fetch_exchange("USD", "JPY", 1)
```

## ローカル起動

```bash
# 依存インストール（ルートで実行）
pip install -r requirements.txt

# .env に以下を設定（ルートの .env を共用）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# 起動（ルートから）
python projects/09_daily_bot/app.py
# → http://localhost:5009
```

## 環境変数

| 変数名 | 必須 | 説明 |
| --- | --- | --- |
| `DISCORD_WEBHOOK_URL` | ✅ | DiscordチャンネルのWebhook URL |
| `SECRET_KEY` | ✅（本番） | FlaskセッションとCSRFに使用 |

## Discordメッセージ例

```
🌅 デイリーダイジェスト — 2026/06/09 (Tue) 08:00 JST

🌤 天気（東京）：一部曇り / 24.5°C / 風速12km/h
💴 USD/JPY：1ドル = 157.3円（2026-06-09 時点）
```

## 技術スタック

- **Flask** — Web UI
- **APScheduler** — バックグラウンドCronジョブ
- **pytz** — JSTタイムゾーン管理
- **threading.Lock** — スレッド間共有リストの保護
- **Discord Webhooks** — メッセージ配信
- **fetchers.py（08_api_hub）** — 外部API取得ロジックの再利用

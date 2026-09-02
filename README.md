# 業務自動化Webアプリ ポートフォリオ

経理・事務・店舗運営の現場業務を対象に開発した、AI活用Webアプリ **35本**のソースコードです。
すべてFlaskで動作し、AI呼び出し・CSRF対策・エラー処理・通知を `shared/` に共通化しています。

- 稼働デモ: <https://ai-l-a-b-o.com>（登録不要・無料で試せます）
- 技術スタック: Python / Flask / SQLAlchemy / Google Gemini API / Anthropic API / Notion API / Discord Webhook / Chart.js / pytest

## 設計の要点

**AIプロバイダを1箇所に集約している。** 全アプリのAI呼び出しは `shared/utils.py` の
`call_claude_json` / `call_claude_text` を通り、環境変数 `AI_PROVIDER` で Gemini と Anthropic を
切り替えます。アプリ側のコードを一切変更せずにモデルを乗り換えられます。

**共通処理を横断的に効かせている。** CSRF（`shared/csrf_setup.py`）、
ユーザー向けエラーメッセージ（`shared/errors.py`）、Discord通知（`shared/notify.py`）は
各アプリが個別に実装せず、共通モジュールを読み込むだけで揃います。

**テストを1プロジェクトに集約している。** `projects/12_pytest_suite/` に
モック・インメモリDB・Flaskテストクライアントを使ったユニットテストをまとめています。

## アプリ一覧

### 店舗・現場業務

| ディレクトリ | 概要 |
| --- | --- |
| [`21_haccp_inspection`](projects/21_haccp_inspection/) | 写真ベース 衛生点検・HACCP記録サポート |
| [`23_store_insight_dashboard`](projects/23_store_insight_dashboard/) | 店舗改善インサイトダッシュボード |
| [`24_shift_scheduler`](projects/24_shift_scheduler/) | シフト作成アシスタントAI |
| [`26_inventory_predictor`](projects/26_inventory_predictor/) | 在庫発注タイミング予測AI |
| [`25_sop_generator`](projects/25_sop_generator/) | 業務マニュアル・SOP自動生成 |
| [`19_roleplay_training`](projects/19_roleplay_training/) | 接客・クレーム対応ロールプレイAI |
| [`20_voice_report`](projects/20_voice_report/) | 音声入力式 日報・引継ぎ自動整形 |
| [`27_recruitment_generator`](projects/27_recruitment_generator/) | 求人原稿・面接質問自動生成 |

### 経理・事務

| ディレクトリ | 概要 |
| --- | --- |
| [`17_inquiry_crm`](projects/17_inquiry_crm/) | 問い合わせ管理CRM（進捗ステータス管理＋返信文生成） |
| [`18_subsidy_matching`](projects/18_subsidy_matching/) | 補助金・助成金マッチング＆事業計画ドラフト生成 |
| [`10_budget_tracker`](projects/10_budget_tracker/) | 家計簿ダッシュボード（Chart.js + SQLAlchemy集計） |
| [`35_csv_analytics`](projects/35_csv_analytics/) | CSVデータ 対話型分析ツール |
| [`31_ocr_tool`](projects/31_ocr_tool/) | 画像→テキスト OCR変換ツール |
| [`22_contact_form`](projects/22_contact_form/) | お問い合わせフォーム |
| [`28_qr_meishi`](projects/28_qr_meishi/) | QRコード名刺メーカー（vCard生成） |

### コンテンツ生成

| ディレクトリ | 概要 |
| --- | --- |
| [`14_seo_article_generator`](projects/14_seo_article_generator/) | SEO記事生成ツール |
| [`16_ad_copy_generator`](projects/16_ad_copy_generator/) | 広告文生成ツール |
| [`15_sns_management_hub`](projects/15_sns_management_hub/) | SNS統合管理ツール |
| [`04_mercari_listing`](projects/04_mercari_listing/) | メルカリ出品文生成ツール |
| [`13_competitor_research`](projects/13_competitor_research/) | 競合調査ツール（Tavily検索 + 要約） |
| [`02_web_article_summary`](projects/02_web_article_summary/) | Web記事要約ツール |
| [`03_youtube_summary`](projects/03_youtube_summary/) | YouTube要約ツール |
| [`33_md_slide_gen`](projects/33_md_slide_gen/) | Markdown→スライド自動生成 |

### 連携・自動化

| ディレクトリ | 概要 |
| --- | --- |
| [`29_form_notion_bot`](projects/29_form_notion_bot/) | Webフォーム→Notion自動転記Bot |
| [`32_gcal_summary_bot`](projects/32_gcal_summary_bot/) | Googleカレンダー連携 予定要約Bot |
| [`37_line_task_bot`](projects/37_line_task_bot/) | LINE Bot→タスク管理連携 |
| [`11_webhook_relay`](projects/11_webhook_relay/) | GitHub→Discord Webhook中継（HMAC-SHA256署名検証） |
| [`09_daily_bot`](projects/09_daily_bot/) | 毎朝Discordお知らせBot（APScheduler） |
| [`08_api_hub`](projects/08_api_hub/) | 外部API連携ハブ（天気・為替・ニュース） |
| [`05_aliexpress_monitor`](projects/05_aliexpress_monitor/) | 価格の定期監視・Discord通知 |
| [`36_clipboard_formatter`](projects/36_clipboard_formatter/) | ブラウザ拡張連携 クリップボード自動整形 |
| [`34_realtime_translate`](projects/34_realtime_translate/) | 多言語リアルタイム翻訳チャット |
| [`30_realtime_market`](projects/30_realtime_market/) | リアルタイム為替・株価モニター |
| [`07_memo_app`](projects/07_memo_app/) | メモアプリ（ユーザー認証付き） |

### テスト

| ディレクトリ | 概要 |
| --- | --- |
| [`12_pytest_suite`](projects/12_pytest_suite/) | モック・インメモリDB・Flaskテストクライアントによるユニットテスト |
| [`38_lang_bench`](projects/38_lang_bench/) | バックエンド言語8種の性能比較ベンチマーク（Docker同時実行・k6負荷試験） |

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # 各APIキーを記入する
python start_all.py              # 全アプリ起動（ポート5002〜5037）
```

個別に動かす場合は各ディレクトリの `README.md` を参照してください。
`hub_app.py` は全アプリを1プロセスに束ねる本番用のエントリポイントです。

## このリポジトリについて

- 稼働環境の接続情報・運用ログ・実データ（DBファイル）は含みません。ソースコードのみです。
- `.env.example` の値はすべてプレースホルダです。

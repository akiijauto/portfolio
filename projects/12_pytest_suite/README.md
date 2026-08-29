# 12. pytest テストスイート

Sprint #3・#4・#5 で実装したモジュール、および Project 13〜17 のFlaskアプリに対して pytest でユニットテストを書いたスプリント。

## テスト構成

| ファイル | 対象 | テスト数 |
| --- | --- | --- |
| `test_webhook.py` | `11_webhook_relay/webhook.py` — 署名検証・Embed生成・イベントルーティング | 14 |
| `test_webhook_app.py` | `11_webhook_relay/app.py` — Flaskエンドポイント | 6 |
| `test_scheduler.py` | `09_daily_bot/scheduler.py` — Discord配信・ログ・スケジューラ | 7 |
| `test_budget.py` | `10_budget_tracker/app.py` — 認証・収支CRUD・Chart.js API | 14 |
| `test_competitor_research.py` | `13_competitor_research` — DDG検索・スクレイピング・AI分析 | 17 |
| `test_seo_article_generator.py` | `14_seo_article_generator` — アウトライン/記事生成API | 18 |
| `test_sns_management_hub.py` | `15_sns_management_hub` — ハッシュタグ/バリエーション/Notionカレンダー | 19 |
| `test_ad_copy_generator.py` | `16_ad_copy_generator` — 広告文一括生成API | 15 |
| `test_inquiry_crm.py` | `17_inquiry_crm` — 問い合わせCRUD + AI返信文生成（インメモリDB） | 29 |

**合計: 139テスト / 139 passed**

## 実行方法

```bash
# ルートから実行
python -m pytest projects/12_pytest_suite/ -v

# 特定ファイルだけ
python -m pytest projects/12_pytest_suite/tests/test_webhook.py -v
```

## 新技術（Sprint #6 習得）

| 技術 | 用途 |
| --- | --- |
| `pytest` フィクスチャ | `@pytest.fixture` でテストクライアント・DBを毎テスト初期化 |
| `unittest.mock.patch` | 外部APIコール（Discord / requests）をモックに差し替え |
| `patch.dict(os.environ)` | 環境変数をテスト内だけ上書き |
| `patch.object` | オブジェクトのメソッドをモック |
| `app.test_client()` | Flask テストクライアントでHTTPリクエストをシミュレート |
| `sqlite:///:memory:` | テスト用インメモリDB（ファイルを汚染しない） |
| `importlib.util.spec_from_file_location` | 既存 app.py を名前衝突なく動的インポート |

## 新技術（Project 13〜17 拡張時に追加）

| 技術 | 用途 |
| --- | --- |
| `sys.path.insert(0, ...)` + `sys.modules.pop(...)` | `generator.py`/`models.py`/`analyzer.py` など同名モジュールを複数プロジェクト間で衝突なくロード |
| `MagicMock` で `anthropic.Anthropic` 応答を再現 | `mock_client.messages.create.return_value.content[0].text` にJSON文字列を設定し、コードフェンス除去・JSONパースを検証 |
| `mock_client.messages.create.call_args.kwargs["messages"]` | AIへ送信したプロンプト本文の内容（文字数切り詰め・トーン別ルールなど）を検証 |
| `patch.object(<app_module>, "get_notion", ...)` | Notionクライアント未設定/設定済みの両分岐をテスト |
| `requests.get` をモックしたDOM/HTML解析テスト | DuckDuckGo検索結果のリダイレクトURL抽出・エンコーディングフォールバックを検証 |

## モック戦略

| ケース | 手法 |
| --- | --- |
| Discord HTTP POSTを止める | `patch.object(webhook, "_send_discord_embed")` |
| `requests.post` そのものを止める | `patch("scheduler.requests.post")` |
| GITHUB_WEBHOOK_SECRET を設定する | `patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "..."}` |
| DBをインメモリに差し替える | `app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"` + `db.drop_all() / db.create_all()` |
| Claude APIレスポンスをモックする | `patch.object(generator, "_client", return_value=mock_client)` |
| Notion APIをモックする | `patch.object(<app_module>, "get_notion", return_value=MagicMock())` |
| 検索/スクレイピング先のHTTPをモックする | `patch.object(analyzer.requests, "get", return_value=mock_response)` |

## 既知の修正履歴

- Project 13〜17 追加時、`10_budget_tracker` と `17_inquiry_crm` がともに `models.py` を持つことによるモジュール名衝突で `test_budget.py` の収集が失敗していた。`test_budget.py` 側でも `sys.path.insert(0, str(PROJECT))` + `sys.modules.pop("models"/"app")` を行うよう修正し解消。
- コミット `5f84b68`（セキュリティ修正: `GITHUB_WEBHOOK_SECRET` 未設定時はWebhookを拒否するよう変更）以降、`test_webhook.py::test_no_secret_always_passes` と `test_webhook_app.py` の署名なしリクエストのテストが実装と乖離していた。テストを「シークレット未設定時は拒否（403）」「署名ありリクエストのみ受理」という現行仕様に合わせて修正。

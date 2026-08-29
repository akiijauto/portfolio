"""
初心者向けエラーメッセージ集。
.envのキー名を露出せず、原因と解決策を日本語で案内する。
"""

MESSAGES = {
    # 設定ミス系
    "missing_discord":   "Discord通知の設定が見つかりません。設定ファイル(.env)にDISCORD_WEBHOOK_URLを追加してください。",
    "missing_twitter":   "Twitter/X APIの設定が見つかりません。設定ファイル(.env)にTwitterのAPIキーを追加してください。",
    "missing_notion":    "Notionの接続情報が見つかりません。設定ファイル(.env)を確認してください。",
    "missing_anthropic": "AI(Claude)のAPIキーが見つかりません。設定ファイル(.env)にANTHROPIC_API_KEYを追加してください。",

    # ネットワーク系
    "fetch_failed":      "ページの取得に失敗しました。URLが正しいか、インターネットに接続されているか確認してください。",
    "timeout":           "接続がタイムアウトしました。しばらく待ってから再試行してください。",

    # API系
    "twitter_paid":      "Twitter/X APIの無料プランでは投稿できません。有料プラン(Basic $100/月)が必要です。",
    "notion_not_found":  "Notionのページが見つかりません。IntegrationがそのページとDBに接続されているか確認してください。",
    "ai_error":          "AIの処理中にエラーが発生しました。しばらく待ってから再試行してください。",
    "ai_busy":           "AIが混み合っているか、通信が不安定です。1分ほど待ってから再試行してください。",
    "service_paused":    "申し訳ございません。現在、AI機能を一時的に提供できない状態になっております。"
                          "管理者へ自動で連絡しておりますので、しばらく時間をおいてから再度お試しください。",

    # スクレイピング系
    "no_transcript":     "この動画には字幕がありません。字幕付きの動画URLを入力してください。",
    "js_site":           "このサイトはJavaScriptで動いており、自動取得に対応していません。別のURLを試してください。",
    "price_not_found":   "価格を取得できませんでした。Bot対策により取得できない場合は「手動入力」で価格を登録してください。",

    # 汎用
    "internal_error":    "処理中にエラーが発生しました。しばらく待ってから再試行してください。",
    "invalid_input":     "入力値が無効です。内容を確認して再試行してください。",
}

def get(key: str, fallback: str = "") -> str:
    return MESSAGES.get(key, fallback or f"エラーが発生しました（{key}）。")

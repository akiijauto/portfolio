"""
初心者向けエラーメッセージ集（Vercelデプロイ用に shared/errors.py を複製）。
.envのキー名を露出せず、原因と解決策を日本語で案内する。
"""

MESSAGES = {
    "missing_discord":   "Discord通知の設定が見つかりません。設定ファイル(.env)にDISCORD_WEBHOOK_URLを追加してください。",
    "internal_error":    "処理中にエラーが発生しました。しばらく待ってから再試行してください。",
    "invalid_input":     "入力値が無効です。内容を確認して再試行してください。",
}

def get(key: str, fallback: str = "") -> str:
    return MESSAGES.get(key, fallback or f"エラーが発生しました（{key}）。")

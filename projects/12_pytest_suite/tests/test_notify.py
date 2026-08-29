"""shared/notify.py のテスト（管理者通知: メール / Discord / 未設定時のログ警告）。"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import notify


class TestNotifyAdmin:
    def test_no_config_logs_warning(self, caplog):
        with patch.dict("os.environ", {}, clear=True):
            with caplog.at_level("WARNING"):
                notify.notify_admin("件名", "本文")
        assert "管理者通知先が未設定" in caplog.text

    def test_discord_webhook_configured_sends_request(self, caplog):
        with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}, clear=True), \
             patch.object(notify, "requests") as mock_requests, \
             caplog.at_level("WARNING"):
            # status_codeを明示しないとMagicMockのまま比較され、TypeErrorが例外分岐に
            # 吸われて「成功パスを一度も通らないのに通るテスト」になる。
            mock_requests.post.return_value.status_code = 204
            notify.notify_admin("件名", "本文")
        mock_requests.post.assert_called_once()
        args, kwargs = mock_requests.post.call_args
        assert args[0] == "https://discord.test/webhook"
        assert "件名" in kwargs["json"]["content"]
        assert "本文" in kwargs["json"]["content"]
        # 送信できたので「未設定」警告は出ない
        assert "管理者通知先が未設定" not in caplog.text

    def test_discord_404_is_detected_and_reported(self, caplog):
        """Webhook失効(404)を無言で握り潰さないこと（2026-08-22に数週間見逃した）。"""
        with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}, clear=True), \
             patch.object(notify, "requests") as mock_requests, \
             caplog.at_level("WARNING"):
            mock_requests.post.return_value.status_code = 404
            notify.notify_admin("件名", "本文")
        assert "Webhookが削除されています" in caplog.text
        # 送信できていないのでsentが立たず、未通知の警告も出ること
        assert "管理者通知先が未設定" in caplog.text

    def test_discord_error_does_not_leak_webhook_url(self, caplog):
        """例外メッセージ経由でWebhook URLがログへ平文で残らないこと。"""
        # secret_audit.py の Discord Webhook パターンは discord.com / discordapp.com の
        # ホストだけを見る。架空の値でもpre-pushフックに引っかかるため .test を使う。
        url = "https://discord.test/api/webhooks/1234567890123456789/PLACEHOLDER_TOKEN"
        with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": url}, clear=True), \
             patch.object(notify, "requests") as mock_requests, \
             caplog.at_level("WARNING"):
            mock_requests.post.side_effect = Exception(f"404 Client Error for url: {url}")
            notify.notify_admin("件名", "本文")
        assert "PLACEHOLDER_TOKEN" not in caplog.text
        assert "<DISCORD_WEBHOOK_URL>" in caplog.text

    def test_discord_webhook_failure_does_not_raise(self, caplog):
        with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}, clear=True), \
             patch.object(notify, "requests") as mock_requests, \
             caplog.at_level("WARNING"):
            mock_requests.post.side_effect = Exception("network error")
            notify.notify_admin("件名", "本文")
        assert "管理者通知先が未設定" in caplog.text

    def test_smtp_configured_sends_email(self):
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.test", "SMTP_PORT": "587",
            "SMTP_USER": "user@test", "SMTP_PASSWORD": "pass",
        }, clear=True), patch.object(notify, "smtplib") as mock_smtplib:
            mock_server = MagicMock()
            mock_smtplib.SMTP.return_value.__enter__.return_value = mock_server
            notify.notify_admin("件名", "本文")
        mock_server.login.assert_called_once_with("user@test", "pass")
        mock_server.send_message.assert_called_once()

    def test_smtp_failure_falls_back_without_raising(self, caplog):
        with patch.dict("os.environ", {"SMTP_HOST": "smtp.test"}, clear=True), \
             patch.object(notify, "smtplib") as mock_smtplib, \
             caplog.at_level("WARNING"):
            mock_smtplib.SMTP.side_effect = Exception("connection refused")
            notify.notify_admin("件名", "本文")
        assert "管理者通知先が未設定" in caplog.text

    def test_smtp_password_missing_does_not_attempt_send(self, caplog):
        """パスワードが無いと分かっているのに送りに行かないこと。

        送るとGmailは 530 Authentication Required で必ず拒否する。
        10秒のタイムアウトを待って例外になるだけなので、先に打ち切る。
        2026-08-23にVPSで実際にこの状態だった。
        """
        with patch.dict("os.environ", {"SMTP_HOST": "smtp.test",
                                       "SMTP_USER": "user@test"}, clear=True), \
             patch.object(notify, "smtplib") as mock_smtplib, \
             caplog.at_level("WARNING"):
            notify.notify_admin("件名", "本文")
        mock_smtplib.SMTP.assert_not_called()
        assert "SMTP_PASSWORD が未設定" in caplog.text
        assert "管理者通知先が未設定" in caplog.text

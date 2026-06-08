import pytest
from unittest.mock import patch, MagicMock


def test_send_calls_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_SENDER", "sender@gmail.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "test-password")
    monkeypatch.setenv("EMAIL_RECEIVER", "receiver@gmail.com")

    import importlib
    import delivery.email_sender as em
    importlib.reload(em)

    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        em.send("테스트 리포트 내용")

    mock_smtp.assert_called_once_with("smtp.gmail.com", 587)


def test_send_to_custom_recipient(monkeypatch):
    monkeypatch.setenv("EMAIL_SENDER", "sender@gmail.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "test-password")
    monkeypatch.setenv("EMAIL_RECEIVER", "default@gmail.com")

    import importlib
    import delivery.email_sender as em
    importlib.reload(em)

    mock_server = MagicMock()
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        em.send("내용", to="custom@gmail.com")

    mock_server.sendmail.assert_called_once()
    args = mock_server.sendmail.call_args[0]
    assert args[1] == "custom@gmail.com"

from catchy.core.webhook.models import Webhook


def test_webhook_defaults_preferred_language_to_none() -> None:
    webhook = Webhook(url="https://example.test/webhook")

    assert webhook.preferred_language is None


def test_webhook_accepts_preferred_language() -> None:
    webhook = Webhook(
        url="https://example.test/webhook",
        preferred_language="English",
    )

    assert webhook.preferred_language == "English"

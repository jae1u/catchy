from typing import Any

import pytest


class RecordingRequest:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {
            "authorization": "Bearer sk-test-secret-value",
        }
        self.body = b'{"OPENAI_API_KEY":"sk-test-secret-value"}'


def test_vcr_config_redacts_common_secret_locations(
    vcr_config: dict[str, Any],
) -> None:
    assert "authorization" in vcr_config["filter_headers"]
    assert "x-api-key" in vcr_config["filter_headers"]
    assert "api_key" in vcr_config["filter_query_parameters"]
    assert "token" in vcr_config["filter_post_data_parameters"]


def test_vcr_config_scrubs_secret_environment_values_from_response_body(
    monkeypatch: pytest.MonkeyPatch,
    vcr_config: dict[str, Any],
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    response = {
        "headers": {"authorization": ["Bearer sk-test-secret-value"]},
        "body": {"string": b'{"key":"sk-test-secret-value"}'},
    }

    scrubbed = vcr_config["before_record_response"](response)

    assert scrubbed["headers"]["authorization"] == ["<REDACTED>"]
    assert b"sk-test-secret-value" not in scrubbed["body"]["string"]


def test_vcr_config_scrubs_secret_environment_values_from_request_body(
    monkeypatch: pytest.MonkeyPatch,
    vcr_config: dict[str, Any],
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value")
    request = RecordingRequest()

    scrubbed = vcr_config["before_record_request"](request)

    assert scrubbed.headers["authorization"] == "<REDACTED>"
    assert b"sk-test-secret-value" not in scrubbed.body

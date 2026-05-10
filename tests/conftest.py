from __future__ import annotations

import os
from typing import Any, cast

import pytest

_SENSITIVE_HEADER_NAMES = [
    "authorization",
    "cookie",
    "openai-organization",
    "openai-project",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
]

_SENSITIVE_PARAMETER_NAMES = [
    "access_token",
    "api_key",
    "apikey",
    "client_secret",
    "key",
    "openai_api_key",
    "password",
    "secret",
    "token",
]

_REDACTED = "<REDACTED>"


def _environment_secret_values() -> tuple[str, ...]:
    secret_name_markers = ("API_KEY", "AUTH", "PASSWORD", "SECRET", "TOKEN")
    return tuple(
        value
        for name, value in os.environ.items()
        if value
        and len(value) >= 8
        and any(marker in name.upper() for marker in secret_name_markers)
    )


def _redact_text(text: str) -> str:
    for secret in _environment_secret_values():
        text = text.replace(secret, _REDACTED)
    return text


def _redact_bytes(value: bytes) -> bytes:
    return _redact_text(value.decode("utf-8", errors="replace")).encode()


def _redact_response(response: dict[str, Any]) -> dict[str, Any]:
    raw_headers = response.get("headers")
    if isinstance(raw_headers, dict):
        headers = cast(dict[str, Any], raw_headers)
        for name in list(headers):
            if name.lower() in _SENSITIVE_HEADER_NAMES:
                headers[name] = [_REDACTED]

    raw_body = response.get("body")
    if isinstance(raw_body, dict):
        body = cast(dict[str, Any], raw_body)
        body_string = body.get("string")
        if isinstance(body_string, bytes):
            body["string"] = _redact_bytes(body_string)
        elif isinstance(body_string, str):
            body["string"] = _redact_text(body_string)

    return response


def _redact_request(request: Any) -> Any:
    headers = getattr(request, "headers", None)
    if isinstance(headers, dict):
        headers = cast(dict[str, Any], headers)
        for name in list(headers):
            if name.lower() in _SENSITIVE_HEADER_NAMES:
                headers[name] = _REDACTED

    body = getattr(request, "body", None)
    if isinstance(body, bytes):
        request.body = _redact_bytes(body)
    elif isinstance(body, str):
        request.body = _redact_text(body)

    return request


@pytest.fixture(scope="session")
def vcr_config() -> dict[str, Any]:
    return {
        "before_record_request": _redact_request,
        "before_record_response": _redact_response,
        "decode_compressed_response": True,
        "filter_headers": _SENSITIVE_HEADER_NAMES,
        "filter_post_data_parameters": _SENSITIVE_PARAMETER_NAMES,
        "filter_query_parameters": _SENSITIVE_PARAMETER_NAMES,
    }

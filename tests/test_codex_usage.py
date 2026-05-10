import json
from decimal import Decimal
from pathlib import Path

from catchy.codex import (
    TokenUsage,
    estimate_codex_session_jsonl_cost,
    estimate_cost,
)


def test_estimate_cost_counts_cached_input_at_cached_rate() -> None:
    estimate = estimate_cost(
        "gpt-5",
        TokenUsage(input_tokens=1000, cached_input_tokens=400, output_tokens=200),
    )

    assert estimate.usd == Decimal("0.002800")


def test_estimate_cost_counts_new_nano_models() -> None:
    estimate = estimate_cost(
        "gpt-5.4-nano",
        TokenUsage(input_tokens=1000, cached_input_tokens=400, output_tokens=200),
    )

    assert estimate.usd == Decimal("0.000378")


def test_estimate_cost_uses_input_rate_when_no_cached_discount() -> None:
    estimate = estimate_cost(
        "gpt-5.5-pro-2026-04-23",
        TokenUsage(input_tokens=1000, cached_input_tokens=400, output_tokens=200),
    )

    assert estimate.usd == Decimal("0.066000")


def test_estimate_codex_session_jsonl_cost_uses_last_token_usage(
    tmp_path: Path,
) -> None:
    session_path = tmp_path / "rollout.jsonl"
    session_path.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 25,
                            "output_tokens": 10,
                        },
                    },
                },
            }
        )
        + "\n"
    )

    estimate = estimate_codex_session_jsonl_cost(session_path, model="gpt-5")

    assert estimate.usage.input_tokens == 100
    assert estimate.usage.cached_input_tokens == 25
    assert estimate.usage.output_tokens == 10

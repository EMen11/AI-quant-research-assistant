import pytest

from ai_quant.llm import FakeLLM


def test_fake_llm_is_deterministic_and_counts_calls() -> None:
    client = FakeLLM("known response")

    first = client.complete("first prompt")
    second = client.complete("second prompt")

    assert first == second
    assert first.text == "known response"
    assert first.provider == "fake"
    assert client.call_count == 2


def test_fake_llm_rejects_empty_prompt() -> None:
    client = FakeLLM()

    with pytest.raises(ValueError, match="prompt must not be empty"):
        client.complete("   ")

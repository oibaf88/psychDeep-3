from app.services.context_budget import (
    estimate_tokens,
    fit_context_block,
    fit_recent_messages,
    truncate_text,
)


def test_estimate_tokens_is_deterministic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcdefgh") == 2


def test_recent_history_prefers_latest_turns():
    messages = [
        {"role": "user", "content": "a" * 400},
        {"role": "assistant", "content": "b" * 400},
        {"role": "user", "content": "c" * 400},
        {"role": "assistant", "content": "d" * 400},
    ]
    result = fit_recent_messages(messages, max_tokens=220, max_messages=12)
    assert result.truncated is True
    assert result.messages[-1]["content"].startswith("d")
    assert len(result.messages) <= 1


def test_latest_user_turn_is_never_lost():
    messages = [
        {"role": "assistant", "content": "old context " * 200},
        {"role": "user", "content": "mensaje actual"},
    ]
    result = fit_recent_messages(messages, max_tokens=100)
    assert result.messages[-1] == messages[-1]


def test_context_sections_are_packed_in_priority_order():
    result, used, truncated = fit_context_block(
        ["A" * 40, "B" * 40, "C" * 1000],
        max_tokens=30,
    )
    assert result.startswith("A")
    assert used <= 30
    assert truncated is True


def test_truncation_preserves_edges():
    text = "START " + ("x" * 1000) + " END"
    bounded = truncate_text(text, 20)
    assert bounded.startswith("START")
    assert bounded.endswith("END")

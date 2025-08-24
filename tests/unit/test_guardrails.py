from app.graph.guardrails import (
    sanitize_user_message,
    violates_policy,
    blocked_topic,
    system_prompt,
)


def test_guardrails_sanitize_masks_tokens():
    msg = "my api_key is ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
    cleaned = sanitize_user_message(msg)
    assert "[REDACTED]" in cleaned


def test_guardrails_block_pii_and_topics():
    assert violates_policy("CPF 123.456.789-10")
    assert blocked_topic("This involves weapons")


def test_system_prompt_by_agent():
    k = system_prompt("knowledge")
    assert "Cite sources" in k

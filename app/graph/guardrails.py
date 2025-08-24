from __future__ import annotations

import re
from typing import Dict, Any
from app.graph.helpers import sget, sdict


BLOCKED_PATTERNS = [
    re.compile(r"api[_-]?key", re.I),
    re.compile(r"password|senha", re.I),
    re.compile(r"token", re.I),
    re.compile(r"drop\s+table|delete\s+from", re.I),
    # PII simples
    re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),  # CPF
    re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),  # CNPJ
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),  # cartão de crédito genérico
    re.compile(r"chave pix|pix key", re.I),
    re.compile(r"endereço|address.*?residential", re.I),
]

BLOCKED_TOPICS = {
    "porn",
    "violence",
    "weapons",
    "terrorism",
    "hate speech",
}


def sanitize_user_message(message: str) -> str:
    # Remove obvious tracking params and suspicious long tokens
    msg = re.sub(r"utm_[a-zA-Z0-9_=-]+", "", message)
    msg = re.sub(r"[A-Za-z0-9-_]{24,}", "[REDACTED]", msg)
    return msg.strip()


def violates_policy(text: str) -> bool:
    for pat in BLOCKED_PATTERNS:
        if pat.search(text or ""):
            return True
    return False


def blocked_topic(text: str) -> bool:
    lowered = (text or "").lower()
    return any(topic in lowered for topic in BLOCKED_TOPICS)


def enforce(state: Dict[str, Any]) -> Dict[str, Any]:
    message = sget(state, "message", "")
    cleaned = sanitize_user_message(message)
    if violates_policy(cleaned) or blocked_topic(cleaned):
        base = sdict(state)
        return {
            **base,
            "intent": "end",
            "answer": "I cannot assist with that request.",
        }
    base = sdict(state)
    return {**base, "message": cleaned}


def system_prompt(agent: str, locale: str | None = None) -> str:
    # Guardrails and scope per agent
    base = (
        "Follow policy: do not request or output secrets/PII; avoid politics, violence, or hate;"
        " if insufficient context, say you don't know and suggest contacting human support. "
        "Cite sources at the end as URLs under 'Sources:'."
    )
    if agent == "knowledge":
        return (
            base
            + " Answer strictly about InfinitePay products (Maquininha, Tap to Pay, PDV, Pix, Conta, Boleto, Link, Empréstimo, Cartão)."
            + " Prefer information grounded by the provided context and by graph facts (fees/features/how-to)."
            + " If the context is insufficient, explicitly say you don't know and offer to escalate to human."
            + " Output format: short answer first, then bullet points if needed, then 'Sources:' with up to 5 URLs."
        )
    if agent == "support":
        return (
            base
            + " Keep answers concise, do not expose internal identifiers; offer steps and escalation paths."
            + " If sensitive account actions are required, propose a secure channel and avoid exposing PII."
        )
    if agent == "router":
        return base + " Only classify intent and do not fabricate content."
    return base

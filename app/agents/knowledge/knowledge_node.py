"""
Knowledge Node - Main Orchestrator for Knowledge Agent

Refactored knowledge agent using modular components for maximum performance
and debuggability.
"""

import time
import re
from typing import Dict, Any, List, Optional
import logging

from openai import OpenAI
from langsmith import traceable
from langsmith.wrappers import wrap_openai

from app.settings import settings
from app.tools.web_search import web_search
from app.graph.guardrails import enforce
from app.graph.memory import get_user_context_prompt
from app.agents.knowledge.cache_manager import get_cache_manager
from app.agents.knowledge.retrieval_orchestrator import get_orchestrator
from app.agents.knowledge.context_builder import get_context_builder
from app.agents.knowledge.profiler import get_profiler, profile_step, log_profile

logger = logging.getLogger(__name__)

# Global instances
_cache_manager = get_cache_manager()
_orchestrator = get_orchestrator()
_context_builder = get_context_builder()
_profiler = get_profiler()


def _get_system_prompt(locale: str | None, user_id: str = None) -> str:
    """Build system prompt with locale and user context support."""
    # Determine language instruction based on locale
    if (locale or "").lower().startswith("pt"):
        language_instruction = (
            "Always answer in Portuguese (pt-BR), maintain consistent Portuguese throughout the response. "
            "Use Brazilian Portuguese spelling and expressions."
        )
        locale_prefix = "[pt-BR]"
    else:
        language_instruction = (
            "Always answer in English, do not mix languages."
        )
        locale_prefix = "[en]"

    policy = (
        "Follow policy: do not request or output secrets/PII; avoid politics, violence, or hate; "
        "if insufficient context, say you don't know and suggest contacting human support. "
        "Cite sources at the end as URLs under 'Sources:'. Answer strictly about InfinitePay products "
        "(Maquininha, Tap to Pay, PDV, Pix, Conta, Boleto, Link, Empréstimo, Cartão). Prefer information "
        "grounded by the provided context. If the context is insufficient, explicitly say you don't know. "
        f"{language_instruction} Output format: short answer first, then bullet points if needed, "
        "then 'Sources:' with one most-relevant URL. If you already include a 'Sources:' section, do not add another one."
    )

    # Add user context if available
    if user_id:
        try:
            context_prompt = get_user_context_prompt(user_id)
            if context_prompt:
                policy = context_prompt + " " + policy
        except Exception:
            # Fail gracefully if context retrieval fails
            pass

    return f"{locale_prefix} {policy}"


def _build_llm_client() -> Optional[OpenAI]:
    """Build and cache LLM client."""
    if not settings.openai_api_key:
        return None

    # Try cache first
    client = _cache_manager.get("llm_client", "system")
    if client:
        return client

    # Create new client
    client = OpenAI(api_key=settings.openai_api_key)
    wrapped_client = wrap_openai(client)

    # Cache client
    _cache_manager.set("llm_client", wrapped_client, "system", ttl=3600)  # 1 hour

    return wrapped_client


def _calculate_confidence(has_vector: bool, has_faq: bool) -> float:
    """Calculate confidence score based on available evidence."""
    # Heuristic ensemble confidence using configurable weights
    vw = float(settings.rag_vector_weight or 0.4)

    confidence = (vw if has_vector else 0.0) + (0.3 if has_faq else 0.0)

    return confidence


def _should_escalate_to_custom(confidence: float) -> bool:
    """Determine if query should escalate to custom agent."""
    threshold = settings.handoff_threshold
    if threshold is None:
        threshold = 0.45
    return confidence < threshold


def _extract_sources_from_context(context: str) -> List[str]:
    """Extract source URLs from context."""
    # Simple regex to find URLs in context
    url_pattern = r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)"
    urls = re.findall(url_pattern, context)
    return list(set(urls))  # Deduplicate


@traceable(name="KnowledgeAgent.Modular")
def knowledge_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modular Knowledge Agent - Optimized for performance and debuggability.

    Uses specialized components:
    - CacheManager: Centralized caching
    - AsyncRetrievalOrchestrator: Parallel retrieval execution
    - ContextBuilder: Intelligent context construction
    - LangSmithProfiler: Granular performance tracking
    """
    with profile_step("KnowledgeAgent.Modular", {"state_keys": list(state.keys())}):

        # Input validation and setup
        question = state.get("message", "")
        if not question:
            return {
                "answer": "No question provided",
                "agent": "KnowledgeAgent",
                "grounding": {"mode": "error", "confidence": 0.0},
            }

        total_start = time.perf_counter()
        meta = {"agent": "KnowledgeAgent"}

        # Set profiler metadata
        _profiler.set_metadata("question", question)
        _profiler.set_metadata("agent_version", "modular")

        with profile_step("KnowledgeAgent.Setup"):
            # Apply guardrails
            state = enforce(state)
            question = state.get("message", "")

            # Get embeddings (cached)
            emb_shared = _cache_manager.get("embeddings", "system")
            if not emb_shared:
                from app.rag.embeddings import get_embeddings

                emb_shared = get_embeddings()
                if emb_shared:
                    _cache_manager.set("embeddings", emb_shared, "system", ttl=3600)

        # Query complexity analysis
        with profile_step("KnowledgeAgent.ComplexityAnalysis"):
            query_complexity = len(question.split())
            _profiler.set_metadata("query_complexity", query_complexity)

        # Retrieval orchestration
        with profile_step("KnowledgeAgent.Retrieval"):
            vector_k = int(settings.rag_vector_k or 3)
            if query_complexity > 10:  # Complex queries get more results
                vector_k = min(vector_k + 1, 5)

            # Execute retrieval (parallel or sequential based on complexity)
            vector_result, faq_result = _orchestrator.orchestrate(
                question=question, vector_k=vector_k, emb_shared=emb_shared, enable_vector=True, enable_faq=True
            )

            # Extract results
            vector_docs = vector_result.docs if vector_result.success else []
            faq_docs = faq_result.docs if faq_result.success else []

            # Update metadata with retrieval performance
            meta.update(
                {
                    "vector_ms": str(vector_result.latency_ms),
                    "vector_connect_ms": str(vector_result.connect_ms),
                    "faq_ms": str(faq_result.latency_ms),
                    "faq_connect_ms": str(faq_result.connect_ms),
                    "vector_docs_count": str(len(vector_docs)),
                    "faq_docs_count": str(len(faq_docs)),
                    "retrieval_errors": str({"vector": vector_result.error, "faq": faq_result.error}),
                }
            )

        # Context building
        with profile_step("KnowledgeAgent.ContextBuilding"):
            combined_context, context_metadata = _context_builder.build_context(
                question=question, vector_docs=vector_docs, faq_docs=faq_docs
            )

            # Update metadata with context info
            meta.update(context_metadata)
            meta["combined_context_chars"] = str(len(combined_context))

        # Check if we have enough context
        has_vector = bool(combined_context and "[DOCS]" in combined_context)
        has_faq = bool(combined_context and "[FAQ]" in combined_context)

        if not combined_context.strip():
            # No context available - fallback to web search
            with profile_step("KnowledgeAgent.WebSearchFallback"):
                results = web_search(question, k=3)
                if results:
                    grounding_sources = [{"type": "web", "url": r.get("url") or r.get("source")} for r in results]
                    return {
                        "answer": "Using web search fallback for open-domain queries.",
                        "agent": "KnowledgeAgent",
                        "grounding": {"mode": "web", "sources": grounding_sources, "confidence": 0.3},
                        "meta": {**meta, "fallback_reason": "no_context"},
                    }

                # Final fallback
                return {
                    "answer": "KnowledgeAgent placeholder: RAG will answer grounded by InfinitePay pages.",
                    "agent": "KnowledgeAgent",
                    "grounding": {"mode": "placeholder", "confidence": 0.0},
                    "meta": {**meta, "fallback_reason": "no_web_results"},
                }

        # LLM generation
        with profile_step("KnowledgeAgent.LLMGeneration"):
            client = _build_llm_client()
            if not client:
                return {
                    "answer": "LLM service unavailable",
                    "agent": "KnowledgeAgent",
                    "grounding": {"mode": "error", "confidence": 0.0},
                    "meta": {**meta, "error": "no_llm_client"},
                }

            sys_prompt = _get_system_prompt(state.get("locale"), state.get("user_id"))
            prompt = f"{sys_prompt}\n\nQuestion: {question}\n\nContext:\n{combined_context}"

            # Check LLM cache
            cached_answer = _cache_manager.get_llm_response(prompt)
            if cached_answer:
                final_answer = cached_answer
                llm_latency_ms = 0
                meta["llm_cache_hit"] = True
            else:
                # Generate response
                llm_start = time.perf_counter()

                try:
                    completion = client.chat.completions.create(
                        model=settings.openai_model_knowledge or settings.openai_model_fast or settings.openai_model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        max_tokens=int(getattr(settings, "openai_max_tokens_knowledge", 512) or 512),
                    )
                    final_answer = completion.choices[0].message.content or ""

                    # Retry logic for short responses
                    min_answer_length = getattr(settings, "min_answer_length", 40)
                    if len(final_answer.strip()) < min_answer_length:
                        completion2 = client.chat.completions.create(
                            model=settings.openai_model_knowledge
                            or settings.openai_model_fast
                            or settings.openai_model,
                            messages=[{"role": "user", "content": prompt + "\n\nPlease answer concisely but fully."}],
                            temperature=0.0,
                            max_tokens=int(getattr(settings, "openai_max_tokens_knowledge_retry", 384) or 384),
                        )
                        retry_answer = completion2.choices[0].message.content
                        if retry_answer and len(retry_answer.strip()) > len(final_answer):
                            final_answer = retry_answer

                    llm_latency_ms = (time.perf_counter() - llm_start) * 1000

                    # Cache successful responses
                    if final_answer and len(final_answer.strip()) >= min_answer_length:
                        _cache_manager.set_llm_response(prompt, final_answer)

                except Exception as e:
                    logger.error(f"LLM generation failed: {e}")
                    final_answer = ""
                    llm_latency_ms = (time.perf_counter() - llm_start) * 1000

            meta.update(
                {
                    "llm_latency_ms": str(llm_latency_ms),
                    "llm_model": settings.openai_model or "",
                    "prompt_tokens_estimate": str(int((len(prompt) + len(question)) / 4)),
                }
            )

        # Confidence calculation and decision making
        with profile_step("KnowledgeAgent.DecisionMaking"):
            confidence = _calculate_confidence(has_vector, has_faq)

            # Check for out-of-scope responses
            lower_ans = (final_answer or "").lower()
            out_of_scope_phrases = [
                "i don't know",
                "i do not know",
                "não tenho informações",
                "não sei",
                "fora do escopo",
            ]
            is_oos = any(phrase in lower_ans for phrase in out_of_scope_phrases)

            # Extract and prioritize sources
            source_urls = _extract_sources_from_context(combined_context)
            max_sources = int(getattr(settings, "rag_sources_max", 2) or 2)

            # Prioritize URLs by relevance
            prioritized_urls = source_urls[:max_sources] if source_urls else []

            # Attach sources if relevant and not OOS
            attach_sources = bool(prioritized_urls) and not is_oos and "sources:" not in lower_ans.lower()

            if attach_sources:
                final_answer += "\n\nSources: " + ", ".join(prioritized_urls)

        # Build final response
        with profile_step("KnowledgeAgent.Finalize"):
            mode_value = "vector+faq" if (has_vector or has_faq) else "none"

            grounding = {
                "mode": mode_value,
                "sources": prioritized_urls if attach_sources else [],
                "confidence": confidence,
            }

            total_ms = (time.perf_counter() - total_start) * 1000

            # Update final metadata
            meta.update(
                {
                    "total_ms": str(total_ms),
                    "oos": str(is_oos),
                    "attached_sources": str(attach_sources),
                    "has_vector": str(has_vector),
                    "has_faq": str(has_faq),
                    "confidence": str(confidence),
                    "escalation_decision": str(_should_escalate_to_custom(confidence)),
                }
            )

            # Log performance profile to LangSmith
            log_profile()

            # Preserve original state information
            result = {
                "answer": final_answer,
                "agent": "KnowledgeAgent",
                "grounding": grounding,
                "meta": meta
            }

            # Preserve original fields from input state
            for key in ["user_id", "message", "locale", "intent"]:
                if key in state:
                    result[key] = state[key]

            return result


@traceable(name="KnowledgeNext.Modular")
def knowledge_next(state: Dict[str, Any]) -> str:
    """Decide next step based on confidence - optimized version."""
    grounding = state.get("grounding", {})
    confidence = grounding.get("confidence", 0.0)

    # Check for out-of-scope
    meta = state.get("meta", {})
    if meta.get("oos", False):
        return "personality"

    # Check confidence threshold
    threshold = settings.handoff_threshold
    if threshold is None:
        threshold = 0.45

    decision = "custom" if confidence < threshold else "personality"

    # Update metadata with decision info
    if isinstance(state, dict) and "meta" in state:
        state["meta"].update(
            {"handoff_confidence": confidence, "handoff_threshold": threshold, "handoff_decision": decision}
        )

    return decision

"""
Context Builder - Intelligent Context Construction

Builds optimized context for LLM generation with smart budgeting,
prioritization, and text processing.
"""

import re
import time
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass
import logging

from langchain_core.documents import Document
from app.settings import settings
from app.agents.knowledge.profiler import get_profiler, profile_step

logger = logging.getLogger(__name__)


@dataclass
class ContextSection:
    """Represents a section of context with metadata."""

    name: str
    content: str
    priority: int = 1  # Higher = more important
    source: str = ""
    token_estimate: int = 0
    char_count: int = 0


@dataclass
class ContextBudget:
    """Budget allocation for context sections."""

    total_chars: int
    sections: Dict[str, int]  # section_name -> allocated_chars
    min_allocations: Dict[str, int]  # section_name -> minimum_chars
    dynamic_allocation: bool = True


class ContextBuilder:
    """
    Intelligent context builder for LLM generation.

    Features:
    - Smart text cleaning and preprocessing
    - Dynamic budget allocation
    - Content prioritization
    - Source deduplication
    - Performance optimization
    """

    def __init__(self):
        self._profiler = get_profiler()

        # Configuration
        self._max_context_chars = getattr(settings, "rag_max_context_chars", 3000)
        self._min_faq_chars = getattr(settings, "rag_min_chars_faq", 600)
        self._min_docs_chars = getattr(settings, "rag_min_chars_docs", 800)

        # URL patterns for product matching
        self._product_patterns = {
            "maquininha": ["/maquininha"],
            "maquininha smart": ["/maquininha"],
            "maquininha celular": ["/maquininha-celular", "/tap-to-pay"],
            "tap to pay": ["/tap-to-pay", "/maquininha-celular"],
            "pix": ["/pix"],
            "pdv": ["/pdv"],
            "boleto": ["/boleto"],
            "conta": ["/conta", "/conta-digital"],
            "cartao": ["/cartao"],
            "cartão": ["/cartao"],
            "emprestimo": ["/emprestimo"],
            "empréstimo": ["/emprestimo"],
        }

    def _clean_doc_text(self, text: str) -> str:
        """Clean document text by removing unwanted lines."""
        if not text:
            return ""

        lines = []
        for line in text.splitlines():
            line = line.strip()
            # Skip metadata lines and empty lines
            if (
                line
                and not line.startswith("URL:")
                and not line.startswith("TAGS:")
                and not line.startswith("SOURCE:")
                and not line.startswith("ID:")
                and len(line) > 10
            ):  # Skip very short lines
                lines.append(line)

        return "\n".join(lines)

    def _extract_faq_content(self, doc: Any) -> str:
        """Extract and format FAQ content."""
        if not hasattr(doc, "metadata"):
            return str(doc.page_content or "")

        metadata = getattr(doc, "metadata", {})
        question = metadata.get("question") or ""
        answer = metadata.get("answer") or getattr(doc, "page_content", "") or ""
        url = metadata.get("url") or metadata.get("source", "")

        if question and answer:
            suffix = f" | Source: {url}" if url else ""
            content = f"Q: {question}\nA: {answer}{suffix}"
            # Limit FAQ content to prevent overflow
            return content[:700]
        else:
            content = getattr(doc, "page_content", "") or ""
            suffix = f" | Source: {url}" if url else ""
            return (content + suffix)[:700]

    def _matches_product_patterns(self, url: str, patterns: List[str]) -> bool:
        """Check if URL matches any product patterns."""
        if not url:
            return False

        url_lower = url.lower()
        return any(pattern in url_lower for pattern in patterns)

    def _filter_docs_by_product(self, docs: List[Any], question: str) -> List[Any]:
        """Filter documents based on product relevance."""
        if not docs:
            return docs

        question_lower = question.lower()

        # Find relevant product patterns
        relevant_patterns = []
        for product, patterns in self._product_patterns.items():
            if product in question_lower:
                relevant_patterns.extend(patterns)

        if not relevant_patterns:
            return docs  # No product filtering needed

        # Filter documents that match product patterns
        filtered = []
        for doc in docs:
            if hasattr(doc, "metadata"):
                metadata = getattr(doc, "metadata", {})
                url = str(metadata.get("url") or metadata.get("source") or "")

                if self._matches_product_patterns(url, relevant_patterns):
                    filtered.append(doc)

        # If no documents match, return original list
        return filtered if filtered else docs

    def _calculate_budget_allocation(self, sections: Dict[str, ContextSection]) -> ContextBudget:
        """Calculate optimal budget allocation for sections."""
        total_chars = self._max_context_chars

        # Define minimum allocations
        min_allocations = {"faq": self._min_faq_chars, "docs": self._min_docs_chars}

        # Count present sections
        present_sections = {
            name: section for name, section in sections.items() if section.content and section.content.strip()
        }

        if not present_sections:
            return ContextBudget(total_chars, {}, min_allocations)

        present_count = len(present_sections)

        # Calculate allocations
        allocations = {}

        if present_count == 1:
            # Single section gets all space
            section_name = list(present_sections.keys())[0]
            allocations[section_name] = total_chars
        else:
            # Multiple sections - allocate proportionally
            floor = 0.1  # 10% floor per section
            total_floor = floor * present_count
            remaining = max(0.0, 1.0 - total_floor)

            # Calculate proportions based on content size and priority
            total_weight = sum(section.char_count * section.priority for section in present_sections.values())

            for name, section in present_sections.items():
                if total_weight > 0:
                    proportion = (section.char_count * section.priority) / total_weight
                    allocation = int(total_chars * (floor + proportion * remaining))
                else:
                    allocation = int(total_chars / present_count)

                # Apply minimum allocation
                min_alloc = min_allocations.get(name, 0)
                allocations[name] = max(allocation, min_alloc)

        return ContextBudget(total_chars, allocations, min_allocations)

    def _trim_content_smart(self, content: str, limit: int) -> str:
        """Smartly trim content to fit within character limit."""
        if not content or len(content) <= limit:
            return content

        # Try to trim at sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", content)
        trimmed = ""

        for sentence in sentences:
            if len(trimmed + sentence) <= limit:
                trimmed += sentence
            else:
                break

        # If no sentences found or trimming didn't work, trim at word boundaries
        if not trimmed or len(trimmed) < limit * 0.8:
            words = content.split()
            trimmed = ""

            for word in words:
                if len(trimmed + word) <= limit:
                    trimmed += word + " "
                else:
                    break

        return trimmed.strip()

    def _deduplicate_sources(self, urls: List[str]) -> List[str]:
        """Remove duplicate URLs while preserving order."""
        seen = set()
        deduplicated = []

        for url in urls:
            if url and url not in seen:
                seen.add(url)
                deduplicated.append(url)

        return deduplicated

    def build_context(
        self, question: str, vector_docs: Optional[List[Any]] = None, faq_docs: Optional[List[Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build optimized context for LLM generation.

        Returns:
            Tuple of (context_string, metadata_dict)
        """
        with profile_step("ContextBuilder.build_context", {"question": question}):

            vector_docs = vector_docs or []
            faq_docs = faq_docs or []

            # Create context sections
            sections = {}

            # Process vector documents
            if vector_docs:
                filtered_docs = self._filter_docs_by_product(vector_docs, question)

                vector_texts = []
                for doc in filtered_docs:
                    cleaned = self._clean_doc_text(getattr(doc, "page_content", "") or "")
                    if cleaned:
                        vector_texts.append(cleaned)

                vector_content = "\n\n".join(vector_texts)
                if vector_content.strip():
                    sections["docs"] = ContextSection(
                        name="docs", content=vector_content, priority=2, char_count=len(vector_content)  # High priority
                    )

            # Process FAQ documents
            if faq_docs:
                faq_texts = []
                for doc in faq_docs:
                    faq_text = self._extract_faq_content(doc)
                    if faq_text:
                        faq_texts.append(faq_text)

                faq_content = "\n\n".join(faq_texts)
                if faq_content.strip():
                    sections["faq"] = ContextSection(
                        name="faq", content=faq_content, priority=3, char_count=len(faq_content)  # Highest priority
                    )

            # Calculate budget allocation
            budget = self._calculate_budget_allocation(sections)

            # Apply allocations and trim content
            context_parts = []
            section_lengths = {}

            for section_name, section in sections.items():
                allocated_chars = budget.sections.get(section_name, 0)
                if allocated_chars > 0:
                    trimmed_content = self._trim_content_smart(section.content, allocated_chars)
                    if trimmed_content:
                        context_parts.append(f"[{section.name.upper()}]\n{trimmed_content}")
                        section_lengths[section_name] = len(trimmed_content)

            # Combine context
            final_context = "\n\n".join(context_parts).strip()

            # Collect source URLs for metadata
            source_urls = []
            for doc in vector_docs or []:
                if hasattr(doc, "metadata"):
                    metadata = getattr(doc, "metadata", {})
                    url = metadata.get("url") or metadata.get("source")
                    if url:
                        source_urls.append(str(url))

            # Deduplicate URLs
            source_urls = self._deduplicate_sources(source_urls)

            # Build metadata
            metadata = {
                "context_char_count": len(final_context),
                "context_sections": list(sections.keys()),
                "section_lengths": section_lengths,
                "budget_allocation": budget.sections,
                "source_urls": source_urls,
                "source_count": len(source_urls),
                "vector_docs_filtered": len(vector_docs) != len(self._filter_docs_by_product(vector_docs, question)),
                "faq_docs_count": len(faq_docs),
            }

            return final_context, metadata


# Global instance
_context_builder = ContextBuilder()


def get_context_builder() -> ContextBuilder:
    """Get the global context builder instance."""
    return _context_builder


def build_context(
    question: str, vector_docs: Optional[List[Any]] = None, faq_docs: Optional[List[Any]] = None
) -> Tuple[str, Dict[str, Any]]:
    """Convenience function for context building."""
    return _context_builder.build_context(question, vector_docs, faq_docs)

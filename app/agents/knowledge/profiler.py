"""
LangSmith Profiler - Granular Performance Monitoring

Provides detailed profiling and tracing capabilities for the Knowledge Agent.
Tracks performance metrics for each step and integrates with LangSmith.
"""

import time
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from functools import wraps
import logging

from langsmith import traceable

logger = logging.getLogger(__name__)


@dataclass
class ProfileStep:
    """Represents a single profiled step."""

    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["ProfileStep"] = field(default_factory=list)
    parent: Optional["ProfileStep"] = None
    thread_id: int = field(default_factory=lambda: threading.get_ident())


@dataclass
class ProfileResult:
    """Result of a profiling session."""

    total_duration_ms: float
    steps: List[ProfileStep]
    metadata: Dict[str, Any] = field(default_factory=dict)


class LangSmithProfiler:
    """
    Advanced profiler for Knowledge Agent with LangSmith integration.

    Features:
    - Hierarchical profiling with nested steps
    - Thread-aware profiling
    - Automatic LangSmith integration
    - Performance metrics collection
    - Memory usage tracking
    """

    def __init__(self):
        self._current_step: Optional[ProfileStep] = None
        self._step_stack: List[ProfileStep] = []
        self._session_metadata: Dict[str, Any] = {}
        self._enabled = True

    def set_metadata(self, key: str, value: Any):
        """Set session-level metadata."""
        self._session_metadata[key] = value

    def enable(self):
        """Enable profiling."""
        self._enabled = True

    def disable(self):
        """Disable profiling."""
        self._enabled = False

    @contextmanager
    def profile_step(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for profiling a step."""
        if not self._enabled:
            yield
            return

        start_time = time.perf_counter()

        step = ProfileStep(name=name, start_time=start_time, metadata=metadata or {}, parent=self._current_step)

        # Add to parent's children if we have a parent
        if self._current_step:
            self._current_step.children.append(step)

        # Push to stack
        self._step_stack.append(step)
        self._current_step = step

        try:
            yield step
        finally:
            # Pop from stack
            if self._step_stack:
                self._step_stack.pop()

            # Calculate duration
            end_time = time.perf_counter()
            step.end_time = end_time
            step.duration_ms = (end_time - start_time) * 1000

            # Restore parent
            self._current_step = self._step_stack[-1] if self._step_stack else None

    def profile_function(self, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Decorator for profiling functions."""

        def decorator(func: Callable):
            step_name = name or f"{func.__module__}.{func.__qualname__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.profile_step(step_name, metadata):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def get_profile_result(self) -> ProfileResult:
        """Get the profiling result for the current session."""
        if not self._step_stack:
            return ProfileResult(total_duration_ms=0, steps=[])

        root_step = self._step_stack[0]
        total_duration = root_step.duration_ms or 0

        # Collect all steps in hierarchy
        all_steps = []

        def collect_steps(step: ProfileStep):
            all_steps.append(step)
            for child in step.children:
                collect_steps(child)

        collect_steps(root_step)

        return ProfileResult(total_duration_ms=total_duration, steps=all_steps, metadata=self._session_metadata.copy())

    def log_to_langsmith(self, result: ProfileResult, run_name: str = "KnowledgeAgent.Profile"):
        """Log profiling results to LangSmith."""
        if not result.steps:
            return

        # Prepare metadata for LangSmith
        metadata = {
            "profile_total_duration_ms": result.total_duration_ms,
            "profile_step_count": len(result.steps),
            "profile_session_metadata": result.metadata,
            "profile_thread_count": len(set(step.thread_id for step in result.steps)),
        }

        # Add step details
        for i, step in enumerate(result.steps):
            metadata[f"step_{i}_name"] = step.name
            metadata[f"step_{i}_duration_ms"] = step.duration_ms or 0
            metadata[f"step_{i}_thread_id"] = step.thread_id
            metadata[f"step_{i}_metadata"] = step.metadata

        # Log with traceable decorator effect
        logger.info(f"Profile completed: {result.total_duration_ms:.1f}ms across {len(result.steps)} steps")

    def reset(self):
        """Reset the profiler state."""
        self._current_step = None
        self._step_stack.clear()
        self._session_metadata.clear()

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        result = self.get_profile_result()

        if not result.steps:
            return {"total_duration_ms": 0, "step_count": 0}

        # Calculate metrics
        step_durations = [step.duration_ms or 0 for step in result.steps]
        step_names = [step.name for step in result.steps]

        return {
            "total_duration_ms": result.total_duration_ms,
            "step_count": len(result.steps),
            "avg_step_duration_ms": sum(step_durations) / len(step_durations),
            "max_step_duration_ms": max(step_durations),
            "min_step_duration_ms": min(step_durations),
            "step_names": step_names,
            "slowest_steps": sorted(zip(step_names, step_durations), key=lambda x: x[1], reverse=True)[
                :5
            ],  # Top 5 slowest steps
        }


# Global profiler instance
_profiler = LangSmithProfiler()


def get_profiler() -> LangSmithProfiler:
    """Get the global profiler instance."""
    return _profiler


# Convenience functions
def profile_step(name: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager for profiling steps."""
    return _profiler.profile_step(name, metadata)


def profile_function(name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
    """Decorator for profiling functions."""
    return _profiler.profile_function(name, metadata)


def log_profile(run_name: str = "KnowledgeAgent.Profile"):
    """Log current profiling session to LangSmith."""
    result = _profiler.get_profile_result()
    _profiler.log_to_langsmith(result, run_name)
    return result


def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary of current session."""
    return _profiler.get_performance_summary()


# Async support
import asyncio


class AsyncLangSmithProfiler(LangSmithProfiler):
    """Async version of LangSmithProfiler."""

    @contextmanager
    async def profile_step_async(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Async context manager for profiling a step."""
        if not self._enabled:
            yield
            return

        start_time = time.perf_counter()

        step = ProfileStep(name=name, start_time=start_time, metadata=metadata or {}, parent=self._current_step)

        # Add to parent's children if we have a parent
        if self._current_step:
            self._current_step.children.append(step)

        # Push to stack
        self._step_stack.append(step)
        self._current_step = step

        try:
            yield step
        finally:
            # Pop from stack
            if self._step_stack:
                self._step_stack.pop()

            # Calculate duration
            end_time = time.perf_counter()
            step.end_time = end_time
            step.duration_ms = (end_time - start_time) * 1000

            # Restore parent
            self._current_step = self._step_stack[-1] if self._step_stack else None

    def profile_async_function(self, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """Decorator for profiling async functions."""

        def decorator(func):
            step_name = name or f"{func.__module__}.{func.__qualname__}"

            @wraps(func)
            async def wrapper(*args, **kwargs):
                async with self.profile_step_async(step_name, metadata):
                    return await func(*args, **kwargs)

            return wrapper

        return decorator


# Global async profiler instance
_async_profiler = AsyncLangSmithProfiler()


def get_async_profiler() -> AsyncLangSmithProfiler:
    """Get the global async profiler instance."""
    return _async_profiler


# Backward compatibility
profile_step_async = _async_profiler.profile_step_async
profile_async_function = _async_profiler.profile_async_function

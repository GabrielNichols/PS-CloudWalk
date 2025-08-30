from typing import Any, Dict, Optional, List
from pydantic import BaseModel
from langchain_core.messages import BaseMessage


class AppState(BaseModel):
    # Core user input
    user_id: str
    message: str
    locale: Optional[str] = None

    # Conversation memory - essential for LangGraph message persistence
    messages: List[BaseMessage] = []

    # Intelligent routing fields
    intent: Optional[str] = None
    current_route: Optional[str] = None  # Current active agent
    routing_history: List[str] = []  # Track agent routing history
    routing_confidence: Optional[float] = None
    routing_reason: Optional[str] = None

    # Agent workflow data
    retrieval: Optional[Dict[str, Any]] = None
    answer: Optional[str] = None
    agent: Optional[str] = None
    grounding: Optional[Dict[str, Any]] = None

    # Memory and context
    user_context: Optional[Dict[str, Any]] = None
    conversation_context: Optional[Dict[str, Any]] = None

    # Metadata and tracing
    meta: Dict[str, Any] = {}
    trace: Dict[str, Any] = {}

    # Escalation and human-in-the-loop
    needs_human_escalation: bool = False
    escalation_reason: Optional[str] = None
    human_response: Optional[str] = None

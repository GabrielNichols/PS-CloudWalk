from typing import Any, Dict, Optional
from pydantic import BaseModel


class AppState(BaseModel):
    user_id: str
    message: str
    locale: Optional[str] = None
    intent: Optional[str] = None
    retrieval: Optional[Dict[str, Any]] = None
    answer: Optional[str] = None
    agent: Optional[str] = None
    grounding: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = {}
    trace: Dict[str, Any] = {}

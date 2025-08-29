from typing import Optional, Dict, Any
from app.settings import settings
from langgraph.checkpoint.memory import MemorySaver

# Global instances
_checkpointer: Optional[object] = None
_memory_store: Optional[object] = None
_postgres_available = False

# Try to import PostgresStore conditionally
try:
    from langgraph.store.postgres import PostgresStore
    _postgres_available = True
except ImportError:
    _postgres_available = False
    PostgresStore = None

def get_langgraph_checkpointer():
    """
    Get the LangGraph checkpointer for conversation state persistence.
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    if not settings.database_url:
        _checkpointer = MemorySaver()
        return _checkpointer

    # Use in-memory for development (Windows compatibility)
    _checkpointer = MemorySaver()
    return _checkpointer

def get_memory_store():
    """
    Get the memory store for long-term memory storage.
    Uses PostgresStore if available, otherwise falls back to in-memory.
    """
    global _memory_store

    if _memory_store is not None:
        return _memory_store

    if not settings.database_url:
        # Fallback to in-memory if no database configured
        _memory_store = {}
        return _memory_store

    if not _postgres_available or PostgresStore is None:
        # Fallback to in-memory if PostgreSQL dependencies not available
        print("⚠️  PostgresStore not available, using in-memory storage")
        _memory_store = {}
        return _memory_store

    try:
        # Initialize PostgresStore for long-term memory
        _memory_store = PostgresStore.from_conn_string(settings.database_url)
        _memory_store.setup()  # Create tables if they don't exist
        return _memory_store
    except Exception as e:
        print(f"⚠️  Failed to initialize PostgresStore: {e}, using in-memory storage")
        _memory_store = {}
        return _memory_store

def store_user_memory(user_id: str, namespace: str, key: str, value: Dict[str, Any]):
    """
    Store user-specific memory in the memory store.

    Args:
        user_id: User identifier
        namespace: Memory category (e.g., "preferences", "history", "context")
        key: Memory key (e.g., "language", "last_topic", "interaction_count")
        value: Memory data to store
    """
    try:
        store = get_memory_store()

        if isinstance(store, dict):
            # In-memory storage
            memory_key = f"{user_id}:{namespace}:{key}"
            store[memory_key] = value
        else:
            # PostgresStore
            memory_key = (user_id, namespace)
            store.put(memory_key, key, value)
    except Exception as e:
        print(f"Warning: Failed to store user memory: {e}")

def retrieve_user_memory(user_id: str, namespace: str, key: str = None) -> Dict[str, Any]:
    """
    Retrieve user-specific memory from the memory store.

    Args:
        user_id: User identifier
        namespace: Memory category
        key: Specific memory key (if None, returns all memories in namespace)

    Returns:
        Memory data or empty dict if not found
    """
    try:
        store = get_memory_store()

        if isinstance(store, dict):
            # In-memory storage
            if key:
                memory_key = f"{user_id}:{namespace}:{key}"
                return store.get(memory_key, {})
            else:
                # Get all memories for this user and namespace
                prefix = f"{user_id}:{namespace}:"
                memories = {}
                for mem_key, value in store.items():
                    if mem_key.startswith(prefix):
                        actual_key = mem_key[len(prefix):]
                        memories[actual_key] = value
                return memories
        else:
            # PostgresStore
            memory_key = (user_id, namespace)

            if key:
                # Get specific memory item
                memories = store.search(memory_key)
                for memory in memories:
                    if memory.key == key:
                        return memory.value
                return {}
            else:
                # Get all memories in namespace
                memories = store.search(memory_key)
                return {memory.key: memory.value for memory in memories}
    except Exception as e:
        print(f"Warning: Failed to retrieve user memory: {e}")
        return {}

def update_user_context(user_id: str, message: str, agent: str, response: str = None):
    """
    Update user contextual memory based on interaction.

    Args:
        user_id: User identifier
        message: User message
        agent: Agent that handled the request
        response: Agent response (optional)
    """
    try:
        # Get current context
        context = retrieve_user_memory(user_id, "context", "current") or {
            "interaction_count": 0,
            "last_agent": None,
            "last_topic": None,
            "preferred_language": "en",
            "topics_discussed": [],
            "last_interaction": None
        }

        # Update interaction count
        context["interaction_count"] += 1
        context["last_agent"] = agent
        context["last_interaction"] = message

        # Let AI detect language and topics naturally from context
        # No hardcoded keyword matching - AI handles everything

        # Store updated context
        store_user_memory(user_id, "context", "current", context)

    except Exception as e:
        print(f"Warning: Failed to update user context: {e}")

def get_user_context_prompt(user_id: str) -> str:
    """
    Generate contextual prompt enhancement based on user history.

    Args:
        user_id: User identifier

    Returns:
        Contextual prompt string to enhance LLM responses
    """
    try:
        context = retrieve_user_memory(user_id, "context", "current") or {}

        enhancements = []

        # Language preference
        if context.get("preferred_language") == "pt-BR":
            enhancements.append("User prefers Portuguese (pt-BR) responses.")

        # Returning user
        if context.get("interaction_count", 0) > 3:
            enhancements.append("This is a returning user with multiple interactions.")

        # Recent topics
        if context.get("last_topic"):
            enhancements.append(f"Recent conversation topic: {context['last_topic']}")

        # Topics discussed
        if context.get("topics_discussed"):
            topics_str = ", ".join(context["topics_discussed"][:3])  # Limit to 3 topics
            enhancements.append(f"Previously discussed topics: {topics_str}")

        return " ".join(enhancements) if enhancements else ""

    except Exception as e:
        print(f"Warning: Failed to generate context prompt: {e}")
        return ""

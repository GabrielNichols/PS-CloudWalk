from typing import Optional, Dict, Any, List
from app.settings import settings
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
import uuid

# Global instances
_checkpointer: Optional[object] = None
_memory_store: Optional[object] = None
_postgres_available = False
_postgres_saver_available = False

# Try to import Postgres components conditionally
try:
    from langgraph.store.postgres import PostgresStore
    _postgres_available = True
except ImportError:
    _postgres_available = False
    PostgresStore = None

try:
    from langgraph.checkpoint.postgres import PostgresSaver
    _postgres_saver_available = True
except ImportError:
    _postgres_saver_available = False
    PostgresSaver = None

def _ensure_sslmode(uri: str) -> str:
    """
    Ensure SSL mode is set for Supabase compatibility.
    """
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

    parsed = urlparse(uri)
    qs = parse_qs(parsed.query)
    qs.setdefault("sslmode", ["require"])
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

def get_langgraph_checkpointer():
    """
    Get the LangGraph checkpointer for conversation state persistence.
    Uses PostgresSaver if available, otherwise falls back to MemorySaver.
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    db_url = getattr(settings, "database_url", "")
    
    # Skip PostgreSQL attempts if DATABASE_URL is empty or not set
    if not db_url or db_url.strip() == "":
        print("🔄 Using MemorySaver (no DATABASE_URL configured)")
        _checkpointer = MemorySaver()
        return _checkpointer

    # Try to use PostgresSaver for production persistence
    if _postgres_saver_available and PostgresSaver:
        try:
            print("🔄 Attempting to initialize PostgresSaver for checkpoints...")
            conn_string = _ensure_sslmode(db_url)

            # Try different initialization approaches
            postgres_checkpointer = None

            # First, try with connection pool if available
            try:
                from psycopg_pool import ConnectionPool
                print("🔄 Using ConnectionPool for better connection management...")
                pool = ConnectionPool(
                    conninfo=conn_string,
                    min_size=1,
                    max_size=10,
                    kwargs={"autocommit": True, "row_factory": dict}
                )
                postgres_checkpointer = PostgresSaver(pool)
            except ImportError:
                print("⚠️ psycopg_pool not available, trying direct connection...")
                # Fallback to direct connection
                postgres_checkpointer = PostgresSaver.from_conn_string(conn_string)

            # Handle different API versions - some return context managers
            if hasattr(postgres_checkpointer, '__enter__'):
                # It's a context manager, enter it to get the actual object
                _checkpointer = postgres_checkpointer.__enter__()
            else:
                # It's already the actual object
                _checkpointer = postgres_checkpointer

            # Try to setup tables (some versions may not have this method)
            if hasattr(_checkpointer, 'setup'):
                _checkpointer.setup()  # Create tables if they don't exist

            print("✅ PostgresSaver initialized successfully - checkpoints will persist!")
            return _checkpointer
        except Exception as e:
            print(f"⚠️ PostgresSaver failed ({e}) - falling back to MemorySaver")
            print("   💡 This is normal in development or if PostgreSQL dependencies are missing")
            print("   💡 Check that 'langgraph-checkpoint-postgres' is installed")

    # Fallback to in-memory for development or when Postgres is not available
    print("🔄 Using MemorySaver (development mode or Postgres not available)")
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

    db_url = getattr(settings, "database_url", "")
    
    # Skip PostgreSQL attempts if DATABASE_URL is empty or not set
    if not db_url or db_url.strip() == "":
        print("🔄 Using in-memory storage for long-term memory (no DATABASE_URL configured)")
        _memory_store = {}
        return _memory_store

    if not _postgres_available or PostgresStore is None:
        print("⚠️ PostgresStore not available - using in-memory storage for long-term memory")
        print("   💡 Install 'langgraph' with PostgreSQL support for persistent long-term memory")
        _memory_store = {}
        return _memory_store

    try:
        print("🔄 Attempting to initialize PostgresStore for long-term memory...")
        conn_string = _ensure_sslmode(db_url)

        # Try different initialization approaches
        postgres_memory_store = None

        # First, try with connection pool if available
        try:
            from psycopg_pool import ConnectionPool
            print("🔄 Using ConnectionPool for memory store...")
            pool = ConnectionPool(
                conninfo=conn_string,
                min_size=1,
                max_size=5,
                kwargs={"autocommit": True, "row_factory": dict}
            )
            postgres_memory_store = PostgresStore(pool)
        except ImportError:
            print("⚠️ psycopg_pool not available for memory store, trying direct connection...")
            # Fallback to direct connection
            postgres_memory_store = PostgresStore.from_conn_string(conn_string)

        # Handle different API versions - some return context managers
        if hasattr(postgres_memory_store, '__enter__'):
            # It's a context manager, enter it to get the actual object
            _memory_store = postgres_memory_store.__enter__()
        else:
            # It's already the actual object
            _memory_store = postgres_memory_store

        # Try to setup tables (some versions may not have this method)
        if hasattr(_memory_store, 'setup'):
            _memory_store.setup()  # Create tables if they don't exist

        print("✅ PostgresStore initialized successfully - long-term memory will persist!")
        return _memory_store
    except Exception as e:
        print(f"⚠️ Failed to initialize PostgresStore: {e}")
        print("   💡 Using in-memory storage for long-term memory")
        print("   💡 This is normal in development or if PostgreSQL is not accessible")
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
            # PostgresStore - try to handle connection issues
            memory_key = (user_id, namespace)
            try:
                store.put(memory_key, key, value)
            except Exception as conn_error:
                if "connection is closed" in str(conn_error):
                    print("⚠️ PostgresStore connection closed, reinitializing...")
                    # Force reinitialization of memory store
                    global _memory_store
                    _memory_store = None
                    store = get_memory_store()
                    if not isinstance(store, dict):
                        store.put(memory_key, key, value)
                        print("✅ Memory stored after reconnection")
                    else:
                        print("⚠️ Fell back to in-memory storage")
                else:
                    raise conn_error
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
            # PostgresStore - try to handle connection issues
            memory_key = (user_id, namespace)
            try:
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
            except Exception as conn_error:
                if "connection is closed" in str(conn_error):
                    print("⚠️ PostgresStore connection closed during retrieval, reinitializing...")
                    # Force reinitialization of memory store
                    global _memory_store
                    _memory_store = None
                    store = get_memory_store()
                    if isinstance(store, dict):
                        print("⚠️ Fell back to in-memory storage")
                        return {}
                    else:
                        # Try again with new connection
                        try:
                            if key:
                                memories = store.search(memory_key)
                                for memory in memories:
                                    if memory.key == key:
                                        return memory.value
                                return {}
                            else:
                                memories = store.search(memory_key)
                                return {memory.key: memory.value for memory in memories}
                        except Exception:
                            return {}
                else:
                    raise conn_error
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

        # Let the AI naturally remember conversation context
        # No hardcoded patterns - LangGraph handles conversation memory

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

        # User's name (most important context)
        if context.get("user_name"):
            enhancements.append(f"User's name is {context['user_name']}.")

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


# ========== LONG-TERM MEMORY FUNCTIONS (Following LangGraph Docs) ==========

def store_user_memory(user_id: str, namespace: str, key: str, value: Dict[str, Any]):
    """
    Store user-specific memory in the memory store.
    Following LangGraph documentation pattern.

    Args:
        user_id: User identifier
        namespace: Memory category (e.g., "memories", "preferences")
        key: Memory key (e.g., "conversation", "personal_info")
        value: Memory data to store
    """
    try:
        store = get_memory_store()

        if isinstance(store, dict):
            # In-memory storage fallback
            memory_key = f"{user_id}:{namespace}:{key}"
            store[memory_key] = value
        else:
            # PostgresStore - use proper namespace tuple
            memory_namespace = (user_id, namespace)
            store.put(memory_namespace, key, value)
            print(f"🧠 Stored long-term memory: {key} for user {user_id}")
    except Exception as e:
        print(f"Warning: Failed to store user memory: {e}")


def retrieve_user_memory(user_id: str, namespace: str, key: str = None) -> Dict[str, Any]:
    """
    Retrieve user-specific memory from the memory store.
    Following LangGraph documentation pattern.

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
            # In-memory storage fallback
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
            # PostgresStore - use proper namespace tuple
            memory_namespace = (user_id, namespace)

            if key:
                # Get specific memory item
                try:
                    memories = store.search(memory_namespace)
                    for memory in memories:
                        if memory.key == key:
                            return memory.value
                    return {}
                except Exception:
                    return {}
            else:
                # Get all memories in namespace
                try:
                    memories = store.search(memory_namespace)
                    return {memory.key: memory.value for memory in memories}
                except Exception:
                    return {}

    except Exception as e:
        print(f"Warning: Failed to retrieve user memory: {e}")
        return {}


def search_user_memories(user_id: str, query: str, namespace: str = "memories", limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search user memories using semantic search.
    Following LangGraph documentation pattern.

    Args:
        user_id: User identifier
        query: Search query for semantic search
        namespace: Memory namespace to search
        limit: Maximum number of results to return

    Returns:
        List of relevant memories
    """
    try:
        store = get_memory_store()

        if isinstance(store, dict):
            # In-memory fallback - simple keyword search
            memory_namespace = (user_id, namespace)
            all_memories = retrieve_user_memory(user_id, namespace)
            results = []

            query_lower = query.lower()
            for key, value in all_memories.items():
                if isinstance(value, dict) and "data" in value:
                    data = str(value["data"]).lower()
                    if any(word in data for word in query_lower.split()):
                        results.append({"key": key, "value": value})

            return results[:limit]
        else:
            # PostgresStore - use semantic search
            memory_namespace = (user_id, namespace)
            try:
                memories = store.search(memory_namespace, query=query, limit=limit)
                return [{"key": memory.key, "value": memory.value} for memory in memories]
            except Exception:
                # Fallback to regular search if semantic search fails
                return list(retrieve_user_memory(user_id, namespace).values())[:limit]

    except Exception as e:
        print(f"Warning: Failed to search user memories: {e}")
        return []


def store_conversation_memory(user_id: str, user_message: str, ai_response: str):
    """
    Store conversation memory for future reference.
    Following LangGraph documentation pattern.
    """
    try:
        # Create unique key for this conversation exchange
        memory_key = f"conv_{uuid.uuid4().hex[:8]}"

        # Store the conversation exchange
        memory_data = {
            "user_message": user_message,
            "ai_response": ai_response,
            "timestamp": "recent",
            "type": "conversation"
        }

        store_user_memory(user_id, "memories", memory_key, {"data": str(memory_data)})

    except Exception as e:
        print(f"Warning: Failed to store conversation memory: {e}")


def get_user_memory_context(user_id: str, query: str = None) -> str:
    """
    Get user memory context for use in prompts.
    Following LangGraph documentation pattern.

    Args:
        user_id: User identifier
        query: Optional search query for semantic search

    Returns:
        Formatted memory context string
    """
    try:
        if query:
            memories = search_user_memories(user_id, query, limit=3)
        else:
            memories = list(retrieve_user_memory(user_id, "memories").values())[:3]

        if not memories:
            return ""

        context_parts = []
        for memory in memories:
            if isinstance(memory, dict) and "data" in memory:
                context_parts.append(str(memory["data"]))

        if context_parts:
            return f"Previous conversations: {'; '.join(context_parts[:3])}"
        else:
            return ""

    except Exception as e:
        print(f"Warning: Failed to get user memory context: {e}")
        return ""


def update_user_context(user_id: str, message: str, agent: str, response: str = None):
    """
    Update user contextual memory based on interaction.
    Centralized in memory.py as per requirements.
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

        # Store updated context
        store_user_memory(user_id, "context", "current", context)

        # Also store conversation memory
        if response:
            store_conversation_memory(user_id, message, response)

    except Exception as e:
        print(f"Warning: Failed to update user context: {e}")


# ========== MEMORY NODE FUNCTIONS FOR LANGGRAPH ==========

def retrieve_memory_node(state, config: RunnableConfig, *, store: BaseStore = None):
    """
    Node to retrieve relevant memories for the current conversation.
    Following LangGraph documentation pattern.
    """
    if not store or not state.get("user_id"):
        return {}

    user_id = state["user_id"]
    current_message = state.get("message", "")

    # Get relevant memories
    memories = search_user_memories(user_id, current_message, "memories", limit=3)

    if memories:
        memory_texts = []
        for memory in memories:
            if isinstance(memory, dict) and "value" in memory:
                value = memory["value"]
                if isinstance(value, dict) and "data" in value:
                    memory_texts.append(str(value["data"]))

        if memory_texts:
            memory_context = f"Previous relevant conversations: {'; '.join(memory_texts)}"
            print(f"🧠 Retrieved {len(memories)} relevant memories for user {user_id}")
            return {"user_context": {"long_term_memory": memory_context}}

    return {"user_context": {"long_term_memory": ""}}


def store_memory_node(state, config: RunnableConfig, *, store: BaseStore = None):
    """
    Node to store new memories from the conversation.
    Following LangGraph documentation pattern.
    """
    if not store or not state.get("user_id"):
        return {}

    user_id = state["user_id"]
    user_message = state.get("message", "").strip()

    # Only store if it's a meaningful message
    if len(user_message) > 5:
        # Store conversation memory
        store_conversation_memory(user_id, user_message, state.get("answer", ""))

    return {}

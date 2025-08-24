from typing import Optional

from app.settings import settings
from langgraph.checkpoint.memory import MemorySaver

# Prefer async Postgres saver per docs; fall back to sync variant
PGSaver: object | None = None
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver as PGSaver
except Exception:  # noqa: BLE001
    try:
        from langgraph.checkpoint.postgres import PostgresSaver as PGSaver
    except Exception:  # noqa: BLE001
        PGSaver = None


_checkpointer: Optional[object] = None


def get_checkpointer():
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    # Prefer Postgres (Supabase). No SQLite fallback as requested.
    if PGSaver is not None and settings.database_url:
        try:
            _checkpointer = PGSaver(settings.database_url)
            return _checkpointer
        except Exception:  # noqa: BLE001
            _checkpointer = None
    # In-memory fallback if Postgres is unavailable or DATABASE_URL missing
    _checkpointer = MemorySaver()
    return _checkpointer

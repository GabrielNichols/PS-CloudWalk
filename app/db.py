import asyncio
import json
from typing import Any, Dict, List, Optional

import asyncpg

from app.settings import settings


def _normalize_dsn(url: str) -> str:
    # Supabase usually requires SSL; ensure sslmode=require if not present
    if "supabase.co" in url and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}sslmode=require"
    return url

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL not configured for Supabase/Postgres")
    _pool = await asyncpg.create_pool(dsn=_normalize_dsn(settings.database_url), min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp BIGINT NOT NULL,
                sources JSONB,
                metadata JSONB
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session_time ON messages(session_id, timestamp);
            """
        )


async def save_message(msg: Dict[str, Any]) -> None:
    """Save a message with deduplication and validation"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Ensure sources and metadata are JSON serializable
        sources = msg.get("sources", [])
        if not isinstance(sources, (list, dict)):
            sources = []

        metadata = msg.get("metadata", {})
        if not isinstance(metadata, (dict, list)):
            metadata = {}

        # Generate a content hash to detect duplicates
        content_hash = hash(f"{msg.get('session_id')}_{msg.get('content')}_{msg.get('role')}")

        # Check for existing message with same content in last 30 seconds (to avoid rapid duplicates)
        thirty_seconds_ago = int(msg.get("timestamp", 0)) - 30000

        existing = await conn.fetchval("""
            SELECT id FROM messages
            WHERE session_id = $1
            AND content = $2
            AND role = $3
            AND timestamp > $4
            AND timestamp <= $5
        """,
        msg.get("session_id"),
        msg.get("content"),
        msg.get("role"),
        thirty_seconds_ago,
        int(msg.get("timestamp", 0)) + 1000  # Allow 1 second tolerance
        )

        if existing:
            return

        await conn.execute(
            """
            INSERT INTO messages (id, session_id, role, content, timestamp, sources, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET
                session_id = EXCLUDED.session_id,
                role = EXCLUDED.role,
                content = EXCLUDED.content,
                timestamp = EXCLUDED.timestamp,
                sources = EXCLUDED.sources,
                metadata = EXCLUDED.metadata
            """,
            msg.get("id"),
            msg.get("session_id"),
            msg.get("role"),
            msg.get("content"),
            int(msg.get("timestamp")),
            json.dumps(sources) if sources else '[]',
            json.dumps(metadata) if metadata else '{}',
        )


async def replace_conversation(session_id: str, messages: List[Dict[str, Any]]) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM messages WHERE session_id = $1", session_id)
            if messages:
                # Prepare data with JSON serializable fields
                prepared_messages = []
                for m in messages:
                    sources = m.get("sources", [])
                    if not isinstance(sources, (list, dict)):
                        sources = []

                    metadata = m.get("metadata", {})
                    if not isinstance(metadata, (dict, list)):
                        metadata = {}

                    prepared_messages.append((
                        m.get("id"),
                        session_id,
                        m.get("role"),
                        m.get("content"),
                        int(m.get("timestamp")),
                        json.dumps(sources) if sources else '[]',
                        json.dumps(metadata) if metadata else '{}',
                    ))

                await conn.executemany(
                    """
                    INSERT INTO messages (id, session_id, role, content, timestamp, sources, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    prepared_messages,
                )


async def get_conversation(session_id: str) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, session_id, role, content, timestamp, sources, metadata FROM messages WHERE session_id = $1 ORDER BY timestamp ASC",
            session_id,
        )
        return [dict(r) for r in rows]


async def delete_conversation(session_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM messages WHERE session_id = $1", session_id)


async def list_sessions() -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT session_id,
                   COUNT(*) AS message_count,
                   MAX(timestamp) AS last_ts
            FROM messages
            GROUP BY session_id
            ORDER BY last_ts DESC
            """
        )
        sessions: List[Dict[str, Any]] = []
        for r in rows:
            sid = r["session_id"]
            last_ts = int(r["last_ts"]) if r["last_ts"] is not None else 0
            # get first user message as title and last message content
            first_row = await conn.fetchrow(
                "SELECT content FROM messages WHERE session_id=$1 AND role='user' ORDER BY timestamp ASC LIMIT 1",
                sid,
            )
            last_row = await conn.fetchrow(
                "SELECT content FROM messages WHERE session_id=$1 ORDER BY timestamp DESC LIMIT 1",
                sid,
            )
            title = (first_row["content"][:30] + "...") if first_row and first_row["content"] else "New Chat"
            last_msg = last_row["content"] if last_row else ""
            sessions.append(
                {
                    "id": sid,
                    "title": title,
                    "lastMessage": last_msg,
                    "timestamp": last_ts,
                    "messageCount": int(r["message_count"] or 0),
                }
            )
        return sessions

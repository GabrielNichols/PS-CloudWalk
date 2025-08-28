import asyncio
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
    pool = await get_pool()
    async with pool.acquire() as conn:
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
            msg.get("sources"),
            msg.get("metadata"),
        )


async def replace_conversation(session_id: str, messages: List[Dict[str, Any]]) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM messages WHERE session_id = $1", session_id)
            if messages:
                await conn.executemany(
                    """
                    INSERT INTO messages (id, session_id, role, content, timestamp, sources, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    [
                        (
                            m.get("id"),
                            session_id,
                            m.get("role"),
                            m.get("content"),
                            int(m.get("timestamp")),
                            m.get("sources"),
                            m.get("metadata"),
                        )
                        for m in messages
                    ],
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

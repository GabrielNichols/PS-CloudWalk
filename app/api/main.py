from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from app.graph.builder import build_graph
from app.graph.memory import (
    get_langgraph_checkpointer,
    update_user_context,
    get_user_context_prompt
)
from app.settings import settings
import time
import json
import asyncio
from typing import Any, Dict, List
from fastapi.middleware.cors import CORSMiddleware
from app import db as dbmod


class MessagePayload(BaseModel):
    message: str
    user_id: str
    locale: str | None = None


app = FastAPI()
# CORS (useful for local dev: CRA on :3000 calling API on :8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*" if settings.app_env != "production" else "https://*"] ,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)
# Initialize the async checkpointer
checkpointer = None
graph = None

@app.on_event("startup")
async def initialize_checkpointer():
    global checkpointer, graph

    print("🚀 FastAPI Startup - Initializing Knowledge Agent...")

    # Initialize warm-up system (includes embeddings pre-loading)
    print("🔥 Initializing Knowledge Agent warm-up system...")
    try:
        from app.agents.knowledge.warmup import initialize_warmup_system
        initialize_warmup_system()
    except Exception as e:
        print(f"⚠️ Failed to initialize warm-up system: {e}")
        # Fallback to basic embeddings pre-loading
        print("🔄 Pre-loading embeddings as fallback...")
        try:
            from app.rag.embeddings import get_embeddings
            from app.agents.knowledge.cache_manager import get_cache_manager

            embeddings = get_embeddings()
            if embeddings:
                cache_manager = get_cache_manager()
                cache_manager.set("embeddings", embeddings, "system", ttl=3600)
                print("✅ Embeddings pre-loaded and cached")
            else:
                print("⚠️ Embeddings not available - RAG will be limited")
        except Exception as e2:
            print(f"⚠️ Failed to pre-load embeddings: {e2}")

    # Initialize graph with checkpointer and long-term memory store
    try:
        print("🔄 Initializing graph, checkpointer and long-term memory store...")
        checkpointer = get_langgraph_checkpointer()

        # Initialize long-term memory store
        store = None
        try:
            from app.graph.memory import get_memory_store
            store = get_memory_store()
            if store and not isinstance(store, dict):  # Check if it's not in-memory fallback
                print("✅ Long-term memory store initialized")
            else:
                print("⚠️ Using in-memory fallback for long-term memory")
        except Exception as e:
            print(f"⚠️ Long-term memory store initialization failed: {e}")

        graph = build_graph(checkpointer=checkpointer, store=store)
        print("✅ Graph initialized successfully with memory capabilities")
    except Exception as e:
        print(f"⚠️ Graph initialization failed, using fallback: {e}")
        # Fallback to in-memory
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        graph = build_graph(checkpointer=checkpointer)
        print("✅ Graph initialized with fallback checkpointer")

    print("🎯 FastAPI Startup Complete - Knowledge Agent Ready!")


_rate_limiter_store: dict[str, list[float]] = {}

# Simple in-memory conversation store (dev fallback).
# For production, persist via Supabase/Postgres.
_conversations: Dict[str, List[Dict[str, Any]]] = {}


# Database initialization is now handled by the checkpointer setup


def _allow_request(user_id: str) -> bool:
    window = 30.0
    limit = max(1, int((settings.rate_limit_per_minute or 60) / 2))
    now = time.time()
    arr = _rate_limiter_store.setdefault(user_id, [])
    # prune
    while arr and now - arr[0] > window:
        arr.pop(0)
    if len(arr) >= limit:
        return False
    arr.append(now)
    return True


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/warmup/status")
async def warmup_status():
    """Get current warm-up status."""
    try:
        from app.agents.knowledge.warmup import check_warmup_status
        status = check_warmup_status()
        return {
            "ok": True,
            "warmup": status
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "warmup": {
                "status": "error",
                "message": "Unable to check warm-up status"
            }
        }


@app.get("/version")
async def version():
    return {"version": "0.1.0"}


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return response


@app.post("/api/v1/message")
async def message_endpoint(payload: MessagePayload, request: Request):
    global graph, checkpointer

    # Ensure graph is initialized
    if graph is None:
        raise HTTPException(status_code=503, detail="Service initializing, please try again")

    try:
        # basic per-user rate limiting
        client_host = request.client.host if request.client is not None else "anonymous"
        user_key = payload.user_id or client_host
        if not _allow_request(user_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # Persist user message first (best-effort)
        try:
            user_msg = {
                "id": f"msg_{int(time.time()*1000)}_u",
                "session_id": payload.user_id or client_host,
                "content": payload.message,
                "role": "user",
                "timestamp": int(time.time() * 1000),
                "sources": [],
                "metadata": {"agent": "user"},
            }
            if settings.database_url:
                await dbmod.save_message(user_msg)
            else:
                _conversations.setdefault(user_msg["session_id"], []).append({k: v for k, v in user_msg.items() if k != "session_id"})
        except Exception:
            pass
        inputs = {
            "user_id": payload.user_id,
            "message": payload.message,
            "locale": payload.locale,
        }
        result = graph.invoke(
            inputs,
            config={
                "configurable": {
                    "thread_id": payload.user_id,
                }
            },
        )
        # Normalize result to dict
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = result
        else:  # best-effort
            try:
                data = dict(result)
            except Exception:
                data = {"answer": str(result)}

        # Post-process: ensure KnowledgeAgent has structured sources when meta.source_urls exist
        try:
            if isinstance(data, dict) and data.get("agent") == "KnowledgeAgent":
                grounding = data.get("grounding") or {}
                has_sources = bool(isinstance(grounding, dict) and grounding.get("sources"))
                # Avoid adding sources for obvious out-of-scope apologetic answers
                ans = (data.get("answer") or "").lower()
                is_oos = any(p in ans for p in [
                    "i don't know", "i do not know", "não tenho informações", "não sei", "fora do escopo"
                ])
                if not has_sources and not is_oos:
                    meta = data.get("meta") or {}
                    fallback_urls = meta.get("source_urls") or []
                    if fallback_urls:
                        grounding.setdefault("mode", (grounding or {}).get("mode", "vector+faq"))
                        grounding["sources"] = [{"url": u} for u in fallback_urls]
                        data["grounding"] = grounding
        except Exception:
            pass

        # Personality node must set `answer` and `agent`
        # Save assistant message to conversation store (best-effort)
        try:
            session_id = payload.user_id
            assistant_answer = data.get("answer", "")
            agent_used = data.get("agent", "Unknown")
            route_trace = data.get("routing_history") or []

            # Update user contextual memory
            try:
                update_user_context(
                    user_id=session_id,
                    message=payload.message,
                    agent=agent_used,
                    response=assistant_answer
                )
            except Exception as e:
                print(f"Warning: Failed to update user context: {e}")

            msg = {
                "id": f"msg_{int(time.time()*1000)}",
                "session_id": session_id,
                "content": assistant_answer,
                "role": "assistant",
                "timestamp": int(time.time() * 1000),
                # Only knowledge agent should include web sources; others keep empty
                "sources": (data.get("grounding") or {}).get("sources") if agent_used == "KnowledgeAgent" else [],
                "metadata": {
                    "agent": data.get("agent", "Unknown"),
                    **(data.get("meta") or {}),
                    "route_trace": route_trace,
                },
            }
            if settings.database_url:
                try:
                    await dbmod.save_message(msg)

                except Exception as e:
                    print(f"Error saving message or updating context: {e}")
            else:
                _conversations.setdefault(session_id, []).append({k: v for k, v in msg.items() if k != "session_id"})
        except Exception as e:
            print(f"Error in message persistence: {e}")

        return {
            "ok": True,
            "agent": data.get("agent", "Unknown"),
            "answer": data.get("answer", ""),
            "grounding": data.get("grounding"),
            "meta": {
                **(data.get("meta", {})),
                "route_trace": data.get("routing_history") or [],
            },
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


async def generate_streaming_response(payload: MessagePayload, request: Request):
    """Generate streaming response using Server-Sent Events with lightweight progress events."""
    global graph, checkpointer

    # Ensure graph is initialized
    if graph is None:
        yield f"data: {json.dumps({'error': 'Service initializing, please try again'})}\n\n"
        return

    # Rate limiting
    client_host = request.client.host if request.client is not None else "anonymous"
    user_key = payload.user_id or client_host
    if not _allow_request(user_key):
        yield f"data: {json.dumps({'error': 'Rate limit exceeded'})}\n\n"
        return

    inputs = {
        "user_id": payload.user_id,
        "message": payload.message,
        "locale": payload.locale,
    }

    # Start: routing progress
    yield f"data: {json.dumps({'type': 'progress', 'stage': 'routing'})}\n\n"

    try:
        # Execute graph in a background thread so we can emit periodic progress
        invoke_task = asyncio.to_thread(
            graph.invoke,
            inputs,
            {
                "configurable": {"thread_id": payload.user_id},
            },
        )

        # While the task is running, send "working" pings every second
        while True:
            if invoke_task.done():
                break
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'retrieval'})}\n\n"
            await asyncio.sleep(1.0)

        # Get result
        result = await invoke_task

        # Normalize result
        if hasattr(result, "model_dump"):
            data = result.model_dump()
        elif isinstance(result, dict):
            data = result
        else:
            try:
                data = dict(result)
            except Exception:
                data = {"answer": str(result)}

        # Ensure KnowledgeAgent has sources: prefer meta.source_urls, else parse from answer
        try:
            agent_used = data.get("agent", "Unknown")
            grounding = data.get("grounding") or {}
            has_sources = (
                isinstance(grounding, dict)
                and isinstance(grounding.get("sources"), list)
                and len(grounding.get("sources")) > 0
            )
            if agent_used == "KnowledgeAgent" and not has_sources:
                # Avoid adding sources for clearly out-of-scope apologies
                meta = data.get("meta") or {}
                oos_flag = meta.get("oos")
                is_oos = str(oos_flag).lower() == "true"
                if not is_oos:
                    # 1) prefer explicit source_urls captured during retrieval
                    src_urls = meta.get("source_urls") or []
                    if src_urls:
                        grounding.setdefault("mode", grounding.get("mode", "vector+faq"))
                        grounding["sources"] = [{"url": u} for u in src_urls]
                        data["grounding"] = grounding
                    else:
                        # 2) fallback: extract URLs from the answer text
                        import re
                        urls = re.findall(r"https?://[^\s)]+", data.get("answer", ""))
                        if urls:
                            grounding.setdefault("sources", [])
                            seen = set()
                            for u in urls:
                                if u not in seen:
                                    grounding["sources"].append({"url": u})
                                    seen.add(u)
                            data["grounding"] = grounding
        except Exception:
            pass

        # If retrieval metrics exist, advertise them before streaming content
        try:
            if data.get('agent') == 'KnowledgeAgent':
                meta = data.get('meta') or {}
                if meta.get('vector_docs_count') or meta.get('faq_docs_count'):
                    yield f"data: {json.dumps({'type': 'progress', 'stage': 'retrieval', 'vector': meta.get('vector_docs_count'), 'faq': meta.get('faq_docs_count')})}\n\n"
        except Exception:
            pass

        # Stream answer chunks
        answer = data.get("answer", "")
        route_trace = data.get("routing_history") or []
        words = answer.split()

        yield f"data: {json.dumps({'type': 'start', 'agent': data.get('agent', 'Unknown')})}\n\n"
        current_text = ""
        for i, word in enumerate(words):
            current_text += word + " "
            chunk_data = {
                'type': 'chunk',
                'content': word + " ",
                'full_content': current_text,
                'is_complete': i == len(words) - 1
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
            await asyncio.sleep(0.05)

        completion_data = {
            'type': 'complete',
            'agent': data.get('agent', 'Unknown'),
            'answer': answer,
            'grounding': data.get('grounding'),
            'meta': {
                **(data.get('meta', {})),
                'route_trace': route_trace,
            },
        }
        yield f"data: {json.dumps(completion_data)}\n\n"

        # Persist assistant message (best-effort)
        try:
            session_id = payload.user_id or client_host
            msg = {
                "id": f"msg_{int(time.time()*1000)}",
                "session_id": session_id,
                "content": answer,
                "role": "assistant",
                "timestamp": int(time.time() * 1000),
                "sources": (data.get("grounding") or {}).get("sources") if (data.get('agent') == "KnowledgeAgent") else [],
                "metadata": {
                    "agent": data.get("agent", "Unknown"),
                    **(data.get("meta") or {}),
                    "route_trace": route_trace,
                },
            }
            if settings.database_url:
                await dbmod.save_message(msg)
            else:
                _conversations.setdefault(session_id, []).append({k: v for k, v in msg.items() if k != "session_id"})
        except Exception:
            pass

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@app.post("/api/v1/message/stream")
async def message_stream_endpoint(payload: MessagePayload, request: Request):
    """Streaming endpoint using Server-Sent Events"""
    return StreamingResponse(
        generate_streaming_response(payload, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "cache-control",
        }
    )


# -------- Conversation/session endpoints (dev fallback) --------
class ConversationSavePayload(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]


@app.get("/api/v1/conversation/{session_id}")
async def get_conversation(session_id: str):
    if settings.database_url:
        try:
            rows = await dbmod.get_conversation(session_id)
            # Rows have session_id; frontend ignores it per-message, ok
            return {"session_id": session_id, "messages": rows}
        except Exception:
            pass
    messages = _conversations.get(session_id, [])
    return {"session_id": session_id, "messages": messages}


@app.post("/api/v1/conversation")
async def save_conversation(payload: ConversationSavePayload):
    if settings.database_url:
        try:
            await dbmod.replace_conversation(payload.session_id, payload.messages or [])
            return {"ok": True}
        except Exception:
            pass
    _conversations[payload.session_id] = payload.messages or []
    return {"ok": True}


@app.delete("/api/v1/conversation/{session_id}")
async def delete_conversation(session_id: str):
    if settings.database_url:
        try:
            await dbmod.delete_conversation(session_id)
            return {"ok": True}
        except Exception:
            pass
    _conversations.pop(session_id, None)
    return {"ok": True}


@app.get("/api/v1/sessions")
async def list_sessions():
    if settings.database_url:
        try:
            return await dbmod.list_sessions()
        except Exception:
            pass
    sessions = []
    for sid, msgs in _conversations.items():
        last = msgs[-1] if msgs else None
        sessions.append({
            "id": sid,
            "title": (msgs[0]["content"][:30] + "...") if msgs else "New Chat",
            "lastMessage": (last or {}).get("content", ""),
            "timestamp": (last or {}).get("timestamp", int(time.time() * 1000)),
            "messageCount": len(msgs),
        })
    sessions.sort(key=lambda s: s["timestamp"], reverse=True)
    return sessions

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from app.graph.builder import build_graph
from app.graph.memory import get_checkpointer
from app.settings import settings
import time
import json
import asyncio


class MessagePayload(BaseModel):
    message: str
    user_id: str
    locale: str | None = None


app = FastAPI()
try:
    checkpointer = get_checkpointer()
except Exception:
    checkpointer = None
graph = build_graph(checkpointer=checkpointer)


_rate_limiter_store: dict[str, list[float]] = {}


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
    try:
        # basic per-user rate limiting
        client_host = request.client.host if request.client is not None else "anonymous"
        user_key = payload.user_id or client_host
        if not _allow_request(user_key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
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
        # Personality node must set `answer` and `agent`
        return {
            "ok": True,
            "agent": data.get("agent", "Unknown"),
            "answer": data.get("answer", ""),
            "grounding": data.get("grounding"),
            "meta": data.get("meta", {}),
        }
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))


async def generate_streaming_response(payload: MessagePayload, request: Request):
    """Generate streaming response using Server-Sent Events"""
    try:
        # basic per-user rate limiting
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

        # Get the full response first (we'll stream it in chunks)
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
        else:
            try:
                data = dict(result)
            except Exception:
                data = {"answer": str(result)}

        # Stream the response in chunks
        answer = data.get("answer", "")
        words = answer.split()

        # Send start event
        yield f"data: {json.dumps({'type': 'start', 'agent': data.get('agent', 'Unknown')})}\n\n"

        # Stream answer word by word
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
            await asyncio.sleep(0.05)  # Small delay to simulate streaming

        # Send completion event with full metadata
        completion_data = {
            'type': 'complete',
            'agent': data.get('agent', 'Unknown'),
            'answer': answer,
            'grounding': data.get('grounding'),
            'meta': data.get('meta', {}),
        }
        yield f"data: {json.dumps(completion_data)}\n\n"

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

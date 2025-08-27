from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.graph.builder import build_graph
from app.graph.memory import get_checkpointer
from app.settings import settings
import time


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

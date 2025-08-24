from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.graph.builder import build_graph
from app.graph.memory import get_checkpointer


class MessagePayload(BaseModel):
    message: str
    user_id: str
    locale: str | None = None


app = FastAPI(title="Agent Swarm API", version="0.1.0")
checkpointer = get_checkpointer()
graph = build_graph(checkpointer=checkpointer)


@app.post("/api/v1/message")
async def message_endpoint(payload: MessagePayload):
    try:
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

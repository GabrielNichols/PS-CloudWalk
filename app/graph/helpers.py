from typing import Any, Dict


def sget(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def sget_meta(state: Any) -> dict:
    meta = sget(state, "meta", {})
    return meta if isinstance(meta, dict) else {}


def sdict(state: Any) -> Dict[str, Any]:
    if hasattr(state, "model_dump"):
        try:
            return state.model_dump()
        except Exception:
            pass
    if hasattr(state, "dict"):
        try:
            return state.dict()
        except Exception:
            pass
    if isinstance(state, dict):
        return state
    try:
        return dict(state)
    except Exception:
        return {}

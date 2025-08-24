import os
from dotenv import load_dotenv


def _strip_quotes(val: str | None) -> str | None:
    if not val:
        return val
    v = val.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


def pytest_configure(config):
    # Load .env so LangSmith sees API key/project even in test env
    load_dotenv(override=False)
    # Enable LangSmith tracing in tests if key is present
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    # Respect user's LANGSMITH_API_KEY in environment
    # Optionally set project name for grouping test runs
    if os.environ.get("LANGSMITH_PROJECT") is None:
        os.environ["LANGSMITH_PROJECT"] = "ps-cloudwalk-tests"
    # Sanitize potential quoted values from .env
    for key in [
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
        "LANGSMITH_ENDPOINT",
        "LANGCHAIN_ENDPOINT",
    ]:
        val = os.environ.get(key)
        sval = _strip_quotes(val)
        if sval is not None:
            os.environ[key] = sval

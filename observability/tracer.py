import time
import functools
from langfuse import Langfuse, observe
from config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

_client = Langfuse(
    public_key=LANGFUSE_PUBLIC_KEY,
    secret_key=LANGFUSE_SECRET_KEY,
    host=LANGFUSE_HOST
)


def trace_llm_call(fn):
    """
    Decorator — wrap any function that calls the LLM.
    Records: function name, inputs, output preview, latency.
    Usage: @trace_llm_call above run_agent()
    """
    @observe(name=fn.__name__, as_type="agent", capture_input=False, capture_output=False)
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.time()
        trace_input = {
            "user_query": kwargs.get("user_query", ""),
            "model_name": kwargs.get("model_name", "default"),
            "session_id": kwargs.get("session_id", ""),
            "project_id": kwargs.get("project_id", ""),
        }
        _client.update_current_span(input=trace_input)
        try:
            result = fn(*args, **kwargs)
            latency_ms = int((time.time() - start) * 1000)
            _client.update_current_span(
                output=result[:500],
                metadata={"latency_ms": latency_ms}
            )
            print(f"[Langfuse] Traced: {fn.__name__} ({latency_ms}ms)")
            return result
        except Exception as e:
            _client.update_current_span(level="ERROR", status_message=str(e))
            raise
    return wrapper


def trace_tool_call(tool_name: str, query: str, result: str, latency_ms: int):
    """Log a single tool execution as a Langfuse event."""
    _client.create_event(
        name=f"tool:{tool_name}",
        input={"query": query},
        output={
            "result_chars": len(result),
            "preview": result[:200]
        },
        metadata={"latency_ms": latency_ms}
    )


def flush():
    """Call at end of session — ensures all events are sent to Langfuse."""
    _client.flush()
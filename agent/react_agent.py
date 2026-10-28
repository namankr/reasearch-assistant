import time
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception
from observability.tracer import trace_tool_call, trace_llm_call
from memory.vector_store import VectorMemory
from security.sanitiser import sanitise
from config import GEMINI_API_KEY, LLM_MODEL, MAX_ITERATIONS, MAX_TOOL_OUTPUT_CHARS
from tools.web_search import web_search, WEB_SEARCH_TOOL
from agent.prompts import SYSTEM_PROMPT

_client = genai.Client(api_key=GEMINI_API_KEY)

_memory: dict[str, VectorMemory] = {}

TOOL_REGISTRY = {
    "web_search": web_search
}


def get_memory(project_id: str) -> VectorMemory:
    if project_id not in _memory:
        _memory[project_id] = VectorMemory(project_id)
    return _memory[project_id]


def _build_gemini_tools():
    """Default tools — web search only. Used by research agent."""
    decl = types.FunctionDeclaration(
        name=WEB_SEARCH_TOOL["name"],
        description=WEB_SEARCH_TOOL["description"],
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(
                    type=types.Type.STRING,
                    description="The search query — be specific and concise."
                )
            },
            required=["query"]
        )
    )
    return [types.Tool(function_declarations=[decl])]


def _to_gemini_history(history: list[dict]) -> list:
    gemini_msgs = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        gemini_msgs.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )
    return gemini_msgs


def is_rate_limit_error(exception) -> bool:
    return isinstance(exception, genai_errors.APIError) and exception.code == 429


# ── Module-level retry wrapper ────────────────────────────────────────────
@retry(
    wait=wait_random_exponential(min=2, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception(is_rate_limit_error),
    reraise=True
)
def _send_with_retry(chat, message):
    return chat.send_message(message)


# ── Main agent function ───────────────────────────────────────────────────
@trace_llm_call
def run_agent(
    user_query: str,
    history: list[dict],
    session_id: str,
    project_id: str,
    model_name: str = None,
    system_prompt_override: str = None,
    tool_registry_override: dict = None,
    gemini_tools_override: list = None,     # ← NEW: pass travel tool declarations
) -> str:
    memory       = get_memory(project_id)
    past_context = memory.retrieve(user_query, session_id)
    active_model = model_name or LLM_MODEL

    active_prompt   = system_prompt_override or SYSTEM_PROMPT
    active_registry = tool_registry_override or TOOL_REGISTRY
    active_tools    = gemini_tools_override  or _build_gemini_tools()  # ← NEW

    gemini_history = _to_gemini_history(history)

    if past_context:
        gemini_history = [
            types.Content(role="user", parts=[types.Part(
                text=f"[Relevant past findings]\n{past_context}")]),
            types.Content(role="model", parts=[types.Part(
                text="Understood, I'll use these past findings to inform my answer.")])
        ] + gemini_history

    chat = _client.chats.create(
        model=active_model,
        config=types.GenerateContentConfig(
            system_instruction=active_prompt,   # ← Bug 1 fixed: one key only
            tools=active_tools                  # ← Bug 3 fixed: uses override
        ),
        history=gemini_history
    )

    print(f"\n[Agent] Thinking about: {user_query}")

    message = user_query
    for iteration in range(MAX_ITERATIONS):

        try:
            response = _send_with_retry(chat, message)
        except genai_errors.APIError as e:
            if e.code == 429:
                print("[Agent] Gemini quota exceeded after max retries.")
                return ("Quota exceeded (HTTP 429). Please wait for the rate "
                        "limit to reset or enable billing, then try again.")
            print(f"[Agent] Gemini API error: {e}")
            return f"Model request failed: {e.message or str(e)}"
        except Exception as e:
            print(f"[Agent] Unexpected error: {e}")
            return f"Agent operation failed: {str(e)}"

        candidate = response.candidates[0]
        part       = candidate.content.parts[0]

        if getattr(part, "function_call", None) and part.function_call.name:
            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)
            print(f"[Agent] Tool call: {fn_name}({fn_args})")

            t0 = time.time()
            if fn_name in active_registry:        # ← Bug 2 fixed: active_registry
                tool_result = active_registry[fn_name](**fn_args)
            else:
                tool_result = f"Unknown tool: {fn_name}"
                print(f"[Agent] ⚠ Tool '{fn_name}' not in registry. "
                      f"Available: {list(active_registry.keys())}")

            trace_tool_call(
                tool_name=fn_name,
                query=str(fn_args),
                result=tool_result,
                latency_ms=int((time.time() - t0) * 1000)
            )

            clean_result = sanitise(tool_result, source=fn_args.get("query", fn_name))
            if len(clean_result) > MAX_TOOL_OUTPUT_CHARS:
                clean_result = clean_result[:MAX_TOOL_OUTPUT_CHARS] + "\n[truncated]"
            memory.store(clean_result, source=fn_name, session_id=session_id)

            print(f"[Agent] Tool returned {len(clean_result)} chars "
                  f"({int((time.time()-t0)*1000)}ms)")

            message = types.Part(
                function_response=types.FunctionResponse(
                    name=fn_name,
                    response={"result": clean_result}
                )
            )

        else:
            print(f"[Agent] Done after {iteration + 1} iteration(s)")
            return part.text

        time.sleep(1)

    return "Max iterations reached without a final answer."
# to do : Step 6: agent/react_agent.py — the ReAct loop

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.generativeai import protos
from memory.vector_store import VectorMemory
from security.sanitiser import sanitise

from config import GEMINI_API_KEY, LLM_MODEL, MAX_ITERATIONS
from tools.web_search import web_search, WEB_SEARCH_TOOL
from agent.prompts import SYSTEM_PROMPT

genai.configure(api_key=GEMINI_API_KEY)

# Initialise memory once (module level)
_memory: dict[str, VectorMemory] = {}

# ── Tool registry — add more tools here later ─────────────────────────────
TOOL_REGISTRY ={
    "web_search":web_search
}


# ── get Memory ─────────────────────────────
def get_memory(project_id: str)-> VectorMemory:
    if project_id not in _memory:
        _memory[project_id] = VectorMemory(project_id)
    return _memory[project_id]



# ── Build Gemini tool schema ──────────────────────────────────────────────
def _build_gemini_tools():
    decl = FunctionDeclaration(
        name = WEB_SEARCH_TOOL["name"],
        description=WEB_SEARCH_TOOL["description"],
        parameters=WEB_SEARCH_TOOL["parameters"]
    )
    return [Tool(function_declarations=[decl])]

# ── History format conversion ─────────────────────────────────────────────
def _to_gemini_history(history: list[dict]) -> list:
    """Convert [{role, content}] → Gemini Content objects."""
    gemini_msgs = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        gemini_msgs.append({"role": role, "parts": [msg["content"]]})
    return gemini_msgs

# ── Main agent function ───────────────────────────────────────────────────
def run_agent(user_query: str, history:list[dict], session_id: str, project_id: str) -> str:
    # """
    # Run one turn of the ReAct loop.

    # history  — list of {role, content} dicts from ChatService
    # returns  — the agent's final text answer
    # """
    """
    Phase 2 ReAct loop — now with:
    - RAG memory retrieval before each LLM call
    - Tool result sanitisation (injection defence)
    - Tool results stored in vector memory
    """
    memory = get_memory(project_id)
# ── Retrieve relevant past findings ───────────────────────────────────
    past_context = memory.retrieve(user_query, session_id)

    model = genai.GenerativeModel(
        model_name=LLM_MODEL,
        system_instruction=SYSTEM_PROMPT,
        tools= _build_gemini_tools()
    )

    gemini_history = _to_gemini_history(history)

    if past_context:
        # Prepend retrieved memory as context
        gemini_history = [{
            "role": "user",
            "parts": [f"[Relevant past findings]\n{past_context}"]
        }, {
            "role": "model",
            "parts": ["Understood, I'll use these past findings to inform my answer."]
        }] + gemini_history       

    chat = model.start_chat(history=gemini_history)
    
    print(f"\n[Agent] Thinking about: {user_query}")

# ── ReAct loop ────────────────────────────────────────────────────────
    message = user_query
    for iteration in range(MAX_ITERATIONS):
        response = chat.send_message(message)
        candidate = response.candidates[0]
        part = candidate.content.parts[0]

        # ── Tool call? Execute it and feed result back ────────────────────
        if hasattr(part, "function_call") and part.function_call.name:
            fn_name = part.function_call.name
            fn_args = dict(part.function_call.args)

            print(f"[Agent] Calling tool: {fn_name}({fn_args})")

            if fn_name in TOOL_REGISTRY:
                tool_result = TOOL_REGISTRY[fn_name](**fn_args)
            else:
                tool_result = f"Unknown tool: {fn_name}"
            
            # ── Sanitise before it enters the prompt ──────────────────────
            clean_result = sanitise(tool_result, source=fn_args.get("query", fn_name))

            # ── Store in vector memory for future retrieval ───────────────
            memory.store(clean_result, source=fn_name, session_id=session_id)

            print(f"[Agent] Tool returned {len(clean_result)} chars")

            # Feed the tool result back as a function response
            message = [
                protos.Part(
                    function_response=protos.FunctionResponse(
                        name=fn_name,
                        response={"result": tool_result}
                    )
                )
            ]

        # ── Text response → we're done ────────────────────────────────────
        else:
            final_answer = part.text
            print(f"[Agent] Done after {iteration + 1} iteration(s)")
            return final_answer

    return "Max iterations reached without a final answer."
# to do : Step 6: agent/react_agent.py — the ReAct loop

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from google.generativeai import protos

from config import GEMINI_API_KEY, LLM_MODEL, MAX_ITERATIONS
from tools.web_search import web_search, WEB_SEARCH_TOOL
from agent.prompts import SYSTEM_PROMPT

genai.configure(api_key=GEMINI_API_KEY)

# ── Tool registry — add more tools here later ─────────────────────────────
TOOL_REGISTRY ={
    "web_search":web_search
}

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
def run_agent(user_query: str, history:list[dict]) -> str:
    """
    Run one turn of the ReAct loop.

    history  — list of {role, content} dicts from ChatService
    returns  — the agent's final text answer
    """
    model = genai.GenerativeModel(
        model_name=LLM_MODEL,
        system_instruction=SYSTEM_PROMPT,
        tools= _build_gemini_tools()
    )

    gemini_history = _to_gemini_history(history)

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

            print(f"[Agent] Tool returned {len(tool_result)} chars")

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
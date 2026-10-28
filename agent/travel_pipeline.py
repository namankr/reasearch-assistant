from agent.booker import run_booker, handle_approval, EDIT_PREFIX
from agent.coordinator import run_coordinator
from chat.service import ChatService

PROJECT_ID = "travel_agent"


def handle_user_message(user_input: str, session_id: str) -> str:
    """
    Coordinator -> Booker pipeline with the approval gate in front.
    The service-layer status decides routing, not the LLM.
    """
    chat = ChatService(project_id=PROJECT_ID, session_id=session_id)
    is_revision = False

    if chat.get_status() == "awaiting_approval":
        response = handle_approval(user_input, session_id)
        if not response.startswith(EDIT_PREFIX):
            return response
        edit = response[len(EDIT_PREFIX):]
        original = chat.get_context("original_request") or ""
        is_revision = True
        request = f"{original}\nRevision requested by user: {edit}".strip()
    else:
        chat.set_status("running")
        request = user_input

    original_request = request
    plan = run_coordinator(request, session_id, is_revision=is_revision)
    if plan.status == "conflict":
        return plan.message
    return run_booker(plan, session_id, original_request=original_request)

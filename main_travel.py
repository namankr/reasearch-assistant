from agent.travel_pipeline import handle_user_message
from chat.service import ChatService
from observability.tracer import flush

PROJECT_ID = "travel_agent"


def main():
    print("\nTravel Agent - Phases 6-9 (Researcher -> Coordinator -> Booker)")
    print("=" * 60)

    chat = ChatService(project_id=PROJECT_ID)
    sid = chat.get_session_id()
    print(f"Session: {sid}")
    print("Examples: 'Find flights and hotels from Delhi to Goa this weekend'")
    print("Commands: quit | new\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "new":
            chat = ChatService(project_id=PROJECT_ID)
            sid = chat.get_session_id()
            print(f"New session: {sid}\n")
            continue

        try:
            response = handle_user_message(user_input, sid)
        except Exception as e:
            response = f"Sorry, that request failed: {e}"

        chat.save_message("user", user_input)
        chat.save_message("assistant", response)
        print(f"\nAgent: {response}\n")

    flush()


if __name__ == "__main__":
    main()
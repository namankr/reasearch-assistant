from chat.service import ChatService
from agent.react_agent import run_agent
import sys

PROJECT_ID = "research_agent"


def main():
    # ── Session handling ──────────────────────────────────────────────────
    chat = ChatService(project_id=PROJECT_ID)
    print(f"\nResearch Agent — Phase 1")
    print(f"Session: {chat.get_session_id()}")
    print("Type 'quit' to exit, 'new' for a new session, 'history' to see past turns\n")

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
            print(f"New session: {chat.get_session_id()}\n")
            continue
        if user_input.lower() == "history":
            for msg in chat.load_history():
                print(f"  [{msg['role']}] {msg['content'][:100]}")
            print()
            continue

        # ── Save user message ─────────────────────────────────────────────
        chat.save_message("user", user_input)

        # ── Load history and run agent ────────────────────────────────────
        history = chat.load_history()
        # Pass history excluding the last message (that's the current query)
        response = run_agent(user_input, history[:-1])

        # ── Save and print response ───────────────────────────────────────
        chat.save_message("assistant", response)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    main()
from chat.service import ChatService
from agent.react_agent import run_agent
from security.sanitiser import demo_injection_attack
from cache.cache_manager import CacheManager
from router.model_router import ModelRouter
from router.cost_tracker import CostTracker


PROJECT_ID = "research_agent"

cache = CacheManager()
router = ModelRouter()
tracker = CostTracker()

def main():
    # ── Show injection demo once at startup ───────────────────────────────
    demo_injection_attack()
    # ── Session handling ──────────────────────────────────────────────────
    chat = ChatService(project_id=PROJECT_ID)
    print(f"\nResearch Agent — Phase 3 & 4")
    print(f"Session: {chat.get_session_id()}")
    print("Type 'quit' to exit, 'new' for a new session, 'history'  to see past turns  'stats'\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye!")
            cache.print_stats()
            tracker.print_summary()
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            cache.print_stats()
            tracker.print_summary()
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
        if user_input.lower() == "stats":
            cache.print_stats()
            tracker.print_summary()
            continue
    

        # ── Phase 4: Route to the right model ────────────────────────────
        model_name, complexity = router.route(user_input)

        # ── Phase 3: Check cache before hitting the LLM ──────────────────
        cached_answer = cache.get(user_input, model_name) 
        if cached_answer:
            # Log as cache hit — zero tokens consumed
            tracker.log(user_input, model_name,
                        tokens_est=0, cache_hit=True)
            chat.save_message("user", user_input)
            chat.save_message("assistant", cached_answer)
            print(f"\nAgent [cached]: {cached_answer}\n")
            continue 

        # ── Cache miss — run the agent ──────────────────────────────────
        # ── Save user message ─────────────────────────────────────────────
        chat.save_message("user", user_input)

        # ── Load history and run agent ────────────────────────────────────
        # history = chat.load_history()
        # Pass history excluding the last message (that's the current query)
        # response = run_agent(user_input, history[:-1])

        response = run_agent(
        user_query=user_input,
        history=chat.build_context(),   # now uses windowed context
        session_id=chat.get_session_id(),
        project_id=PROJECT_ID,
        model_name=model_name
        )
        # ── Store answer in both cache layers ─────────────────────────────
        cache.store(user_input, model_name, response)
        # ── Estimate tokens and log cost ──────────────────────────────────
        # Rough estimate: ~1 token per 4 chars of input + output
        tokens_est = (len(user_input) + len(response)) // 4
        tracker.log(user_input, model_name,
                    tokens_est=tokens_est, cache_hit=False)
        
        # ── Save and print response ───────────────────────────────────────
        chat.save_message("assistant", response)
        print(f"\nAgent [{complexity} → {model_name.split('-')[-1]}]: "
              f"{response}\n")


if __name__ == "__main__":
    main()
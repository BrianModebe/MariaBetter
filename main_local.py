"""
UAE Finance Pro Chatbot -- local RAG CLI. No API key, no cost, fully
offline once the model is downloaded.

Setup (one-time):
    1. Install Ollama: https://ollama.com
    2. ollama pull llama3.2
    3. ollama create uae-finance-bot -f Modelfile   (tuned params -- see Modelfile)

Run:
    python main_local.py                  # uses uae-finance-bot by default
    python main_local.py llama3.1         # or any other pulled/built, tool-capable model

Same retrieval + tool-calling pipeline as main_rag.py (see that file), but
generation runs on your machine via Ollama instead of the Claude API.
Slower and less reliable at tool calls than the Claude version, especially
on CPU-only hardware. uae-finance-bot is llama3.2 with a lower temperature
and higher repeat_penalty (see Modelfile) for more consistent behavior and
fewer repetition-loop failures -- it does not fix the underlying 3B model's
tool-calling judgment, which is a capability ceiling. If it's still
unreliable, try a larger model (e.g. `ollama pull llama3.1` for the 8B
version).

Commands:
    reset       clear conversation history and start fresh
    help        show this message
    quit / exit leave the chatbot
"""

import sys

from local_chatbot import LocalRAGChatbot

HELP_TEXT = """
Commands:
  reset             clear conversation history, start fresh
  help              show this message
  quit / exit       leave the chatbot

Or just ask a finance question, e.g.:
  what is uae corporate tax?
  does that apply to my free zone company?
  if I save 2000 aed a month at 6% for 10 years, what do I end up with?
""".strip()


def _ensure_ready(bot: LocalRAGChatbot, model: str) -> bool:
    try:
        available = {m["model"] for m in bot.client.list()["models"]}
    except Exception as exc:
        print(
            f"Could not reach Ollama ({exc}).\n"
            "Install it from https://ollama.com, make sure it's running, and try again."
        )
        return False

    if not any(m == model or m.startswith(model + ":") for m in available):
        if model == "uae-finance-bot":
            print(
                "Model 'uae-finance-bot' hasn't been built yet. In another terminal, run:\n"
                "  ollama create uae-finance-bot -f Modelfile\n"
                "then re-run this."
            )
        elif model == "uae-finance-bot-tuned":
            print(
                "Model 'uae-finance-bot-tuned' hasn't been built yet. Put uae-finance-bot-tuned.gguf in the\n"
                "project folder, then in another terminal run:\n"
                "  ollama create uae-finance-bot-tuned -f Modelfile.tuned\n"
                "and re-run this (see finetune/README.md)."
            )
        else:
            print(
                f"Model '{model}' isn't pulled yet. In another terminal, run:\n"
                f"  ollama pull {model}\n"
                "then re-run this."
            )
        return False

    return True


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "uae-finance-bot"
    bot = LocalRAGChatbot(model=model)

    if not _ensure_ready(bot, model):
        sys.exit(1)

    print(f"UAE Finance Pro Chatbot (local, model={model}) -- type 'help' for commands, 'quit' to exit.\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        lowered = user_input.lower()

        if lowered in ("quit", "exit"):
            print("Goodbye!")
            break

        if lowered == "help":
            print(HELP_TEXT)
            continue

        if lowered == "reset":
            bot.reset()
            print("Conversation history cleared.\n")
            continue

        try:
            answer = bot.ask(user_input)
        except Exception as exc:
            print(f"\n[error talking to Ollama: {exc}]\n")
            continue

        print(f"\n{answer}\n")
        if bot.last_chart:
            print(f"[Chart: \"{bot.last_chart['title']}\" -- run `python app.py` and open the web UI to view it]\n")
        if bot.last_payment_button:
            print("[Create payment link button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_invoice_button:
            print("[Generate invoice button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_quote_button:
            print("[Generate quote button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_schedule_payments_button:
            print("[Schedule payments button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_chase_payment_button:
            print("[Send reminder button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_refund_button:
            print("[Send refund button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_talk_to_team_button:
            print("[Talk to team button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_set_reminder_button:
            print("[Set reminder button -- run `python app.py` and open the web UI to see it]\n")
        if bot.last_register_business_button:
            print("[Register business button -- run `python app.py` and open the web UI to see it]\n")


if __name__ == "__main__":
    main()

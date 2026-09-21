"""
Finance Education Chatbot — command-line interface.

Run:
    python main.py

Commands (typed at the prompt, case-insensitive):
    topics              List all topic categories.
    list                List every question the bot can answer.
    list <topic>        List questions within one topic (e.g. "list Investing").
    calc                Run a simple compound-interest / savings-growth calculator.
    help                Show this message again.
    quit / exit         Leave the chatbot.

Anything else is treated as a finance question, e.g.:
    > what is compound interest?
    > roth vs traditional
"""

from chatbot import FinanceChatbot

HELP_TEXT = """
Commands:
  topics            list topic categories
  list [topic]       list questions (optionally within one topic)
  calc              run the compound-interest calculator
  help              show this message
  quit / exit       leave the chatbot

Or just ask a finance question, e.g.:
  what is compound interest?
  roth vs traditional ira
  50/30/20 rule
""".strip()


def run_compound_interest_calculator() -> None:
    print("\n-- Compound Interest / Savings Growth Calculator --")
    try:
        principal = float(input("Starting amount ($): ").strip() or 0)
        monthly_contribution = float(input("Monthly contribution ($): ").strip() or 0)
        annual_rate_pct = float(input("Expected annual return (%): ").strip() or 0)
        years = float(input("Number of years: ").strip() or 0)
    except ValueError:
        print("Please enter numeric values only.\n")
        return

    monthly_rate = (annual_rate_pct / 100) / 12
    months = int(round(years * 12))

    balance = principal
    total_contributed = principal
    for _ in range(months):
        balance += monthly_contribution
        total_contributed += monthly_contribution
        balance *= (1 + monthly_rate)

    growth = balance - total_contributed

    print(f"\nAfter {years:g} years:")
    print(f"  Total contributed : ${total_contributed:,.2f}")
    print(f"  Investment growth : ${growth:,.2f}")
    print(f"  Ending balance    : ${balance:,.2f}\n")


def main() -> None:
    bot = FinanceChatbot()
    print("Finance Education Chatbot — type 'help' for commands, 'quit' to exit.\n")

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

        if lowered == "topics":
            for t in bot.topics():
                print(f"  - {t}")
            continue

        if lowered == "calc":
            run_compound_interest_calculator()
            continue

        if lowered.startswith("list"):
            topic = user_input[4:].strip() or None
            questions = bot.list_questions(topic)
            if not questions:
                print(f"No questions found for topic '{topic}'. Type 'topics' to see valid topics.")
            else:
                for q in questions:
                    print(f"  - {q}")
            continue

        match = bot.ask(user_input)
        print(f"\n[{match.topic}] {match.answer}\n")


if __name__ == "__main__":
    main()

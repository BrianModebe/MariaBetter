"""
Knowledge base for the Finance Education Chatbot.

Each entry has:
- "question": the canonical question
- "alt": a list of alternative phrasings/keywords people might use
  (these are folded into the search index to improve matching)
- "answer": the explanation returned to the user
- "topic": a category label, used for the `topics` / `list` command

Feel free to add more entries here — the chatbot re-indexes automatically.
"""

KNOWLEDGE_BASE = [
    # ---------------------------------------------------------------- Budgeting
    {
        "topic": "Budgeting",
        "question": "What is a budget?",
        "alt": ["define budget", "budgeting basics", "how to budget"],
        "answer": (
            "A budget is a plan for how you'll spend and save your income over a "
            "given period. It lists your expected income, then allocates it across "
            "expenses, savings, and debt payments so you spend intentionally rather "
            "than running out of money before your next paycheck."
        ),
    },
    {
        "topic": "Budgeting",
        "question": "What is the 50/30/20 rule?",
        "alt": ["50 30 20 budget rule", "how should I split my income"],
        "answer": (
            "The 50/30/20 rule is a simple budgeting guideline: 50% of after-tax "
            "income goes to needs (rent, utilities, groceries), 30% to wants "
            "(dining out, entertainment), and 20% to savings and debt repayment. "
            "It's a starting point, not a strict law — adjust the splits to fit "
            "your situation."
        ),
    },
    {
        "topic": "Budgeting",
        "question": "What is an emergency fund?",
        "alt": ["why do I need an emergency fund", "how much emergency savings"],
        "answer": (
            "An emergency fund is cash set aside for unexpected expenses (medical "
            "bills, job loss, urgent repairs) so you don't have to rely on high-"
            "interest debt. A common target is 3-6 months of essential living "
            "expenses, kept in an easily accessible account like a savings account."
        ),
    },
    # ---------------------------------------------------------------- Saving & Interest
    {
        "topic": "Saving & Interest",
        "question": "What is compound interest?",
        "alt": ["how does compounding work", "compound vs simple interest"],
        "answer": (
            "Compound interest is interest calculated on both the original amount "
            "(principal) and the interest that has already accumulated. Because "
            "each period's interest is added to the balance before the next "
            "period's interest is calculated, growth accelerates over time — which "
            "is why starting to save early matters more than the amount you start with."
        ),
    },
    {
        "topic": "Saving & Interest",
        "question": "What is the difference between APR and APY?",
        "alt": ["apr vs apy", "annual percentage rate vs yield"],
        "answer": (
            "APR (Annual Percentage Rate) is the simple yearly interest rate, "
            "without accounting for compounding within the year. APY (Annual "
            "Percentage Yield) includes the effect of compounding, so it reflects "
            "the actual return you'd earn (on savings) or pay (on loans) over a year. "
            "APY is always >= APR when compounding occurs more than once a year."
        ),
    },
    {
        "topic": "Saving & Interest",
        "question": "What is inflation?",
        "alt": ["why do prices go up", "what causes inflation"],
        "answer": (
            "Inflation is the rate at which the general price level of goods and "
            "services rises over time, eroding the purchasing power of money. If "
            "inflation is 3% a year, something costing $100 today will cost "
            "roughly $103 next year — meaning cash sitting idle loses real value."
        ),
    },
    # ---------------------------------------------------------------- Investing Basics
    {
        "topic": "Investing",
        "question": "What is a stock?",
        "alt": ["what does it mean to own a share", "define stock"],
        "answer": (
            "A stock (or share) represents a unit of ownership in a company. "
            "Owning stock entitles you to a proportional claim on the company's "
            "assets and profits, and often a vote on major decisions. Stock prices "
            "rise or fall based on the company's performance and investor expectations."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is a bond?",
        "alt": ["how do bonds work", "define bond"],
        "answer": (
            "A bond is essentially a loan you make to a government or company. "
            "In exchange, the issuer promises to pay you periodic interest "
            "(the 'coupon') and return the original amount (the 'face value') at "
            "maturity. Bonds are generally lower-risk and lower-return than stocks."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is a mutual fund?",
        "alt": ["how do mutual funds work"],
        "answer": (
            "A mutual fund pools money from many investors to buy a diversified "
            "portfolio of stocks, bonds, or other assets, managed by a professional "
            "fund manager. You buy shares of the fund itself, and its value moves "
            "with the combined performance of its holdings, minus management fees."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is an ETF?",
        "alt": ["exchange traded fund", "etf vs mutual fund"],
        "answer": (
            "An ETF (Exchange-Traded Fund) is similar to a mutual fund in that it "
            "holds a basket of assets, but it trades on an exchange like a stock, "
            "so its price moves throughout the day. ETFs typically have lower fees "
            "than actively managed mutual funds and are often used to track an index."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is diversification?",
        "alt": ["why diversify", "don't put all eggs in one basket"],
        "answer": (
            "Diversification means spreading your investments across different "
            "assets, sectors, or regions so that a poor result in one doesn't sink "
            "your whole portfolio. It reduces unsystematic (company- or sector-"
            "specific) risk, though it can't eliminate broad market risk."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is risk tolerance?",
        "alt": ["how much investment risk should I take"],
        "answer": (
            "Risk tolerance is how much volatility or potential loss you're "
            "willing and able to accept in pursuit of returns. It depends on your "
            "time horizon, income stability, goals, and psychological comfort with "
            "seeing your portfolio value fluctuate."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is dollar-cost averaging?",
        "alt": ["dca investing strategy"],
        "answer": (
            "Dollar-cost averaging means investing a fixed amount at regular "
            "intervals (e.g., monthly) regardless of price. This buys more shares "
            "when prices are low and fewer when prices are high, smoothing out the "
            "average purchase price and reducing the risk of poorly timed lump-sum "
            "investments."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is market capitalization?",
        "alt": ["market cap meaning"],
        "answer": (
            "Market capitalization ('market cap') is a company's total share price "
            "multiplied by its number of outstanding shares — essentially the "
            "market's estimate of the company's total value. It's used to classify "
            "companies as large-cap, mid-cap, or small-cap."
        ),
    },
    {
        "topic": "Investing",
        "question": "What is a P/E ratio?",
        "alt": ["price to earnings ratio"],
        "answer": (
            "The Price-to-Earnings (P/E) ratio divides a company's share price by "
            "its earnings per share. It's a rough gauge of how much investors are "
            "paying for each dollar of profit — a high P/E can suggest high growth "
            "expectations (or overvaluation), while a low P/E can suggest undervaluation "
            "(or trouble)."
        ),
    },
    # ---------------------------------------------------------------- Credit & Debt
    {
        "topic": "Credit & Debt",
        "question": "What is a credit score?",
        "alt": ["how is credit score calculated", "what affects my credit score"],
        "answer": (
            "A credit score is a numeric summary of your creditworthiness, "
            "typically ranging from 300-850. It's based on factors like payment "
            "history, amounts owed, length of credit history, new credit "
            "inquiries, and credit mix. Lenders use it to decide whether to "
            "approve loans and at what interest rate."
        ),
    },
    {
        "topic": "Credit & Debt",
        "question": "What is the difference between good debt and bad debt?",
        "alt": ["good debt vs bad debt"],
        "answer": (
            "'Good debt' typically finances something that builds wealth or "
            "earning potential over time (e.g., a mortgage, student loans, a "
            "business loan) and often carries a lower interest rate. 'Bad debt' "
            "usually finances depreciating assets or consumption at high interest "
            "(e.g., high-interest credit card debt) and can erode your finances."
        ),
    },
    {
        "topic": "Credit & Debt",
        "question": "What is the debt snowball method?",
        "alt": ["debt snowball vs avalanche"],
        "answer": (
            "The debt snowball method pays off debts from smallest balance to "
            "largest, regardless of interest rate, to build psychological momentum "
            "from quick wins. The debt avalanche method instead targets the "
            "highest-interest debt first, which minimizes total interest paid — "
            "mathematically more efficient, but slower to show early progress."
        ),
    },
    # NOTE: the old "Retirement & Taxes" entries here (401(k), Roth vs
    # traditional IRA, US progressive tax brackets) were removed — they're
    # actively wrong for a UAE user (no personal income tax, no 401k/IRA
    # system). UAE-specific retirement, tax, and business-finance content now
    # lives in knowledge/*.json (see knowledge_loader.py), organized by the
    # clusters in the UAE Finance Pro Chatbot roadmap doc.
    # ---------------------------------------------------------------- Insurance & Risk
    {
        "topic": "Insurance & Risk",
        "question": "What is insurance and how does it work?",
        "alt": ["why do people buy insurance"],
        "answer": (
            "Insurance is a way to transfer financial risk: you pay a smaller, "
            "predictable amount (a premium) to an insurer in exchange for "
            "protection against a larger, uncertain loss (e.g., a health "
            "emergency, car accident, or property damage). Insurers pool "
            "premiums across many policyholders to cover the losses of the few "
            "who file claims."
        ),
    },
    {
        "topic": "Insurance & Risk",
        "question": "What is liquidity?",
        "alt": ["what does liquid asset mean"],
        "answer": (
            "Liquidity refers to how quickly and easily an asset can be converted "
            "to cash without significantly affecting its price. Cash is perfectly "
            "liquid; real estate is relatively illiquid because selling it takes "
            "time and effort. Keeping some liquid assets matters for covering "
            "short-term needs."
        ),
    },
    # ---------------------------------------------------------------- Financial Statements
    {
        "topic": "Financial Statements",
        "question": "What is the difference between assets and liabilities?",
        "alt": ["assets vs liabilities"],
        "answer": (
            "Assets are things you own that have value (cash, investments, "
            "property). Liabilities are what you owe (loans, credit card "
            "balances, mortgages). Net worth is simply assets minus liabilities — "
            "a core measure of financial health."
        ),
    },
    {
        "topic": "Financial Statements",
        "question": "What is cash flow?",
        "alt": ["what is net cash flow", "income vs cash flow"],
        "answer": (
            "Cash flow is the net amount of money moving in and out of your "
            "accounts over a period. Positive cash flow means more coming in than "
            "going out; negative means you're spending more than you earn. It's "
            "distinct from net worth, which is a snapshot of assets vs liabilities "
            "at a point in time."
        ),
    },
]

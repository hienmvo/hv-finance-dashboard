# Finance Dashboard

A minimalist, locally hosted personal finance dashboard for Chase and Bank of America CSV exports.

## Setup

```bash
# 1. Install Flask (only dependency)
pip install flask

# 2. Run
python app.py

# 3. Open in browser
http://localhost:5000
```

## Usage

1. **Upload** — click `+ Upload CSV` and drop in one or more statement CSVs. The app auto-detects the bank.
2. **Filter** — use the bank buttons, date presets (YTD / Q1–Q4 / Monthly / Custom), or the search bar.
3. **Categorize** — change a transaction's category inline via the dropdown, or click **⊕ Similar** to apply a category to all transactions from the same payee at once.
4. **Rules** — when you use **⊕ Similar**, check *"Remember this rule"* to save it. Future uploads will auto-apply the rule. View/delete rules via the **Rules** button.

## Supported Banks

| Bank | How to export |
|------|--------------|
| **Chase** | Account → Download → CSV |
| **Bank of America** | Statements & Documents → Download → CSV |

## Categories

**Income:** Income · Zelle In · ATM Deposit · Investment In · Tax Refund · Wire Transfer In · Cash Rewards · Other Income

**Expenses:** Credit Card Payment · Zelle Out · Rent/Mortgage · Investment Out · Groceries · Utilities · Insurance · Bank Fee · Taxes · Wire Transfer Out · ATM Withdrawal · Other Expense

**Hidden by default:** Internal Transfer (toggle visible via the switch in the filter bar)

## Data

All data is stored locally in `data/finance.db` (SQLite). The `data/` folder is gitignored so your financial data is never committed to version control.

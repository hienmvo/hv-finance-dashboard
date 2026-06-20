# HV Finance Dashboard

> ⚠️ **Early build** functional and actively used, but still in development. Features may change and some banks are not yet supported.

A locally hosted personal finance dashboard that parses Chase and Bank of America CSV exports, auto-categorizes transactions, and visualizes spending over time.

---

## Setup

```bash
# 1. Install the only dependency
pip install flask

# 2. Run
python app.py

# 3. Open in browser
http://localhost:5000
```

---

## Supported Banks

| Bank | Account Type | Format |
|------|-------------|--------|
| Chase | Checking | ✅ |
| Chase | Credit Card | ✅ |
| Bank of America | Checking | ⚠️ |
| Bank of America | Credit Card (standard export) | ⚠️ |
| Bank of America | Credit Card (CardHolder Name export) | ⚠️ |
| Wells Fargo | Any | ❌ Not yet supported |
| Amex | Any | ❌ Not yet supported |

Upload multiple CSVs at once, the app auto-detects the bank from the file format

---

## Features

**Transactions**
- Auto-categorization on upload using rule-based pattern matching
- Inline category editing per transaction
- Use "⊕ Similar" to mass-categorize all transactions matching a payee pattern in one click
- Rules module allows for viewing and deletion of saved auto-categorization rules
- Search, filter by category, sort by date or amount
- "Ignore category" excludes transactions from income/expense totals without hiding them

**Dashboard**
- Income / Expenses / Net summary cards
- Investment tracking card (Webull, Wealthfront) tracks deposits, withdrawals, and net invested separately from regular income/expenses
- Income and expense donut charts
- Trends line chart visualize income vs expenses over time with toggleable net line
- Bar chart visualize stacked expenses by category or income vs expenses side by side
- All charts support Day / Week / Month / Quarter granularity

**Filtering**
- Filter by bank account
- Date presets: All Time, YTD, Q1 - Q4, monthly picker, or custom range
- Show/hide internal transfers toggle
- Chase CC payments automatically hidden from checking to prevent double-counting

---

## Data & Privacy

All data is stored locally in a SQLite database (`finance.db`). Nothing is sent to any external server.

---

## Known Limitations

- Bank of America CSV formats may sometimes have issues
- Wells Fargo / Amex CSV formats are not yet supported
- No mobile layout, designed for desktop use
- Budget planning tab is planned but not yet implemented

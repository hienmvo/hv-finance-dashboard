# HV Finance Dashboard
> ⚠️ **Early build** - Functional and actively used, but still in development. Features may change and some banks are not yet supported.
 
A personal finance dashboard that analyzes Chase and Bank of America CSV exports, auto-categorizes transactions, and visualizes spending over time. Runs as a standalone desktop app, no browser or internet connection required.
 
---
 
## Installation
 
Download `FinanceDashboard.exe` from the [Releases](https://github.com/hienmvo/hv_finance_dashboard/releases) page and double-click to run. No Python or setup required.
 
> All data is stored locally on your device. No data is ever uploaded or shared.
 
## Supported Banks
 
| Bank | Account Type | Status |
|------|-------------|--------|
| Chase | Checking | ✅ |
| Chase | Credit Card | ✅ |
| Bank of America | Checking | ⚠️ |
| Bank of America | Credit Card (standard export) | ⚠️ |
| Bank of America | Credit Card (CardHolder Name export) | ⚠️ |
| Wells Fargo | Any | ❌ Not yet supported |
| Amex | Any | ❌ Not yet supported |
 
Upload multiple CSVs at once. The app auto-detects the bank from the file format.
 
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
- Trends line chart visualizes income vs expenses over time with toggleable net line
- Bar chart visualizes stacked expenses by category or income vs expenses side by side
- All charts support Day / Week / Month / Quarter granularity

**Filtering**
  
- Filter by bank account
- Date presets: All Time, YTD, Q1 - Q4, monthly picker, or custom range
- Show/hide internal transfers toggle
- Chase CC payments automatically hidden from checking to prevent double-counting

**Other**
  
- Drag and drop CSV upload
- Reset button to wipe all transactions and rules and start fresh
---
 
## Data & Privacy
 
All data is stored locally in a SQLite database on your device (`AppData/Roaming/FinanceDashboard/` on Windows). Nothing is sent to any external server.
 
---
 
## Known Limitations

- No mobile layout, so far only tested for Windows
- Bank of America CSV formats may sometimes have issues
- Wells Fargo / Amex CSV formats are not yet supported
- Budget planning tab is planned but not yet implemented
 

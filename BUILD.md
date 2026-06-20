# Building the Finance Dashboard Desktop App

## First-time setup

Install dependencies:
```
pip install flask pywebview pyinstaller
```

---

## Running without building (still works)

```
python app.py
```

This opens a native app window directly — no browser needed. You only need to build
with PyInstaller if you want a standalone `.exe` / `.app` to double-click without Python.

---

## Building the standalone executable

From the project folder, run:

```
pyinstaller finance_dashboard.spec
```

This produces a `dist/FinanceDashboard/` folder. Inside is `FinanceDashboard.exe`
(Windows) or `FinanceDashboard` (Mac/Linux).

**To use it:**
1. Copy the entire `dist/FinanceDashboard/` folder wherever you want (Desktop, etc.)
2. Double-click `FinanceDashboard.exe` (or create a shortcut to it)
3. A `data/` folder is created next to the executable — this is where your database lives

> Your transaction history persists between sessions in `data/finance.db`.
> Don't delete that folder unless you want to wipe your data.

---

## Notes

- Build on Windows → get a `.exe`. Build on Mac → get a `.app`. You can't cross-compile.
- The `dist/` and `build/` folders are safe to delete and rebuild anytime.
- First launch may take 2–3 seconds while the app initializes.

# Expense Tracker

A small Flask + SQLite expense tracker used to practise agentic workflows.
See CLAUDE.md for how we work on it.

## Setup

```
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS or Linux
pip install -r requirements.txt
```

## Run

```
python seed.py     # optional: load about 50 sample expenses into expenses.db
python app.py      # then open http://127.0.0.1:5000
```

Pages: `/` (add, list, total), `/report` (monthly report), and `/budgets`
(budgets, see below).

## Budgets

Set a budget per category per month on `/budgets`. The page shows, for a month
(default: the current month, or pick one with `?month=YYYY-MM`), how much was
spent per category against its budget. A category over its budget is flagged
OVER. A category with spending but no budget shows its spend and is never
flagged. Exactly at the budget is not over.

`python seed.py` also sets sample budgets for 2026-09 and 2026-10. It adds them
to an existing `expenses.db` too. The seeded expenses run May to September 2026,
so view `?month=2026-09` to see over budget rows.

## Test

```
pytest
```

## Layout

- `app.py`: Flask routes (web layer only)
- `expenses.py`: data access, calculation, and budget logic
- `seed.py`: sample data
- `tests/`: pytest unit tests

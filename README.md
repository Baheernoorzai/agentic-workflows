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

Pages: `/` (add, list, total) and `/report` (monthly report).

## Test

```
pytest
```

## Layout

- `app.py`: Flask routes (web layer only)
- `expenses.py`: data access and calculation logic
- `seed.py`: sample data
- `tests/`: pytest unit tests

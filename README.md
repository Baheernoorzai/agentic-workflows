# Applied Agentic Workflows: Expense Tracker

A small Flask + SQLite expense tracker used to practise and document four
reusable workflows with Claude Code: feature development, bug triage,
refactoring, and analytics. The app is intentionally realistic and slightly
imperfect, so each workflow had honest work to do.

## The four workflows

| Workflow | What we did in this project |
|---|---|
| Feature development | Added monthly budgets: set a budget per category per month and flag categories that are over budget |
| Bug triage | Reproduced and fixed an expense total that was sometimes off by a cent (float rounding), with a regression test |
| Refactoring | Broke the long, deeply nested `monthly_report` into small functions with no behavior change, guarded by characterization tests |
| Analytics | Explored the data, answered business questions with SQL, and verified every figure a second way |

- [PLAYBOOKS.md](PLAYBOOKS.md): the four workflows as reusable playbooks, each
  with ordered steps, human checkpoints, and a prompt template you can paste.
- [ANALYSIS.md](ANALYSIS.md): the analytics workflow's output, with the
  questions, queries, results, and a verified insights summary.
- [CLAUDE.md](CLAUDE.md): the working rules for the agent (plan then act,
  checkpoints, small steps, git save points). It also maps phrases like "run
  the bug triage workflow" to the matching playbook.

## Setup

```
python -m venv venv
venv\Scripts\activate         # Windows (PowerShell: venv\Scripts\Activate.ps1)
# source venv/bin/activate    # macOS or Linux
pip install -r requirements.txt
```

## Run

```
python seed.py     # load about 50 sample expenses and sample budgets into expenses.db
python app.py      # then open http://127.0.0.1:5000
```

If `flask run` is not found on your PATH, use `python -m flask run` instead.

Pages: `/` (add, list, total), `/report` (monthly report), and `/budgets`
(budgets, see below).

## Budgets

Set a budget per category per month on `/budgets`. The page shows, for a month
(default: the current month, or pick one with `?month=YYYY-MM`), how much was
spent per category against its budget. A category over its budget is flagged
OVER. A category with spending but no budget shows its spend and is never
flagged. Exactly at the budget is not over.

`python seed.py` sets sample budgets for 2026-09 and 2026-10, and adds them to
an existing `expenses.db` too. The seeded expenses run May to September 2026,
so view `?month=2026-09` to see over budget rows.

## Test

```
pytest
```

The suite includes the budget tests, a regression test for the total bug, and
characterization tests that pin the behavior of `monthly_report`.

## Layout

- `app.py`: Flask routes (web layer only)
- `expenses.py`: data access, calculation, and budget logic
- `seed.py`: sample data
- `tests/`: pytest unit tests
- `CLAUDE.md`, `PLAYBOOKS.md`, `ANALYSIS.md`: the workflow documentation

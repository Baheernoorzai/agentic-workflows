# CLAUDE.md

## Project purpose

A single small Flask + SQLite expense tracker that we will use to practise four
real world workflows: feature development, bug triage, refactoring, and
analytics. The app is intentionally realistic and slightly imperfect so the
workflows have honest work to do.

The four workflows:

1. Feature development: add a new capability to the app.
2. Bug triage: reproduce, diagnose, and fix a reported defect.
3. Refactoring: improve structure without changing behavior.
4. Analytics: answer questions about the expense data.

## How I want you to work (applies to every workflow)

1. PLAN THEN ACT: for any non trivial task, investigate and propose a short
   plan BEFORE changing code. Wait for my approval.
2. CHECKPOINTS: pause for my approval after you propose a plan, after you
   diagnose a bug, and before any bulk or risky change.
3. SMALL STEPS: make one logical change at a time and tell me how to verify it.
4. GIT SAVE POINTS: after each good state, suggest a commit with a clear
   message. One logical change, one commit.
5. STAY IN SCOPE: do only what the current brief asks. If you spot other
   issues, list them for later rather than fixing them now.
6. EXPLAIN: briefly explain what you did and why, so I learn the workflow, not
   just the result.

### What this means in practice

- Do not edit files until I have approved the plan for that task.
- A plan is short: what you found, what you will change, how we will verify it.
- Run the tests (or the relevant check) after each step and report the result
  honestly, including failures.
- Never commit on your own. Suggest the commit message and wait for me.
- "Risky" includes deleting data, rewriting many files at once, schema changes,
  and anything that touches the SQLite database file.
- Keep a running "noticed but not fixed" list and show it at the end of a task.

## Tech conventions

- Python 3, Flask, SQLite, pytest for tests.
- Keep business logic separate from the web layer where reasonable, so it can
  be tested directly.
- Do NOT use em dashes or en dashes anywhere in code, comments, or docs. Use
  commas or the word 'to' for ranges.

## Workflow notes

### Feature development
- Restate the feature in your own words and confirm it before planning.
- Add or update tests alongside the feature.

### Bug triage
- Reproduce the bug first, ideally with a failing test.
- Diagnose and report the root cause, then pause for my approval before fixing.
- Fix only the diagnosed cause, not neighboring problems.

### Refactoring
- Behavior must not change. Make sure tests cover the code before moving it.
- Refactor in small steps, running tests after each one.

### Analytics
- Prefer read only queries. Never modify expense data while analysing it.
- State the question, the query used, and any assumptions behind the answer.

## Note

Do not build the app yet. I will ask for it in the next step.

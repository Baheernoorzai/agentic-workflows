"""Data access and calculation logic for the expense tracker.

This module has no Flask imports so it can be unit tested directly.
"""
import math
import sqlite3
from datetime import datetime
from decimal import Decimal

DEFAULT_DB = "expenses.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    date TEXT NOT NULL,
    note TEXT
)
"""


def get_connection(db_path=DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


BUDGETS_SCHEMA = """
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    month TEXT NOT NULL,
    amount REAL NOT NULL,
    UNIQUE (category, month)
)
"""


def init_db(conn):
    conn.execute(SCHEMA)
    conn.execute(BUDGETS_SCHEMA)
    conn.commit()


def add_expense(conn, amount, category, date, note=None):
    """Validate and insert an expense. Returns the new row id."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Amount must be a number")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    category = (category or "").strip()
    if not category:
        raise ValueError("Category is required")

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError("Date must be in YYYY-MM-DD format")

    note = (note or "").strip() or None

    cur = conn.execute(
        "INSERT INTO expenses (amount, category, date, note) VALUES (?, ?, ?, ?)",
        (amount, category, date, note),
    )
    conn.commit()
    return cur.lastrowid


def list_expenses(conn):
    """All expenses, newest first."""
    rows = conn.execute(
        "SELECT id, amount, category, date, note FROM expenses ORDER BY date DESC, id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def calculate_total(expenses):
    """Sum the amounts of the given expenses (list of dicts)."""
    # FIXED (was TEACHING CONSTRAINT A): float accumulation drifted, e.g.
    # 0.01 + 33.33 * 3 gave 99.99999999999999. Sum exact decimals instead.
    # str() gives the shortest round-trip form, so 0.1 becomes Decimal("0.1").
    total = Decimal("0")
    for e in expenses:
        total += Decimal(str(e["amount"]))
    return float(total)


def _month_key(date_string):
    """Return "YYYY-MM" for a "YYYY-MM-DD" date string. Raises ValueError if bad."""
    d = datetime.strptime(date_string, "%Y-%m-%d")
    return f"{d.year}-{d.month:02d}"


def _group_by_month(expenses):
    """Sort usable expenses into months and categories. Returns (months, skipped).

    Behavior kept exactly as it was (see the characterization tests):
    - A month entry is created as soon as a row has a parseable date, even if
      the amount is then skipped, so such a month can end up empty.
    - Amounts that are None, zero, negative, or NaN are skipped and counted.
    - A falsy category becomes "Uncategorized".
    - category is only read after the amount is accepted.
    """
    months = {}
    skipped = 0
    for expense in expenses:
        if expense is None:
            skipped += 1
            continue
        if "date" not in expense or not expense["date"]:
            skipped += 1
            continue
        try:
            month_key = _month_key(expense["date"])
        except ValueError:
            skipped += 1
            continue

        month = months.setdefault(
            month_key, {"total": 0.0, "count": 0, "categories": {}}
        )
        amount = expense["amount"]
        if amount is None or not amount > 0:
            skipped += 1
            continue

        name = expense["category"] if expense["category"] else "Uncategorized"
        category = month["categories"].setdefault(name, {"total": 0.0, "count": 0})
        month["total"] += amount
        month["count"] += 1
        category["total"] += amount
        category["count"] += 1
    return months, skipped


def _top_category(categories):
    """Name of the category with the largest total, or None if there are none.

    A tie goes to the category seen first (insertion order), not alphabetical.
    """
    return max(categories, key=lambda name: categories[name]["total"], default=None)


def _category_lines(month):
    """Per-category rows for one month, alphabetical, with percent of the month."""
    lines = []
    for name in sorted(month["categories"]):
        category = month["categories"][name]
        percent = 0
        if month["total"] > 0:
            percent = category["total"] / month["total"] * 100
        lines.append({
            "category": name,
            "total": round(category["total"], 2),
            "count": category["count"],
            "percent": round(percent, 1),
        })
    return lines


def _month_summary(month_key, month):
    """One month's row in the report: totals, average, top category, categories."""
    average = month["total"] / month["count"] if month["count"] > 0 else 0
    return {
        "month": month_key,
        "total": round(month["total"], 2),
        "count": month["count"],
        "average": round(average, 2),
        "top_category": _top_category(month["categories"]),
        "categories": _category_lines(month),
    }


def monthly_report(expenses):
    """Spending report grouped by month, then by category.

    Returns {"months": [...], "grand_total": float, "skipped": int}. Months
    are in date order. Rows that cannot be used are counted in "skipped".

    REFACTORED (was TEACHING CONSTRAINT B). Behavior is unchanged and pinned by
    tests/test_monthly_report_characterization.py, quirks included.
    """
    months, skipped = _group_by_month(expenses)
    summaries = []
    grand_total = 0.0
    for month_key in sorted(months):
        grand_total += months[month_key]["total"]
        summaries.append(_month_summary(month_key, months[month_key]))
    return {
        "months": summaries,
        "grand_total": round(grand_total, 2),
        "skipped": skipped,
    }


def _validate_month(month):
    # Round-trip so unpadded input like "2026-9" is rejected, not stored
    # under a key that would never match "2026-09".
    try:
        if datetime.strptime(month, "%Y-%m").strftime("%Y-%m") != month:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Month must be in YYYY-MM format")
    return month


def set_budget(conn, category, month, amount):
    """Set the budget for a category and month. Setting it again updates it."""
    category = (category or "").strip()
    if not category:
        raise ValueError("Category is required")
    _validate_month(month)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Budget amount must be a number")
    if not math.isfinite(amount):
        raise ValueError("Budget amount must be a number")
    if amount <= 0:
        raise ValueError("Budget amount must be greater than zero")

    conn.execute(
        "INSERT INTO budgets (category, month, amount) VALUES (?, ?, ?) "
        "ON CONFLICT (category, month) DO UPDATE SET amount = excluded.amount",
        (category, month, amount),
    )
    conn.commit()


def list_budgets(conn, month):
    """All budgets set for the given month, ordered by category."""
    _validate_month(month)
    rows = conn.execute(
        "SELECT id, category, month, amount FROM budgets WHERE month = ? ORDER BY category",
        (month,),
    ).fetchall()
    return [dict(r) for r in rows]


def budget_status(conn, month):
    """Spent versus budget per category for one month (YYYY-MM).

    One row per category that has a budget or any spending that month:
    {category, budget, spent, remaining, over}. A category with no budget
    shows its spend but has budget and remaining set to None and is never
    flagged over. Over means spent is strictly greater than budget.
    """
    _validate_month(month)

    # Sum in whole cents so float rounding cannot leak into comparisons.
    spent_cents = {}
    rows = conn.execute(
        "SELECT category, amount FROM expenses WHERE substr(date, 1, 7) = ?",
        (month,),
    ).fetchall()
    for r in rows:
        spent_cents[r["category"]] = spent_cents.get(r["category"], 0) + round(r["amount"] * 100)

    budget_cents = {b["category"]: round(b["amount"] * 100) for b in list_budgets(conn, month)}

    status = []
    for category in set(spent_cents) | set(budget_cents):
        spent = spent_cents.get(category, 0)
        budget = budget_cents.get(category)
        status.append({
            "category": category,
            "budget": None if budget is None else budget / 100,
            "spent": spent / 100,
            "remaining": None if budget is None else (budget - spent) / 100,
            "over": budget is not None and spent > budget,
        })

    status.sort(key=lambda s: (not s["over"], s["category"]))
    return status

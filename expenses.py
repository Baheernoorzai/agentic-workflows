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


def monthly_report(expenses):
    # TEACHING CONSTRAINT B: intentionally long, deeply nested, and doing
    # several jobs at once (parsing, grouping, totals, stats, formatting).
    # This is the refactoring target. Do not clean it up yet.
    report = {}
    skipped = 0
    for e in expenses:
        if e is not None:
            if "date" in e and e["date"]:
                try:
                    d = datetime.strptime(e["date"], "%Y-%m-%d")
                    month_key = str(d.year) + "-" + ("0" + str(d.month) if d.month < 10 else str(d.month))
                    if month_key not in report:
                        report[month_key] = {"total": 0.0, "count": 0, "categories": {}}
                    if e["amount"] is not None:
                        if e["amount"] > 0:
                            report[month_key]["total"] += e["amount"]
                            report[month_key]["count"] += 1
                            cat = e["category"] if e["category"] else "Uncategorized"
                            if cat not in report[month_key]["categories"]:
                                report[month_key]["categories"][cat] = {"total": 0.0, "count": 0}
                            report[month_key]["categories"][cat]["total"] += e["amount"]
                            report[month_key]["categories"][cat]["count"] += 1
                        else:
                            skipped += 1
                    else:
                        skipped += 1
                except ValueError:
                    skipped += 1
            else:
                skipped += 1
        else:
            skipped += 1

    lines = []
    grand_total = 0.0
    for month_key in sorted(report.keys()):
        m = report[month_key]
        grand_total += m["total"]
        top_cat = None
        top_amount = -1
        for cat in m["categories"]:
            if m["categories"][cat]["total"] > top_amount:
                top_amount = m["categories"][cat]["total"]
                top_cat = cat
        avg = m["total"] / m["count"] if m["count"] > 0 else 0
        cat_lines = []
        for cat in sorted(m["categories"].keys()):
            pct = 0
            if m["total"] > 0:
                pct = m["categories"][cat]["total"] / m["total"] * 100
            cat_lines.append({
                "category": cat,
                "total": round(m["categories"][cat]["total"], 2),
                "count": m["categories"][cat]["count"],
                "percent": round(pct, 1),
            })
        lines.append({
            "month": month_key,
            "total": round(m["total"], 2),
            "count": m["count"],
            "average": round(avg, 2),
            "top_category": top_cat,
            "categories": cat_lines,
        })

    return {"months": lines, "grand_total": round(grand_total, 2), "skipped": skipped}


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

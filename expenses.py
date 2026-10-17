"""Data access and calculation logic for the expense tracker.

This module has no Flask imports so it can be unit tested directly.
"""
import sqlite3
from datetime import datetime

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


def init_db(conn):
    conn.execute(SCHEMA)
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
    # TEACHING CONSTRAINT A: plain float accumulation. Money can pick up
    # rounding errors this way (e.g. 0.1 + 0.2). To be fixed in bug triage.
    total = 0.0
    for e in expenses:
        total += e["amount"]
    return total


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

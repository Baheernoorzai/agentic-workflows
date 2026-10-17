"""Insert about 50 sample expenses across several categories and months.

Usage: python seed.py [db_path]
Re-running adds more rows only if the table is empty, to avoid duplicates.
"""
import random
import sys
from datetime import date, timedelta

import expenses

# (category, min amount, max amount, sample notes)
CATEGORIES = [
    ("Groceries", 15, 120, ["Weekly shop", "Farmers market", "Corner store"]),
    ("Rent", 1200, 1200, ["Monthly rent"]),
    ("Transport", 5, 60, ["Bus pass", "Fuel", "Taxi", "Train ticket"]),
    ("Dining", 10, 90, ["Lunch", "Dinner out", "Coffee", "Takeaway"]),
    ("Utilities", 40, 160, ["Electricity", "Water", "Internet"]),
    ("Entertainment", 8, 70, ["Movie", "Concert", "Streaming", "Game"]),
    ("Health", 10, 150, ["Pharmacy", "Gym", "Dentist"]),
]

START = date(2026, 5, 1)
END = date(2026, 9, 30)
COUNT = 50


def seed(conn, count=COUNT):
    rng = random.Random(42)
    span = (END - START).days
    inserted = 0

    # One rent payment per month so the category has a clear pattern.
    for month in range(5, 10):
        expenses.add_expense(conn, 1200, "Rent", date(2026, month, 1).isoformat(), "Monthly rent")
        inserted += 1

    while inserted < count:
        name, low, high, notes = rng.choice(CATEGORIES[:1] + CATEGORIES[2:])
        when = START + timedelta(days=rng.randint(0, span))
        amount = round(rng.uniform(low, high), 2)
        note = rng.choice(notes) if rng.random() < 0.7 else None
        expenses.add_expense(conn, amount, name, when.isoformat(), note)
        inserted += 1
    return inserted


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else expenses.DEFAULT_DB
    conn = expenses.get_connection(path)
    expenses.init_db(conn)
    existing = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    if existing:
        print(f"{path} already has {existing} expenses, skipping seed.")
    else:
        print(f"Inserted {seed(conn)} expenses into {path}.")
    conn.close()

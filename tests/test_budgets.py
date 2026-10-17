import pytest

import expenses

MONTH = "2026-09"


@pytest.fixture
def conn():
    c = expenses.get_connection(":memory:")
    expenses.init_db(c)
    yield c
    c.close()


def by_category(status):
    return {s["category"]: s for s in status}


def test_set_budget_inserts(conn):
    expenses.set_budget(conn, "Dining", MONTH, "200")
    budgets = expenses.list_budgets(conn, MONTH)
    assert len(budgets) == 1
    assert budgets[0]["category"] == "Dining"
    assert budgets[0]["amount"] == 200


def test_set_budget_again_updates(conn):
    expenses.set_budget(conn, "Dining", MONTH, 200)
    expenses.set_budget(conn, "Dining", MONTH, 250)
    budgets = expenses.list_budgets(conn, MONTH)
    assert len(budgets) == 1
    assert budgets[0]["amount"] == 250


def test_set_budget_strips_category_whitespace(conn):
    expenses.set_budget(conn, "  Dining ", MONTH, 100)
    assert expenses.list_budgets(conn, MONTH)[0]["category"] == "Dining"


def test_init_db_adds_budgets_table_to_existing_database(conn):
    conn.execute("DROP TABLE budgets")
    expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    expenses.init_db(conn)
    expenses.set_budget(conn, "Dining", MONTH, 100)
    assert len(expenses.list_budgets(conn, MONTH)) == 1
    assert len(expenses.list_expenses(conn)) == 1


def test_budgets_are_per_month(conn):
    expenses.set_budget(conn, "Dining", "2026-09", 200)
    expenses.set_budget(conn, "Dining", "2026-10", 300)
    assert expenses.list_budgets(conn, "2026-09")[0]["amount"] == 200
    assert expenses.list_budgets(conn, "2026-10")[0]["amount"] == 300


@pytest.mark.parametrize(
    "category,month,amount",
    [
        ("", MONTH, 100),
        ("  ", MONTH, 100),
        ("Dining", "2026/09", 100),
        ("Dining", "2026-13", 100),
        ("Dining", None, 100),
        ("Dining", MONTH, "abc"),
        ("Dining", MONTH, 0),
        ("Dining", MONTH, -50),
        ("Dining", "2026-9", 100),
        ("Dining", MONTH, "nan"),
        ("Dining", MONTH, "inf"),
    ],
)
def test_set_budget_rejects_bad_input(conn, category, month, amount):
    with pytest.raises(ValueError):
        expenses.set_budget(conn, category, month, amount)


def test_status_under_budget(conn):
    expenses.set_budget(conn, "Dining", MONTH, 100)
    expenses.add_expense(conn, 40, "Dining", "2026-09-05")
    row = by_category(expenses.budget_status(conn, MONTH))["Dining"]
    assert row["budget"] == 100
    assert row["spent"] == 40
    assert row["remaining"] == 60
    assert row["over"] is False


def test_status_exactly_at_budget_is_not_over(conn):
    expenses.set_budget(conn, "Dining", MONTH, 100)
    expenses.add_expense(conn, 60, "Dining", "2026-09-05")
    expenses.add_expense(conn, 40, "Dining", "2026-09-20")
    row = by_category(expenses.budget_status(conn, MONTH))["Dining"]
    assert row["spent"] == 100
    assert row["remaining"] == 0
    assert row["over"] is False


def test_status_over_budget_is_flagged(conn):
    expenses.set_budget(conn, "Dining", MONTH, 100)
    expenses.add_expense(conn, 80, "Dining", "2026-09-05")
    expenses.add_expense(conn, 45.5, "Dining", "2026-09-20")
    row = by_category(expenses.budget_status(conn, MONTH))["Dining"]
    assert row["spent"] == 125.5
    assert row["remaining"] == -25.5
    assert row["over"] is True


def test_status_no_budget_shows_spend_but_is_not_flagged(conn):
    expenses.add_expense(conn, 500, "Travel", "2026-09-10")
    row = by_category(expenses.budget_status(conn, MONTH))["Travel"]
    assert row["spent"] == 500
    assert row["budget"] is None
    assert row["remaining"] is None
    assert row["over"] is False


def test_status_budget_with_no_spending(conn):
    expenses.set_budget(conn, "Health", MONTH, 75)
    row = by_category(expenses.budget_status(conn, MONTH))["Health"]
    assert row["spent"] == 0
    assert row["remaining"] == 75
    assert row["over"] is False


def test_status_ignores_other_months(conn):
    expenses.set_budget(conn, "Dining", MONTH, 100)
    expenses.add_expense(conn, 90, "Dining", "2026-08-31")
    expenses.add_expense(conn, 90, "Dining", "2026-10-01")
    expenses.add_expense(conn, 10, "Dining", "2026-09-15")
    row = by_category(expenses.budget_status(conn, MONTH))["Dining"]
    assert row["spent"] == 10


def test_status_float_cents_do_not_cause_false_over(conn):
    # 0.1 + 0.2 is 0.30000000000000004 as a float, which would exceed 0.3.
    expenses.set_budget(conn, "Dining", MONTH, 0.3)
    expenses.add_expense(conn, 0.1, "Dining", "2026-09-01")
    expenses.add_expense(conn, 0.2, "Dining", "2026-09-02")
    row = by_category(expenses.budget_status(conn, MONTH))["Dining"]
    assert row["spent"] == 0.3
    assert row["over"] is False


def test_status_orders_over_budget_first_then_alphabetical(conn):
    expenses.set_budget(conn, "Dining", MONTH, 100)
    expenses.set_budget(conn, "Utilities", MONTH, 50)
    expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    expenses.add_expense(conn, 90, "Utilities", "2026-09-01")
    expenses.add_expense(conn, 5, "Groceries", "2026-09-01")
    names = [s["category"] for s in expenses.budget_status(conn, MONTH)]
    assert names == ["Utilities", "Dining", "Groceries"]


def test_status_rejects_bad_month(conn):
    with pytest.raises(ValueError):
        expenses.budget_status(conn, "September")

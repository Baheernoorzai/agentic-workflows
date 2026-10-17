import pytest

import expenses


@pytest.fixture
def conn():
    c = expenses.get_connection(":memory:")
    expenses.init_db(c)
    yield c
    c.close()


def ids(conn):
    return [e["id"] for e in expenses.list_expenses(conn)]


def test_delete_removes_only_that_expense(conn):
    a = expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    b = expenses.add_expense(conn, 20, "Transport", "2026-09-02")
    c = expenses.add_expense(conn, 30, "Health", "2026-09-03")
    assert expenses.delete_expense(conn, b) is True
    assert sorted(ids(conn)) == sorted([a, c])


def test_delete_unknown_id_returns_false_and_changes_nothing(conn):
    a = expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    assert expenses.delete_expense(conn, 9999) is False
    assert ids(conn) == [a]


def test_delete_same_id_twice_second_is_false(conn):
    a = expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    assert expenses.delete_expense(conn, a) is True
    assert expenses.delete_expense(conn, a) is False
    assert ids(conn) == []


def test_delete_on_empty_table_is_false(conn):
    assert expenses.delete_expense(conn, 1) is False


def test_total_reflects_deletion(conn):
    expenses.add_expense(conn, 0.1, "A", "2026-09-01")
    b = expenses.add_expense(conn, 0.2, "A", "2026-09-02")
    assert expenses.calculate_total(expenses.list_expenses(conn)) == 0.3
    expenses.delete_expense(conn, b)
    assert expenses.calculate_total(expenses.list_expenses(conn)) == 0.1


def test_budget_status_reflects_deletion(conn):
    expenses.set_budget(conn, "Dining", "2026-09", 100)
    big = expenses.add_expense(conn, 150, "Dining", "2026-09-05")
    row = next(s for s in expenses.budget_status(conn, "2026-09") if s["category"] == "Dining")
    assert row["over"] is True
    expenses.delete_expense(conn, big)
    row = next(s for s in expenses.budget_status(conn, "2026-09") if s["category"] == "Dining")
    assert row["spent"] == 0
    assert row["over"] is False


def test_deleting_an_expense_does_not_touch_budgets(conn):
    expenses.set_budget(conn, "Dining", "2026-09", 100)
    a = expenses.add_expense(conn, 10, "Dining", "2026-09-05")
    expenses.delete_expense(conn, a)
    assert len(expenses.list_budgets(conn, "2026-09")) == 1


def test_deleted_ids_are_not_reused(conn):
    a = expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    b = expenses.add_expense(conn, 20, "Dining", "2026-09-02")
    expenses.delete_expense(conn, b)
    c = expenses.add_expense(conn, 30, "Dining", "2026-09-03")
    assert c > b > a


def test_monthly_report_reflects_deletion(conn):
    a = expenses.add_expense(conn, 10, "Dining", "2026-09-01")
    expenses.add_expense(conn, 5, "Dining", "2026-09-02")
    expenses.delete_expense(conn, a)
    report = expenses.monthly_report(expenses.list_expenses(conn))
    assert report["grand_total"] == 5.0

import pytest

import expenses
import seed


@pytest.fixture
def conn():
    c = expenses.get_connection(":memory:")
    expenses.init_db(c)
    yield c
    c.close()


def test_add_and_list(conn):
    expenses.add_expense(conn, "12.50", "Dining", "2026-06-01", "Lunch")
    expenses.add_expense(conn, 30, "Transport", "2026-06-02")
    items = expenses.list_expenses(conn)
    assert len(items) == 2
    assert items[0]["date"] == "2026-06-02"  # newest first
    assert items[1]["note"] == "Lunch"
    assert items[0]["note"] is None


@pytest.mark.parametrize(
    "amount,category,date",
    [
        ("abc", "Dining", "2026-06-01"),
        (-5, "Dining", "2026-06-01"),
        (0, "Dining", "2026-06-01"),
        (10, "  ", "2026-06-01"),
        (10, "Dining", "06/01/2026"),
        (10, "Dining", "2026-13-40"),
        (10, "Dining", None),
    ],
)
def test_add_rejects_bad_input(conn, amount, category, date):
    with pytest.raises(ValueError):
        expenses.add_expense(conn, amount, category, date)


def test_calculate_total_simple():
    items = [{"amount": 10.0}, {"amount": 5.5}]
    assert expenses.calculate_total(items) == 15.5


def test_calculate_total_empty():
    assert expenses.calculate_total([]) == 0


def test_monthly_report_groups_by_month_and_category():
    items = [
        {"amount": 10, "category": "A", "date": "2026-05-03"},
        {"amount": 30, "category": "B", "date": "2026-05-20"},
        {"amount": 20, "category": "A", "date": "2026-06-01"},
    ]
    report = expenses.monthly_report(items)
    assert [m["month"] for m in report["months"]] == ["2026-05", "2026-06"]
    may = report["months"][0]
    assert may["total"] == 40
    assert may["top_category"] == "B"
    assert may["average"] == 20
    assert report["grand_total"] == 60
    assert report["skipped"] == 0


def test_monthly_report_skips_bad_rows():
    items = [
        {"amount": 10, "category": "A", "date": "not-a-date"},
        {"amount": None, "category": "A", "date": "2026-05-01"},
        {"amount": 5, "category": "A", "date": "2026-05-01"},
    ]
    report = expenses.monthly_report(items)
    assert report["skipped"] == 2
    assert report["grand_total"] == 5


def test_seed_inserts_expected_range(conn):
    n = seed.seed(conn)
    assert 40 <= n <= 60
    items = expenses.list_expenses(conn)
    assert len(items) == n
    assert len({i["category"] for i in items}) >= 5
    assert len({i["date"][:7] for i in items}) >= 3

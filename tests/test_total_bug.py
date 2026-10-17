"""Regression tests for the bug report: expense total sometimes off.

Float accumulation made totals like 99.99999999999999 instead of 100.0, and
the result depended on the order of the amounts. Expected values here are the
exact decimal sums of the amounts.
"""
import itertools

import app as app_module
import expenses


def as_items(amounts):
    return [{"amount": a} for a in amounts]


def test_three_thirds_and_a_cent_total_exactly_100():
    # 0.01 + 33.33 + 33.33 + 33.33 is exactly 100.00 in decimal money.
    total = expenses.calculate_total(as_items([0.01, 33.33, 33.33, 33.33]))
    assert total == 100.0


def test_ten_dimes_total_exactly_one_dollar():
    total = expenses.calculate_total(as_items([0.1] * 10))
    assert total == 1.0


def test_total_does_not_depend_on_order():
    amounts = [0.01, 33.33, 33.33, 33.33]
    totals = {
        expenses.calculate_total(as_items(p))
        for p in itertools.permutations(amounts)
    }
    assert totals == {100.0}


def test_empty_and_single_totals():
    assert expenses.calculate_total([]) == 0
    assert expenses.calculate_total(as_items([19.99])) == 19.99


def test_index_page_shows_no_long_float_tail(tmp_path):
    app_module.app.config["DB_PATH"] = str(tmp_path / "bug.db")
    conn = expenses.get_connection(app_module.app.config["DB_PATH"])
    expenses.init_db(conn)
    # list_expenses is newest first, so insert in reverse to make the page sum
    # in the order 0.01, 33.33, 33.33, 33.33. Float addition depends on order.
    for amount in (33.33, 33.33, 33.33, 0.01):
        expenses.add_expense(conn, amount, "Test", "2026-09-01")
    conn.close()
    html = app_module.app.test_client().get("/").data.decode()
    assert "99.99999999999999" not in html

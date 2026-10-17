import pytest

import app as app_module
import expenses


@pytest.fixture
def client(tmp_path):
    app_module.app.config["DB_PATH"] = str(tmp_path / "test.db")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def add_expense(client, amount, category, date):
    conn = expenses.get_connection(app_module.app.config["DB_PATH"])
    expenses.init_db(conn)
    expenses.add_expense(conn, amount, category, date)
    conn.close()


def test_budgets_page_loads_for_current_month(client):
    resp = client.get("/budgets")
    assert resp.status_code == 200
    assert app_module.current_month().encode() in resp.data


def test_post_budget_then_page_shows_it(client):
    resp = client.post(
        "/budgets",
        data={"category": "Dining", "month": "2026-09", "amount": "100"},
    )
    assert resp.status_code == 302
    page = client.get("/budgets?month=2026-09")
    assert b"Dining" in page.data
    assert b"100.0" in page.data


def test_over_budget_is_flagged_and_unbudgeted_is_not(client):
    client.post("/budgets", data={"category": "Dining", "month": "2026-09", "amount": "50"})
    add_expense(client, 80, "Dining", "2026-09-03")
    add_expense(client, 500, "Travel", "2026-09-04")
    html = client.get("/budgets?month=2026-09").data.decode()
    assert html.count("OVER") == 1
    assert "no budget" in html
    travel_row = html[html.index("Travel"):].split("</tr>")[0]
    assert "OVER" not in travel_row


def test_post_with_bad_amount_shows_error_and_does_not_crash(client):
    resp = client.post(
        "/budgets",
        data={"category": "Dining", "month": "2026-09", "amount": "-5"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"greater than zero" in resp.data


def test_bad_month_in_query_shows_error_and_falls_back(client):
    resp = client.get("/budgets?month=nonsense")
    assert resp.status_code == 200
    assert b"YYYY-MM" in resp.data
    assert app_module.current_month().encode() in resp.data


def test_index_links_to_budgets(client):
    assert b"/budgets" in client.get("/").data

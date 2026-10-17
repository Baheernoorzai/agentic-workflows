import pytest

import app as app_module
import expenses


@pytest.fixture
def client(tmp_path):
    app_module.app.config["DB_PATH"] = str(tmp_path / "test.db")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def add(client, amount, category, date):
    conn = expenses.get_connection(app_module.app.config["DB_PATH"])
    expenses.init_db(conn)
    new_id = expenses.add_expense(conn, amount, category, date)
    conn.close()
    return new_id


def all_ids():
    conn = expenses.get_connection(app_module.app.config["DB_PATH"])
    expenses.init_db(conn)
    found = [e["id"] for e in expenses.list_expenses(conn)]
    conn.close()
    return found


def test_post_delete_removes_the_expense_and_redirects(client):
    keep = add(client, 10, "Dining", "2026-09-01")
    gone = add(client, 20, "Transport", "2026-09-02")
    resp = client.post(f"/delete/{gone}")
    assert resp.status_code == 302
    assert all_ids() == [keep]


def test_deleted_expense_disappears_from_page_and_total_updates(client):
    add(client, 10, "Dining", "2026-09-01")
    gone = add(client, 20.5, "Transport", "2026-09-02")
    html = client.get("/").data.decode()
    assert "Transport" in html and "30.50" in html
    html = client.post(f"/delete/{gone}", follow_redirects=True).data.decode()
    assert "Transport" not in html
    assert "10.00" in html and "30.50" not in html


def test_delete_unknown_id_shows_error_and_changes_nothing(client):
    keep = add(client, 10, "Dining", "2026-09-01")
    resp = client.post("/delete/9999", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Expense not found" in resp.data
    assert all_ids() == [keep]


def test_get_on_delete_url_is_not_allowed(client):
    keep = add(client, 10, "Dining", "2026-09-01")
    assert client.get(f"/delete/{keep}").status_code == 405
    assert all_ids() == [keep]


def test_non_numeric_id_is_a_404(client):
    assert client.post("/delete/abc").status_code == 404


def test_every_row_has_a_delete_form_with_a_confirmation(client):
    first = add(client, 10, "Dining", "2026-09-01")
    second = add(client, 20, "Transport", "2026-09-02")
    html = client.get("/").data.decode()
    assert f'action="/delete/{first}"' in html
    assert f'action="/delete/{second}"' in html
    assert html.count("confirm(") == 2
    assert 'method="post"' in html


def test_empty_state_has_no_delete_button(client):
    html = client.get("/").data.decode()
    assert "No expenses yet" in html
    assert "/delete/" not in html


def test_deleting_updates_budget_status(client):
    conn = expenses.get_connection(app_module.app.config["DB_PATH"])
    expenses.init_db(conn)
    expenses.set_budget(conn, "Dining", "2026-09", 100)
    conn.close()
    big = add(client, 150, "Dining", "2026-09-05")
    assert client.get("/budgets?month=2026-09").data.decode().count("OVER") == 1
    client.post(f"/delete/{big}")
    assert client.get("/budgets?month=2026-09").data.decode().count("OVER") == 0

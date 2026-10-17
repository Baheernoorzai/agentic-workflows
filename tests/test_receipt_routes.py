import io
import os

import pytest

import app as app_module
import expenses
import receipts

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture
def client(tmp_path):
    app_module.app.config["DB_PATH"] = str(tmp_path / "test.db")
    app_module.app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def db():
    conn = expenses.get_connection(app_module.app.config["DB_PATH"])
    expenses.init_db(conn)
    return conn


def add(amount=10, category="Dining", date="2026-09-01"):
    conn = db()
    new_id = expenses.add_expense(conn, amount, category, date)
    conn.close()
    return new_id


def upload(client, expense_id, data=PDF, name="lunch.pdf", **kw):
    return client.post(
        f"/expenses/{expense_id}/receipt",
        data={"receipt": (io.BytesIO(data), name)},
        content_type="multipart/form-data",
        **kw,
    )


def stored_files():
    d = app_module.app.config["UPLOAD_DIR"]
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def receipt_rows():
    conn = db()
    found = conn.execute("SELECT * FROM receipts").fetchall()
    conn.close()
    return found


def test_upload_stores_receipt_and_redirects(client):
    eid = add()
    resp = upload(client, eid)
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    assert len(receipt_rows()) == 1
    assert len(stored_files()) == 1


def test_page_shows_view_link_after_upload(client):
    eid = add()
    upload(client, eid)
    rid = receipt_rows()[0]["id"]
    page = client.get("/").get_data(as_text=True)
    assert f"/receipts/{rid}" in page
    assert "View PDF" in page
    assert "Replace" in page


def test_page_offers_attach_when_no_receipt(client):
    add()
    page = client.get("/").get_data(as_text=True)
    assert "Attach PDF" in page
    assert "View PDF" not in page
    assert 'enctype="multipart/form-data"' in page


def test_view_serves_the_pdf_inline_with_safe_headers(client):
    eid = add()
    upload(client, eid)
    rid = receipt_rows()[0]["id"]
    resp = client.get(f"/receipts/{rid}")
    assert resp.status_code == 200
    assert resp.data == PDF
    assert resp.mimetype == "application/pdf"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Content-Disposition"].startswith("inline")
    assert "lunch.pdf" in resp.headers["Content-Disposition"]


def test_view_unknown_receipt_is_404(client):
    assert client.get("/receipts/9999").status_code == 404


def test_view_non_numeric_id_is_404(client):
    assert client.get("/receipts/abc").status_code == 404
    assert client.get("/receipts/..%2F..%2Fapp.py").status_code == 404


def test_view_when_file_is_missing_is_404(client):
    eid = add()
    upload(client, eid)
    rid = receipt_rows()[0]["id"]
    os.remove(os.path.join(app_module.app.config["UPLOAD_DIR"], stored_files()[0]))
    assert client.get(f"/receipts/{rid}").status_code == 404


def test_upload_to_unknown_expense_shows_error_and_stores_nothing(client):
    resp = upload(client, 9999)
    assert resp.status_code == 302
    assert "Expense+not+found" in resp.headers["Location"]
    assert receipt_rows() == []
    assert stored_files() == []


def test_non_pdf_is_rejected(client):
    eid = add()
    resp = upload(client, eid, data=b"<html></html>", name="a.pdf")
    assert "not+a+valid+PDF" in resp.headers["Location"]
    resp = upload(client, eid, data=PDF, name="a.txt")
    assert "PDF+file" in resp.headers["Location"]
    assert receipt_rows() == []
    assert stored_files() == []


def test_error_message_is_shown_on_the_page(client):
    eid = add()
    resp = upload(client, eid, data=b"nope", name="a.pdf")
    page = client.get(resp.headers["Location"]).get_data(as_text=True)
    assert "not a valid PDF" in page


def test_missing_file_field_shows_error(client):
    eid = add()
    resp = client.post(f"/expenses/{eid}/receipt", data={}, content_type="multipart/form-data")
    assert "Choose+a+PDF" in resp.headers["Location"]


def test_empty_filename_shows_error(client):
    eid = add()
    resp = upload(client, eid, data=b"", name="")
    assert "Choose+a+PDF" in resp.headers["Location"]


def test_file_over_the_limit_is_rejected(client):
    eid = add()
    big = PDF + b"0" * (receipts.MAX_BYTES - len(PDF) + 1)
    resp = upload(client, eid, data=big)
    assert resp.status_code == 302
    assert "too+large" in resp.headers["Location"]
    assert receipt_rows() == []
    assert stored_files() == []


def test_request_far_over_the_limit_gets_a_friendly_redirect(client):
    eid = add()
    huge = PDF + b"0" * (receipts.MAX_BYTES + 2 * 1024 * 1024)
    resp = upload(client, eid, data=huge)
    assert resp.status_code == 302
    assert "too+large" in resp.headers["Location"]
    assert stored_files() == []


def test_get_on_upload_route_is_405(client):
    eid = add()
    assert client.get(f"/expenses/{eid}/receipt").status_code == 405


def test_second_upload_replaces_the_first(client):
    eid = add()
    upload(client, eid, name="one.pdf")
    upload(client, eid, data=PDF + b"x", name="two.pdf")
    assert len(receipt_rows()) == 1
    assert len(stored_files()) == 1
    page = client.get("/").get_data(as_text=True)
    assert "two.pdf" in page
    assert "one.pdf" not in page


def test_receipts_stay_with_their_own_expense(client):
    a = add(category="Dining")
    b = add(category="Transport")
    upload(client, a, name="a.pdf")
    page = client.get("/").get_data(as_text=True)
    assert page.count("View PDF") == 1
    assert page.count("Attach PDF") == 1
    assert b != a


def test_original_filename_is_never_used_on_disk(client):
    eid = add()
    upload(client, eid, name="../../evil.pdf")
    assert stored_files()[0] != "evil.pdf"
    assert not os.path.exists(os.path.join(app_module.app.root_path, "evil.pdf"))


def test_filename_is_escaped_on_the_page(client):
    eid = add()
    upload(client, eid, name="<script>alert(1)</script>.pdf")
    page = client.get("/").get_data(as_text=True)
    assert "<script>alert(1)" not in page


# deleting an expense removes its receipt

def test_deleting_an_expense_removes_its_receipt_row_and_file(client):
    eid = add()
    upload(client, eid)
    assert client.post(f"/delete/{eid}").status_code == 302
    assert receipt_rows() == []
    assert stored_files() == []


def test_deleting_an_expense_keeps_other_receipts(client):
    a = add(category="Dining")
    b = add(category="Transport")
    upload(client, a)
    upload(client, b)
    client.post(f"/delete/{a}")
    assert len(receipt_rows()) == 1
    assert receipt_rows()[0]["expense_id"] == b
    assert len(stored_files()) == 1


def test_deleting_an_expense_without_a_receipt_still_works(client):
    eid = add()
    assert client.post(f"/delete/{eid}").status_code == 302
    assert receipt_rows() == []


def test_deleting_an_unknown_expense_leaves_receipts_alone(client):
    eid = add()
    upload(client, eid)
    client.post("/delete/9999")
    assert len(receipt_rows()) == 1
    assert len(stored_files()) == 1


def test_receipt_url_is_gone_after_the_expense_is_deleted(client):
    eid = add()
    upload(client, eid)
    rid = receipt_rows()[0]["id"]
    client.post(f"/delete/{eid}")
    assert client.get(f"/receipts/{rid}").status_code == 404

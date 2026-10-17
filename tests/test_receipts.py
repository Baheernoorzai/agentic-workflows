import os

import pytest

import expenses
import receipts

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@pytest.fixture
def conn():
    c = expenses.get_connection(":memory:")
    expenses.init_db(c)
    yield c
    c.close()


@pytest.fixture
def updir(tmp_path):
    return str(tmp_path / "uploads")


@pytest.fixture
def eid(conn):
    return expenses.add_expense(conn, 12.5, "Dining", "2026-09-01")


def files(updir):
    return sorted(os.listdir(updir)) if os.path.isdir(updir) else []


def rows(conn):
    return conn.execute("SELECT * FROM receipts").fetchall()


# validation

def test_valid_pdf_passes():
    assert receipts.validate_pdf("lunch.pdf", PDF) == "lunch.pdf"


def test_extension_check_is_case_insensitive():
    assert receipts.validate_pdf("LUNCH.PDF", PDF) == "LUNCH.PDF"


@pytest.mark.parametrize("name", ["lunch.txt", "lunch", "lunch.pdf.exe", "lunch.png"])
def test_wrong_extension_rejected(name):
    with pytest.raises(ValueError, match="PDF file"):
        receipts.validate_pdf(name, PDF)


@pytest.mark.parametrize("name", [None, "", "   "])
def test_missing_filename_rejected(name):
    with pytest.raises(ValueError, match="Choose a PDF"):
        receipts.validate_pdf(name, PDF)


def test_empty_file_rejected():
    with pytest.raises(ValueError, match="empty"):
        receipts.validate_pdf("a.pdf", b"")


def test_wrong_magic_bytes_rejected():
    with pytest.raises(ValueError, match="not a valid PDF"):
        receipts.validate_pdf("a.pdf", b"<html>hi</html>")


def test_magic_must_be_at_the_start():
    with pytest.raises(ValueError, match="not a valid PDF"):
        receipts.validate_pdf("a.pdf", b"  %PDF-1.4")


def test_size_limit_is_inclusive():
    ok = PDF + b"0" * (receipts.MAX_BYTES - len(PDF))
    assert len(ok) == receipts.MAX_BYTES
    receipts.validate_pdf("a.pdf", ok)
    with pytest.raises(ValueError, match="too large"):
        receipts.validate_pdf("a.pdf", ok + b"0")


def test_path_parts_are_stripped_from_the_name():
    assert receipts.validate_pdf("../../etc/evil.pdf", PDF) == "evil.pdf"
    assert receipts.validate_pdf("C:\\temp\\evil.pdf", PDF) == "evil.pdf"


def test_control_characters_are_stripped_from_the_name():
    assert receipts.validate_pdf("a\x00b\nc.pdf", PDF) == "abc.pdf"


def test_long_names_are_capped_then_checked():
    with pytest.raises(ValueError, match="PDF file"):
        receipts.validate_pdf("a" * 500 + ".pdf", PDF)
    assert len(receipts.validate_pdf("a" * 150 + ".pdf", PDF)) == 154


# saving

def test_save_stores_row_and_file(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "lunch.pdf", PDF)
    rec = receipts.get_receipt(conn, rid)
    assert rec["expense_id"] == eid
    assert rec["original_name"] == "lunch.pdf"
    assert rec["size_bytes"] == len(PDF)
    assert files(updir) == [rec["stored_name"]]
    with open(os.path.join(updir, rec["stored_name"]), "rb") as f:
        assert f.read() == PDF


def test_stored_name_is_random_and_ignores_the_uploaded_name(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "../../evil.pdf", PDF)
    stored = receipts.get_receipt(conn, rid)["stored_name"]
    assert "evil" not in stored
    assert os.sep not in stored and "/" not in stored
    assert stored.endswith(".pdf")


def test_two_expenses_get_different_stored_names(conn, updir, eid):
    other = expenses.add_expense(conn, 5, "Dining", "2026-09-02")
    a = receipts.get_receipt(conn, receipts.save_receipt(conn, updir, eid, "a.pdf", PDF))
    b = receipts.get_receipt(conn, receipts.save_receipt(conn, updir, other, "a.pdf", PDF))
    assert a["stored_name"] != b["stored_name"]
    assert len(files(updir)) == 2


def test_upload_directory_is_created_when_missing(conn, updir, eid):
    assert not os.path.isdir(updir)
    receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    assert os.path.isdir(updir)


def test_invalid_file_writes_nothing(conn, updir, eid):
    with pytest.raises(ValueError):
        receipts.save_receipt(conn, updir, eid, "a.pdf", b"nope")
    assert rows(conn) == []
    assert files(updir) == []


def test_unknown_expense_writes_nothing(conn, updir):
    with pytest.raises(ValueError, match="Expense not found"):
        receipts.save_receipt(conn, updir, 9999, "a.pdf", PDF)
    assert rows(conn) == []
    assert files(updir) == []


def test_second_upload_replaces_the_first(conn, updir, eid):
    first = receipts.save_receipt(conn, updir, eid, "one.pdf", PDF)
    old_stored = receipts.get_receipt(conn, first)["stored_name"]
    second = receipts.save_receipt(conn, updir, eid, "two.pdf", PDF + b"more")
    assert len(rows(conn)) == 1
    assert receipts.get_receipt(conn, first) is None
    rec = receipts.get_receipt(conn, second)
    assert rec["original_name"] == "two.pdf"
    assert files(updir) == [rec["stored_name"]]
    assert old_stored not in files(updir)


def test_failed_database_write_removes_the_new_file(conn, updir, eid, monkeypatch):
    class Boom:
        def __init__(self, real):
            self.real = real

        def execute(self, sql, *args):
            if sql.startswith("INSERT INTO receipts"):
                raise RuntimeError("disk full")
            return self.real.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self.real, name)

    with pytest.raises(RuntimeError):
        receipts.save_receipt(Boom(conn), updir, eid, "a.pdf", PDF)
    assert files(updir) == []


def test_failed_replacement_keeps_the_old_receipt(conn, updir, eid):
    first = receipts.save_receipt(conn, updir, eid, "one.pdf", PDF)

    class Boom:
        def __init__(self, real):
            self.real = real

        def execute(self, sql, *args):
            if sql.startswith("INSERT INTO receipts"):
                raise RuntimeError("disk full")
            return self.real.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self.real, name)

    with pytest.raises(RuntimeError):
        receipts.save_receipt(Boom(conn), updir, eid, "two.pdf", PDF)
    assert receipts.get_receipt(conn, first)["original_name"] == "one.pdf"
    assert len(files(updir)) == 1
    assert receipts.read_receipt(conn, updir, first) is not None


# reading

def test_read_returns_record_and_bytes(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    rec, data = receipts.read_receipt(conn, updir, rid)
    assert data == PDF
    assert rec["id"] == rid


def test_read_unknown_id_is_none(conn, updir):
    assert receipts.read_receipt(conn, updir, 9999) is None
    assert receipts.get_receipt(conn, 9999) is None


def test_read_with_missing_file_is_none(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    os.remove(os.path.join(updir, files(updir)[0]))
    assert receipts.read_receipt(conn, updir, rid) is None


# deleting

def test_delete_removes_row_and_file(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    assert receipts.delete_receipt(conn, updir, rid) is True
    assert rows(conn) == []
    assert files(updir) == []


def test_delete_unknown_id_is_false(conn, updir):
    assert receipts.delete_receipt(conn, updir, 9999) is False


def test_delete_twice_second_is_false(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    receipts.delete_receipt(conn, updir, rid)
    assert receipts.delete_receipt(conn, updir, rid) is False


def test_delete_still_works_if_the_file_is_already_gone(conn, updir, eid):
    rid = receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    os.remove(os.path.join(updir, files(updir)[0]))
    assert receipts.delete_receipt(conn, updir, rid) is True
    assert rows(conn) == []


def test_delete_only_touches_that_receipt(conn, updir, eid):
    other = expenses.add_expense(conn, 5, "Dining", "2026-09-02")
    a = receipts.save_receipt(conn, updir, eid, "a.pdf", PDF)
    b = receipts.save_receipt(conn, updir, other, "b.pdf", PDF)
    receipts.delete_receipt(conn, updir, a)
    assert receipts.get_receipt(conn, b) is not None
    assert len(files(updir)) == 1


# schema

def test_init_db_is_safe_to_run_twice(conn):
    expenses.init_db(conn)
    expenses.init_db(conn)
    assert rows(conn) == []

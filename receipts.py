"""PDF receipt storage for expenses.

This module has no Flask imports so it can be unit tested directly. The
database holds the metadata and the PDF bytes live as files in an upload
directory that the caller passes in. Files are stored under random names, so
the name a user uploaded never decides where anything is written.

Files are never opened or parsed as PDFs. We only check the size, the file
extension and the "%PDF-" magic bytes at the start.
"""
import os
import uuid
from datetime import datetime

MAX_BYTES = 5 * 1024 * 1024
PDF_MAGIC = b"%PDF-"
MAX_NAME_LENGTH = 200


def _clean_name(filename):
    """The base name only, without control characters, capped in length."""
    name = (filename or "").replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:MAX_NAME_LENGTH]


def validate_pdf(filename, data):
    """Raise ValueError with a user readable message if this is not an acceptable PDF."""
    name = _clean_name(filename)
    if not name:
        raise ValueError("Choose a PDF file to upload")
    if not name.lower().endswith(".pdf"):
        raise ValueError("Receipt must be a PDF file")
    if not data:
        raise ValueError("The file is empty")
    if len(data) > MAX_BYTES:
        raise ValueError("Receipt is too large (5 MB maximum)")
    if not data.startswith(PDF_MAGIC):
        raise ValueError("That file is not a valid PDF")
    return name


def _path(upload_dir, stored_name):
    return os.path.join(upload_dir, stored_name)


def _remove_file(upload_dir, stored_name):
    try:
        os.remove(_path(upload_dir, stored_name))
    except FileNotFoundError:
        pass


def get_receipt(conn, receipt_id):
    """The receipt record (a dict) for this receipt id, or None."""
    row = conn.execute(
        "SELECT id, expense_id, original_name, stored_name, size_bytes, uploaded_at "
        "FROM receipts WHERE id = ?",
        (receipt_id,),
    ).fetchone()
    return dict(row) if row else None


def save_receipt(conn, upload_dir, expense_id, filename, data):
    """Validate and store a PDF receipt for an expense. Returns the receipt id.

    An expense has at most one receipt, so uploading again replaces the old
    one. Raises ValueError if the file is not acceptable or the expense does
    not exist, and in that case nothing is written.
    """
    name = validate_pdf(filename, data)
    exists = conn.execute(
        "SELECT 1 FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    if not exists:
        raise ValueError("Expense not found")

    old = conn.execute(
        "SELECT stored_name FROM receipts WHERE expense_id = ?", (expense_id,)
    ).fetchone()

    os.makedirs(upload_dir, exist_ok=True)
    stored_name = uuid.uuid4().hex + ".pdf"
    with open(_path(upload_dir, stored_name), "wb") as f:
        f.write(data)

    try:
        conn.execute("DELETE FROM receipts WHERE expense_id = ?", (expense_id,))
        cur = conn.execute(
            "INSERT INTO receipts (expense_id, original_name, stored_name, size_bytes, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (expense_id, name, stored_name, len(data),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        _remove_file(upload_dir, stored_name)
        raise

    if old:
        _remove_file(upload_dir, old["stored_name"])
    return cur.lastrowid


def read_receipt(conn, upload_dir, receipt_id):
    """Returns (record, pdf_bytes), or None if there is no such receipt or its file is gone."""
    record = get_receipt(conn, receipt_id)
    if record is None:
        return None
    try:
        with open(_path(upload_dir, record["stored_name"]), "rb") as f:
            return record, f.read()
    except FileNotFoundError:
        return None


def delete_receipt(conn, upload_dir, receipt_id):
    """Delete a receipt row and its file. Returns True if a receipt was deleted."""
    record = get_receipt(conn, receipt_id)
    if record is None:
        return False
    conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
    conn.commit()
    _remove_file(upload_dir, record["stored_name"])
    return True

"""Flask web layer. Business logic lives in expenses.py."""
import io
import os
from datetime import date

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

import expenses
import receipts

app = Flask(__name__)
app.config["DB_PATH"] = expenses.DEFAULT_DB
app.config["UPLOAD_DIR"] = os.path.join(app.root_path, "uploads")
# Reject oversized requests early; the extra room covers the form overhead.
app.config["MAX_CONTENT_LENGTH"] = receipts.MAX_BYTES + 1024 * 1024


def get_conn():
    conn = expenses.get_connection(app.config["DB_PATH"])
    expenses.init_db(conn)
    return conn


@app.route("/")
def index():
    conn = get_conn()
    try:
        items = expenses.list_expenses(conn)
        receipt_map = receipts.receipts_by_expense(conn)
    finally:
        conn.close()
    total = expenses.calculate_total(items)
    return render_template(
        "index.html",
        expenses=items,
        receipts=receipt_map,
        total=total,
        error=request.args.get("error"),
    )


@app.route("/add", methods=["POST"])
def add():
    conn = get_conn()
    try:
        expenses.add_expense(
            conn,
            request.form.get("amount"),
            request.form.get("category"),
            request.form.get("date"),
            request.form.get("note"),
        )
    except ValueError as exc:
        return redirect(url_for("index", error=str(exc)))
    finally:
        conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    conn = get_conn()
    try:
        receipts.delete_for_expense(conn, app.config["UPLOAD_DIR"], expense_id)
        deleted = expenses.delete_expense(conn, expense_id)
    finally:
        conn.close()
    if not deleted:
        return redirect(url_for("index", error="Expense not found"))
    return redirect(url_for("index"))


@app.route("/expenses/<int:expense_id>/receipt", methods=["POST"])
def upload_receipt(expense_id):
    upload = request.files.get("receipt")
    if upload is None or not upload.filename:
        return redirect(url_for("index", error="Choose a PDF file to upload"))
    data = upload.read(receipts.MAX_BYTES + 1)
    conn = get_conn()
    try:
        receipts.save_receipt(
            conn, app.config["UPLOAD_DIR"], expense_id, upload.filename, data
        )
    except ValueError as exc:
        return redirect(url_for("index", error=str(exc)))
    finally:
        conn.close()
    return redirect(url_for("index"))


@app.errorhandler(413)
def too_large(_exc):
    return redirect(url_for("index", error="Receipt is too large (5 MB maximum)"))


@app.route("/receipts/<int:receipt_id>")
def view_receipt(receipt_id):
    conn = get_conn()
    try:
        found = receipts.read_receipt(conn, app.config["UPLOAD_DIR"], receipt_id)
    finally:
        conn.close()
    if found is None:
        abort(404)
    record, data = found
    resp = send_file(
        io.BytesIO(data),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=record["original_name"],
    )
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@app.route("/report")
def report():
    conn = get_conn()
    try:
        items = expenses.list_expenses(conn)
    finally:
        conn.close()
    return render_template("report.html", report=expenses.monthly_report(items))


def current_month():
    return date.today().strftime("%Y-%m")


@app.route("/budgets")
def budgets():
    month = request.args.get("month") or current_month()
    error = request.args.get("error")
    conn = get_conn()
    try:
        try:
            status = expenses.budget_status(conn, month)
        except ValueError as exc:
            error = str(exc)
            month = current_month()
            status = expenses.budget_status(conn, month)
    finally:
        conn.close()
    return render_template("budgets.html", month=month, status=status, error=error)


@app.route("/budgets", methods=["POST"])
def set_budget():
    month = request.form.get("month")
    conn = get_conn()
    try:
        expenses.set_budget(
            conn,
            request.form.get("category"),
            month,
            request.form.get("amount"),
        )
    except ValueError as exc:
        return redirect(url_for("budgets", month=month, error=str(exc)))
    finally:
        conn.close()
    return redirect(url_for("budgets", month=month))


if __name__ == "__main__":
    app.run(debug=True)

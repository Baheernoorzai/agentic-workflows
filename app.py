"""Flask web layer. Business logic lives in expenses.py."""
from datetime import date

from flask import Flask, redirect, render_template, request, url_for

import expenses

app = Flask(__name__)
app.config["DB_PATH"] = expenses.DEFAULT_DB


def get_conn():
    conn = expenses.get_connection(app.config["DB_PATH"])
    expenses.init_db(conn)
    return conn


@app.route("/")
def index():
    conn = get_conn()
    try:
        items = expenses.list_expenses(conn)
    finally:
        conn.close()
    total = expenses.calculate_total(items)
    return render_template(
        "index.html",
        expenses=items,
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
        deleted = expenses.delete_expense(conn, expense_id)
    finally:
        conn.close()
    if not deleted:
        return redirect(url_for("index", error="Expense not found"))
    return redirect(url_for("index"))


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

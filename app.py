"""Flask web layer. Business logic lives in expenses.py."""
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


@app.route("/report")
def report():
    conn = get_conn()
    try:
        items = expenses.list_expenses(conn)
    finally:
        conn.close()
    return render_template("report.html", report=expenses.monthly_report(items))


if __name__ == "__main__":
    app.run(debug=True)

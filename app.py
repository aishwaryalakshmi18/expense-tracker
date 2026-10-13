from flask import Flask, render_template, request, redirect, url_for, flash, Response
import sqlite3
import os
import csv
import calendar
from io import StringIO
from datetime import date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-before-deploying")

# Use DATABASE_PATH on the hosting service if configured; otherwise use local SQLite.
DB = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "expenses.db")
)

CATEGORIES = ["Food", "Travel", "Bills", "Shopping", "Education", "Healthcare", "Other"]
STATUSES = ["Paid", "Pending", "Needs Review", "Not Applicable"]
FREQUENCIES = ["weekly", "monthly", "quarterly", "yearly"]


def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db():
    # Create the database directory when DATABASE_PATH points to a separate folder.
    os.makedirs(os.path.dirname(os.path.abspath(DB)), exist_ok=True)

    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS expenses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
          amount REAL NOT NULL, category TEXT NOT NULL, expense_date TEXT NOT NULL,
          notes TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Paid',
          recurring_id INTEGER, occurrence_key TEXT UNIQUE);

        CREATE TABLE IF NOT EXISTS budgets(
          id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
          month TEXT NOT NULL, limit_amount REAL NOT NULL, UNIQUE(category,month));

        CREATE TABLE IF NOT EXISTS recurring(
          id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, amount REAL NOT NULL,
          category TEXT NOT NULL, start_date TEXT NOT NULL, frequency TEXT NOT NULL,
          end_date TEXT, active INTEGER NOT NULL DEFAULT 1);
        """)


def shift_month(d, n):
    idx = d.year * 12 + d.month - 1 + n
    y, m = divmod(idx, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def scheduled_dates(rule):
    start = date.fromisoformat(rule["start_date"])
    end = date.fromisoformat(rule["end_date"]) if rule["end_date"] else None
    today = date.today()
    dates, i = [], 0

    while True:
        if rule["frequency"] == "weekly":
            due = date.fromordinal(start.toordinal() + i * 7)
        elif rule["frequency"] == "monthly":
            due = shift_month(start, i)
        elif rule["frequency"] == "quarterly":
            due = shift_month(start, i * 3)
        else:
            due = shift_month(start, i * 12)

        if due > today or (end and due > end):
            break

        dates.append(due)
        i += 1
        if i > 5000:
            break

    return dates


def reconcile():
    with connect() as db:
        rules = db.execute("SELECT * FROM recurring WHERE active=1").fetchall()

        for rule in rules:
            for due in scheduled_dates(rule):
                key = f'{rule["id"]}:{due.isoformat()}'
                db.execute(
                    """INSERT OR IGNORE INTO expenses
                       (title, amount, category, expense_date, notes, status,
                        recurring_id, occurrence_key)
                       VALUES (?, ?, ?, ?, ?, 'Needs Review', ?, ?)""",
                    (
                        rule["title"],
                        rule["amount"],
                        rule["category"],
                        due.isoformat(),
                        "Scheduled recurring payment — please review",
                        rule["id"],
                        key,
                    ),
                )


def money(v):
    return "₹{:,.2f}".format(float(v or 0))


@app.context_processor
def globals_for_templates():
    return {
        "categories": CATEGORIES,
        "today": date.today().isoformat(),
        "money": money,
    }


# Initialize tables when this module is imported by Gunicorn as well as when run directly.
init_db()


@app.before_request
def auto_reconcile():
    reconcile()


@app.route("/")
def dashboard():
    month = request.args.get("month", date.today().strftime("%Y-%m"))

    with connect() as db:
        expenses = db.execute(
            """SELECT * FROM expenses
               WHERE substr(expense_date, 1, 7)=?
               ORDER BY expense_date DESC, id DESC""",
            (month,),
        ).fetchall()

        recent = db.execute(
            "SELECT * FROM expenses ORDER BY expense_date DESC, id DESC LIMIT 8"
        ).fetchall()

        cats = db.execute(
            """SELECT category, SUM(amount) total FROM expenses
               WHERE substr(expense_date, 1, 7)=? AND status='Paid'
               GROUP BY category ORDER BY total DESC""",
            (month,),
        ).fetchall()

        budgets = db.execute(
            "SELECT SUM(limit_amount) total FROM budgets WHERE month=?",
            (month,),
        ).fetchone()["total"] or 0

        review = db.execute(
            "SELECT COUNT(*) n FROM expenses WHERE status IN ('Needs Review','Pending')"
        ).fetchone()["n"]

    paid = sum(x["amount"] for x in expenses if x["status"] == "Paid")
    pending = sum(
        x["amount"] for x in expenses
        if x["status"] in ("Needs Review", "Pending")
    )

    return render_template(
        "dashboard.html",
        month=month,
        expenses=expenses,
        recent=recent,
        cats=cats,
        paid=paid,
        pending=pending,
        budget=budgets,
        remaining=budgets - paid,
        review=review,
    )


@app.route("/transactions")
def transactions():
    month = request.args.get("month", "")
    category = request.args.get("category", "")
    sql, args = "SELECT * FROM expenses WHERE 1=1", []

    if month:
        sql += " AND substr(expense_date,1,7)=?"
        args.append(month)

    if category:
        sql += " AND category=?"
        args.append(category)

    with connect() as db:
        rows = db.execute(
            sql + " ORDER BY expense_date DESC, id DESC", args
        ).fetchall()

    return render_template(
        "transactions.html",
        rows=rows,
        month=month,
        selected_category=category,
    )


@app.route("/transaction/add", methods=["GET", "POST"])
@app.route("/transaction/<int:eid>/edit", methods=["GET", "POST"])
def transaction_form(eid=None):
    with connect() as db:
        item = db.execute(
            "SELECT * FROM expenses WHERE id=?", (eid,)
        ).fetchone() if eid else None

        if eid and not item:
            flash("Transaction not found.", "error")
            return redirect(url_for("transactions"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            category = request.form.get("category", "")
            dt = request.form.get("expense_date", "")
            notes = request.form.get("notes", "").strip()
            status = request.form.get("status", "Paid")

            try:
                amount = float(request.form.get("amount", ""))
                date.fromisoformat(dt)

                if (
                    not title
                    or amount < 0
                    or category not in CATEGORIES
                    or status not in STATUSES
                ):
                    raise ValueError()
            except (ValueError, TypeError):
                flash("Please enter valid transaction details.", "error")
                return render_template("transaction_form.html", item=item)

            if item:
                db.execute(
                    """UPDATE expenses
                       SET title=?, amount=?, category=?, expense_date=?, notes=?, status=?
                       WHERE id=?""",
                    (title, amount, category, dt, notes, status, eid),
                )
            else:
                db.execute(
                    """INSERT INTO expenses
                       (title, amount, category, expense_date, notes, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (title, amount, category, dt, notes, status),
                )

            flash("Transaction saved.", "success")
            return redirect(url_for("transactions"))

    return render_template("transaction_form.html", item=item)


@app.post("/transaction/<int:eid>/delete")
def delete_transaction(eid):
    with connect() as db:
        db.execute("DELETE FROM expenses WHERE id=?", (eid,))

    flash("Transaction deleted.", "success")
    return redirect(request.referrer or url_for("transactions"))


@app.post("/transaction/<int:eid>/status")
def set_status(eid):
    status = request.form.get("status", "")

    if status in STATUSES:
        with connect() as db:
            db.execute("UPDATE expenses SET status=? WHERE id=?", (status, eid))
        flash("Status updated.", "success")

    return redirect(request.referrer or url_for("transactions"))


@app.route("/recurring", methods=["GET", "POST"])
def recurring():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "")
        start = request.form.get("start_date", "")
        end = request.form.get("end_date", "").strip() or None
        freq = request.form.get("frequency", "")

        try:
            amount = float(request.form.get("amount", ""))
            date.fromisoformat(start)

            if end:
                date.fromisoformat(end)

            if (
                not title
                or amount < 0
                or category not in CATEGORIES
                or freq not in FREQUENCIES
                or (end and end < start)
            ):
                raise ValueError()
        except (ValueError, TypeError):
            flash("Please complete all recurring fields correctly.", "error")
            return redirect(url_for("recurring"))

        with connect() as db:
            db.execute(
                """INSERT INTO recurring
                   (title, amount, category, start_date, frequency, end_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, amount, category, start, freq, end),
            )

        reconcile()
        flash(
            "Recurring payment created. Due records have been generated for review.",
            "success",
        )
        return redirect(url_for("recurring"))

    with connect() as db:
        rules = db.execute(
            "SELECT * FROM recurring ORDER BY active DESC, id DESC"
        ).fetchall()

    return render_template("recurring.html", rules=rules)


@app.post("/recurring/<int:rid>/toggle")
def toggle_recurring(rid):
    with connect() as db:
        db.execute("UPDATE recurring SET active=1-active WHERE id=?", (rid,))

    flash("Recurring rule updated.", "success")
    return redirect(url_for("recurring"))


@app.route("/needs-review")
def needs_review():
    with connect() as db:
        rows = db.execute(
            """SELECT * FROM expenses
               WHERE status IN ('Needs Review', 'Pending')
               ORDER BY expense_date, id"""
        ).fetchall()

    grouped = {}
    for row in rows:
        grouped.setdefault(row["expense_date"][:7], []).append(row)

    return render_template("needs_review.html", grouped=grouped, rows=rows)


@app.route("/budgets", methods=["GET", "POST"])
def budgets():
    month = request.values.get("month", date.today().strftime("%Y-%m"))

    if request.method == "POST":
        category = request.form.get("category", "")

        try:
            amount = float(request.form.get("limit_amount", ""))

            if category not in CATEGORIES or amount < 0:
                raise ValueError()

            with connect() as db:
                db.execute(
                    """INSERT INTO budgets(category, month, limit_amount)
                       VALUES (?, ?, ?)
                       ON CONFLICT(category, month)
                       DO UPDATE SET limit_amount=excluded.limit_amount""",
                    (category, month, amount),
                )

            flash("Budget saved.", "success")
        except (ValueError, TypeError):
            flash("Enter a valid budget amount.", "error")

        return redirect(url_for("budgets", month=month))

    with connect() as db:
        rows = db.execute(
            """SELECT b.*,
                      COALESCE((
                        SELECT SUM(e.amount) FROM expenses e
                        WHERE e.category=b.category
                          AND substr(e.expense_date,1,7)=b.month
                          AND e.status='Paid'
                      ), 0) spent
               FROM budgets b
               WHERE b.month=?
               ORDER BY b.category""",
            (month,),
        ).fetchall()

    return render_template("budgets.html", rows=rows, month=month)


@app.route("/analytics")
def analytics():
    month = request.args.get("month", date.today().strftime("%Y-%m"))

    with connect() as db:
        cats = db.execute(
            """SELECT category, SUM(amount) total FROM expenses
               WHERE substr(expense_date,1,7)=? AND status='Paid'
               GROUP BY category ORDER BY total DESC""",
            (month,),
        ).fetchall()

        trend = db.execute(
            """SELECT substr(expense_date,1,7) month, SUM(amount) total
               FROM expenses
               WHERE status='Paid'
               GROUP BY substr(expense_date,1,7)
               ORDER BY month DESC LIMIT 12"""
        ).fetchall()

    return render_template(
        "analytics.html", month=month, cats=cats, trend=list(reversed(trend))
    )


@app.route("/export.csv")
def export_csv():
    with connect() as db:
        rows = db.execute(
            """SELECT title, amount, category, expense_date, status, notes
               FROM expenses ORDER BY expense_date DESC"""
        ).fetchall()

    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["Title", "Amount INR", "Category", "Date", "Status", "Notes"])

    for r in rows:
        writer.writerow([
            r["title"],
            r["amount"],
            r["category"],
            r["expense_date"],
            r["status"],
            r["notes"],
        ])

    # UTF-8 BOM helps spreadsheet programs such as Excel detect UTF-8 correctly.
    return Response(
        "\ufeff" + out.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=expense_tracker.csv"
        },
    )


if __name__ == "__main__":
    # Debug mode is for local development only. Use Gunicorn for hosted deployment.
    app.run(debug=True)

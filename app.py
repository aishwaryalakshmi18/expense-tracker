from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from calendar import monthrange
from models import db, Expense, Budget, CATEGORIES

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
app.config["SECRET_KEY"] = "dev-secret-key"  # fine for a student project
db.init_app(app)


# ---------- Helper functions ----------

def current_month_bounds():
    today = date.today()
    start = date(today.year, today.month, 1)
    end_day = monthrange(today.year, today.month)[1]
    end = date(today.year, today.month, end_day)
    return start, end


def get_monthly_spent(category):
    start, end = current_month_bounds()
    total = (
        db.session.query(db.func.sum(Expense.amount))
        .filter(Expense.category == category)
        .filter(Expense.date >= start, Expense.date <= end)
        .scalar()
    )
    return total or 0


def check_recurring_expenses():
    """If a recurring expense hasn't been logged this month yet, auto-add it."""
    start, _ = current_month_bounds()
    recurring = Expense.query.filter_by(is_recurring=True, frequency="monthly").all()

    seen = set()
    for exp in recurring:
        key = (exp.category, exp.amount, exp.note)
        if key in seen:
            continue
        seen.add(key)

        already_logged_this_month = Expense.query.filter(
            Expense.category == exp.category,
            Expense.amount == exp.amount,
            Expense.note == exp.note,
            Expense.date >= start,
        ).first()

        if not already_logged_this_month:
            new_exp = Expense(
                amount=exp.amount,
                category=exp.category,
                date=start,
                note=exp.note,
                is_recurring=True,
                frequency="monthly",
            )
            db.session.add(new_exp)

    db.session.commit()


# ---------- Routes ----------

@app.route("/")
def dashboard():
    check_recurring_expenses()

    budgets = Budget.query.all()
    budget_data = []
    for b in budgets:
        spent = get_monthly_spent(b.category)
        pct = round((spent / b.monthly_limit) * 100, 1) if b.monthly_limit > 0 else 0
        if pct >= 100:
            status = "over"
        elif pct >= 80:
            status = "warning"
        else:
            status = "ok"
        budget_data.append(
            {
                "category": b.category,
                "limit": b.monthly_limit,
                "spent": spent,
                "pct": min(pct, 100),
                "raw_pct": pct,
                "status": status,
            }
        )

    chart_labels = [b["category"] for b in budget_data]
    chart_values = [b["spent"] for b in budget_data]

    return render_template(
        "dashboard.html",
        budget_data=budget_data,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@app.route("/expenses")
def expenses():
    category = request.args.get("category", "")
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")

    query = Expense.query

    if category:
        query = query.filter_by(category=category)
    if start_date:
        query = query.filter(Expense.date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        query = query.filter(Expense.date <= datetime.strptime(end_date, "%Y-%m-%d").date())

    all_expenses = query.order_by(Expense.date.desc()).all()

    return render_template(
        "expenses.html",
        expenses=all_expenses,
        categories=CATEGORIES,
        selected_category=category,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        exp_date = request.form.get("date")
        note = request.form.get("note", "")
        is_recurring = bool(request.form.get("is_recurring"))

        errors = []
        try:
            amount_val = float(amount)
            if amount_val <= 0:
                errors.append("Amount must be greater than zero.")
        except (TypeError, ValueError):
            errors.append("Amount must be a valid number.")

        if category not in CATEGORIES:
            errors.append("Please select a valid category.")

        if not exp_date:
            errors.append("Date is required.")

        if errors:
            for e in errors:
                flash(e)
            return render_template("add_expense.html", categories=CATEGORIES)

        new_expense = Expense(
            amount=amount_val,
            category=category,
            date=datetime.strptime(exp_date, "%Y-%m-%d").date(),
            note=note,
            is_recurring=is_recurring,
            frequency="monthly" if is_recurring else None,
        )
        db.session.add(new_expense)
        db.session.commit()
        flash("Expense added.")
        return redirect(url_for("expenses"))

    return render_template("add_expense.html", categories=CATEGORIES)


@app.route("/delete-expense/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    db.session.delete(exp)
    db.session.commit()
    flash("Expense deleted.")
    return redirect(url_for("expenses"))


@app.route("/set-budget", methods=["GET", "POST"])
def set_budget():
    if request.method == "POST":
        category = request.form.get("category")
        limit = request.form.get("monthly_limit")

        errors = []
        try:
            limit_val = float(limit)
            if limit_val <= 0:
                errors.append("Budget limit must be greater than zero.")
        except (TypeError, ValueError):
            errors.append("Budget limit must be a valid number.")

        if category not in CATEGORIES:
            errors.append("Please select a valid category.")

        if errors:
            for e in errors:
                flash(e)
            return redirect(url_for("set_budget"))

        existing = Budget.query.filter_by(category=category).first()
        if existing:
            existing.monthly_limit = limit_val
        else:
            db.session.add(Budget(category=category, monthly_limit=limit_val))
        db.session.commit()
        flash("Budget saved.")
        return redirect(url_for("dashboard"))

    budgets = Budget.query.all()
    return render_template("set_budget.html", categories=CATEGORIES, budgets=budgets)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

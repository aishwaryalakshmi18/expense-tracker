from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

CATEGORIES = ["Food", "Travel", "Bills", "Shopping", "Other"]


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    note = db.Column(db.String(200))
    is_recurring = db.Column(db.Boolean, default=False)
    frequency = db.Column(db.String(20)) 

    def __repr__(self):
        return f"<Expense {self.category} {self.amount}>"


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), unique=True, nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Budget {self.category} {self.monthly_limit}>"


import app

with app.connect() as db:
    for table in ["expenses", "budgets", "recurring"]:
        print(f"\n{table.upper()} TABLE:")
        columns = db.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        for column in columns:
            print("-", column["name"])

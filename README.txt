EXPENSE TRACKER — FLASK + SQLITE

FEATURES
- Dashboard with summary cards and interactive category doughnut chart.
- INR formatting using the Indian numbering style.
- Add, edit, delete, and filter transactions.
- Category budgets and budget-versus-paid-spending view.
- Recurring schedules: weekly, monthly, quarterly, yearly.
- Missed scheduled periods are created as "Needs Review", never automatically as Paid.
- Needs Review page grouped by month.
- Monthly analytics, trend chart, CSV export.

RUN ON WINDOWS / VS CODE
1. Extract this ZIP.
2. Open the extracted "expense_tracker" folder in VS Code.
3. Open Terminal > New Terminal.
4. Create a virtual environment (optional but recommended):
   py -m venv .venv
5. Activate it:
   PowerShell: .\.venv\Scripts\Activate.ps1
   If PowerShell blocks activation, use Command Prompt:
   .venv\Scripts\activate.bat
6. Install dependencies:
   python -m pip install -r requirements.txt
7. Run:
   python app.py
8. Open the local URL printed in terminal, usually http://127.0.0.1:5000

DATABASE
The expenses.db SQLite file is created automatically next to app.py on first run.
Back it up before making major changes.

NOTES
- Chart.js is loaded from a CDN, so the charts need internet access in the browser.
- Recurring rules create scheduled records up to today's date whenever the app receives a request.
- Generated recurring records start as "Needs Review". Review them before setting Paid.
- This is a local learning project, not a security-audited financial service.
- Before deploying publicly, set a strong SECRET_KEY, add authentication and CSRF protection,
  and use production settings instead of Flask debug mode.

"""Print the columns of every table, for debugging. Run from backend/: python check_schema.py"""
import sqlite3
from database import DB_NAME

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

for table in ("invoices", "rejected_invoices", "invoice_history"):
    print(f"\nChecking schema of '{table}' table...\n")
    for col in cur.execute(f"PRAGMA table_info({table})").fetchall():
        print(f"Column: {col[1]} | Type: {col[2]}")

conn.close()

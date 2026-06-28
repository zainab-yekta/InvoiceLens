import sqlite3

conn = sqlite3.connect("invoices.db")
cur = conn.cursor()

print("Checking schema of 'invoices' table...\n")
cur.execute("PRAGMA table_info(invoices)")
columns = cur.fetchall()

for col in columns:
    print(f"Column: {col[1]} | Type: {col[2]}")

print("\nChecking schema of 'rejected_invoices' table...\n")
cur.execute("PRAGMA table_info(rejected_invoices)")
columns_rejected = cur.fetchall()

for col in columns_rejected:
    print(f"Column: {col[1]} | Type: {col[2]}")

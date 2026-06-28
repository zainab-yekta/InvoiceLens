import sqlite3

conn = sqlite3.connect("invoices.db")
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE invoices ADD COLUMN accepted BOOLEAN DEFAULT 1")
    conn.commit()
    print("✅ Column 'accepted' added successfully.")
except Exception as e:
    print(f"❌ Error while adding column: {e}")

conn.close()

import os
import re
import sqlite3
import uuid
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Always use the DB next to this file, no matter which folder uvicorn is started from.
# INVOICE_DB_PATH / INVOICE_UPLOAD_DIR let the tests use a throwaway copy.
DB_NAME = os.environ.get("INVOICE_DB_PATH", os.path.join(BASE_DIR, "invoices.db"))
UPLOAD_DIR = os.environ.get("INVOICE_UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))

# Column names can't be passed as SQL parameters, so only these are ever put into a query
DATE_COLUMNS = {"processing_date", "issue_date"}
EDITABLE_COLUMNS = {
    "invoice_number", "issue_date", "tax_number", "vat_percent", "vat_amount",
    "vat_id", "total_amount", "exemption_reason", "currency",
}

ACCEPTED_COLUMNS = [
    "id", "processing_date", "invoice_number", "issue_date",
    "tax_number", "vat_percent", "vat_amount", "vat_id",
    "total_amount", "exemption_reason", "used_ocr", "language", "currency"
]

REJECTED_COLUMNS = ["id", "processing_date", "rejection_date", "invoice_number", "issue_date", "reason"]

HISTORY_COLUMNS = [
    "id", "processing_date", "status", "reason", "invoice_number", "issue_date",
    "total_amount", "vat_amount", "vat_percent", "currency", "tax_number", "vat_id",
    "language", "used_ocr", "tags", "original_filename", "stored_filename"
]

# Stored uploads are always named <32 hex chars>.<extension>, so a name from a request can't point elsewhere
STORED_NAME_PATTERN = re.compile(r"^[0-9a-f]{32}\.(pdf|png|jpg|jpeg|bmp)$")


def _connect():
    return sqlite3.connect(DB_NAME)


def _add_missing_columns(cur, table, columns):
    """Older databases were created before these columns existed."""
    existing = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
    for name, sql_type in columns.items():
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")


def init_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processing_date TEXT,
            invoice_number TEXT,
            issue_date TEXT,
            tax_number TEXT,
            vat_percent TEXT,
            vat_amount TEXT,
            vat_id TEXT,
            total_amount TEXT,
            exemption_reason TEXT,
            accepted BOOLEAN,
            reason TEXT,
            used_ocr BOOLEAN,
            language TEXT,
            currency TEXT
        )
    ''')
    _add_missing_columns(cur, "invoices", {"language": "TEXT", "currency": "TEXT"})

    cur.execute('''
        CREATE TABLE IF NOT EXISTS rejected_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processing_date TEXT,
            rejection_date TEXT,
            invoice_number TEXT,
            issue_date TEXT,
            reason TEXT
        )
    ''')

    # Permanent record of every decision (accepted or rejected) with the original file.
    # Rows here are never edited or deleted, so it stays a trustworthy log.
    cur.execute('''
        CREATE TABLE IF NOT EXISTS invoice_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processing_date TEXT,
            status TEXT,
            reason TEXT,
            invoice_number TEXT,
            issue_date TEXT,
            total_amount TEXT,
            vat_amount TEXT,
            vat_percent TEXT,
            currency TEXT,
            tax_number TEXT,
            vat_id TEXT,
            language TEXT,
            used_ocr BOOLEAN,
            tags TEXT,
            original_filename TEXT,
            stored_filename TEXT
        )
    ''')

    conn.commit()
    conn.close()

def save_invoice(fields, accepted=True, reason="", used_ocr=False, language=""):
    conn = _connect()
    cur = conn.cursor()
    now = datetime.now().isoformat()

    cur.execute('''
        INSERT INTO invoices (
            processing_date, invoice_number, issue_date, tax_number, vat_percent, vat_amount, vat_id,
            total_amount, exemption_reason, accepted, reason, used_ocr, language, currency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        now,
        fields.get("invoice_number", ""),
        fields.get("date", ""),
        fields.get("tax_number", ""),
        fields.get("vat_percent", ""),
        fields.get("vat_amount", ""),
        fields.get("vat_id", ""),
        fields.get("total_amount", ""),
        fields.get("exemption_reason", ""),
        int(accepted),
        reason if not accepted else "",
        int(used_ocr),
        language,
        fields.get("currency", ""),
    ))
    conn.commit()
    conn.close()

def get_all_invoices():
    conn = _connect()
    cur = conn.cursor()

    accepted = cur.execute(
        f"SELECT {', '.join(ACCEPTED_COLUMNS)} FROM invoices WHERE accepted=1 ORDER BY id DESC"
    ).fetchall()
    rejected = cur.execute(
        f"SELECT {', '.join(REJECTED_COLUMNS)} FROM rejected_invoices ORDER BY id DESC"
    ).fetchall()
    history = cur.execute(
        f"SELECT {', '.join(HISTORY_COLUMNS)} FROM invoice_history ORDER BY id DESC"
    ).fetchall()
    conn.close()

    history_rows = []
    for row in history:
        item = dict(zip(HISTORY_COLUMNS, row))
        item["has_file"] = bool(item.pop("stored_filename"))
        history_rows.append(item)

    return {
        "accepted": [dict(zip(ACCEPTED_COLUMNS, row)) for row in accepted],
        "rejected": [dict(zip(REJECTED_COLUMNS, row)) for row in rejected],
        "history": history_rows,
    }

def get_invoice(invoice_id: int):
    conn = _connect()
    row = conn.execute(
        f"SELECT {', '.join(ACCEPTED_COLUMNS)} FROM invoices WHERE id = ?", (invoice_id,)
    ).fetchone()
    conn.close()
    return dict(zip(ACCEPTED_COLUMNS, row)) if row else None

def save_rejected_invoice(invoice_number: str, issue_date: str, reason: str):
    now = datetime.now().isoformat()
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO rejected_invoices (processing_date, rejection_date, invoice_number, issue_date, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (now, now, invoice_number, issue_date , reason))
    conn.commit()
    conn.close()

def invoice_exists_in_any_table(invoice_number: str, exclude_invoice_id=None) -> bool:
    conn = _connect()
    cur = conn.cursor()

    # exclude_invoice_id lets an invoice keep its own number when it is edited
    cur.execute(
        "SELECT COUNT(*) FROM invoices WHERE invoice_number = ? AND id IS NOT ?",
        (invoice_number, exclude_invoice_id),
    )
    count_accepted = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM rejected_invoices WHERE invoice_number = ?", (invoice_number,))
    count_rejected = cur.fetchone()[0]

    conn.close()
    return count_accepted > 0 or count_rejected > 0

def store_upload(file_bytes: bytes, extension: str) -> str:
    """Keep a copy of an uploaded invoice and return its generated file name."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension.lower()}"
    with open(os.path.join(UPLOAD_DIR, stored_name), "wb") as f:
        f.write(file_bytes)
    return stored_name

def upload_path(stored_name):
    """Full path of a stored upload, or None if the name is invalid or the file is gone."""
    if not stored_name or not STORED_NAME_PATTERN.match(stored_name):
        return None
    path = os.path.join(UPLOAD_DIR, stored_name)
    return path if os.path.isfile(path) else None

def add_history(status, reason, fields, language="", used_ocr=False, tags=None,
                original_filename="", stored_filename=None):
    if not upload_path(stored_filename):
        stored_filename = None

    conn = _connect()
    conn.execute('''
        INSERT INTO invoice_history (
            processing_date, status, reason, invoice_number, issue_date, total_amount, vat_amount,
            vat_percent, currency, tax_number, vat_id, language, used_ocr, tags,
            original_filename, stored_filename
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        status,
        reason,
        fields.get("invoice_number", ""),
        fields.get("date", ""),
        fields.get("total_amount", ""),
        fields.get("vat_amount", ""),
        fields.get("vat_percent", ""),
        fields.get("currency", ""),
        fields.get("tax_number", ""),
        fields.get("vat_id", ""),
        language,
        int(bool(used_ocr)),
        ", ".join(tags or []),
        original_filename,
        stored_filename,
    ))
    conn.commit()
    conn.close()

def get_history_file(history_id: int):
    """(path, original file name) of the invoice file behind a history row, or None."""
    conn = _connect()
    row = conn.execute(
        "SELECT stored_filename, original_filename FROM invoice_history WHERE id = ?", (history_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    path = upload_path(row[0])
    return (path, row[1] or os.path.basename(path)) if path else None

def _to_number(value):
    """Amounts are stored as text like "1234.56"; Excel needs real numbers to sum them."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value

def export_invoices_to_excel(invoice_type: str, from_date=None, to_date=None, date_type: str = "processing_date"):
    if date_type not in DATE_COLUMNS:
        raise ValueError(f"Invalid date type: {date_type}")

    # Either end of the range may be left open
    conditions, params = [], []
    if from_date:
        conditions.append(f"DATE({date_type}) >= ?")
        params.append(from_date)
    if to_date:
        conditions.append(f"DATE({date_type}) <= ?")
        params.append(to_date)

    wb = Workbook()
    sheet = wb.active

    conn = _connect()
    cur = conn.cursor()

    if invoice_type == "rejected":
        sheet.title = "rejected-invoice"
        headers = ["Index", "Processing Date", "Invoice Number", "Issue Date", "Reason"]
        number_columns = {}
        query = "SELECT id, processing_date, invoice_number, issue_date, reason FROM rejected_invoices"
        where = conditions
    else:
        sheet.title = "accepted-invoice"
        headers = ["ID", "Processing Date", "Invoice Number", "Issue Date", "Tax Number", "VAT %", "VAT Amount", "VAT ID", "Total", "Currency", "Exemption Reason"]
        # column index -> Excel number format
        number_columns = {5: "0", 6: "#,##0.00", 8: "#,##0.00"}
        query = """
            SELECT id, processing_date, invoice_number, issue_date, tax_number, vat_percent,
                   vat_amount, vat_id, total_amount, currency, exemption_reason
            FROM invoices
        """
        where = ["accepted = 1"] + conditions
    if where:
        query += " WHERE " + " AND ".join(where)
    rows = cur.execute(query + " ORDER BY id", params).fetchall()
    conn.close()

    sheet.append(headers)

    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.fill = PatternFill(start_color="CDEEEF", end_color="CDEEEF", fill_type="solid")
        sheet.column_dimensions[cell.column_letter].width = 30

    for row in rows:
        row = [_to_number(v) if i in number_columns else v for i, v in enumerate(row)]
        sheet.append(row)
        for i, cell in enumerate(sheet[sheet.max_row]):
            cell.alignment = Alignment(horizontal="center")
            if i in number_columns and isinstance(cell.value, float):
                cell.number_format = number_columns[i]

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()

def update_invoice_by_id(invoice_id: int, updated_fields: dict) -> bool:
    unknown = set(updated_fields) - EDITABLE_COLUMNS
    if unknown or not updated_fields:
        raise ValueError(f"Invalid fields: {', '.join(sorted(unknown)) or 'none given'}")

    conn = _connect()
    cur = conn.cursor()
    set_clause = ", ".join(f"{key} = ?" for key in updated_fields.keys())
    values = list(updated_fields.values()) + [invoice_id]

    query = f"UPDATE invoices SET {set_clause} WHERE id = ?"
    cur.execute(query, values)
    conn.commit()
    conn.close()
    return cur.rowcount > 0

def delete_invoice_by_id(invoice_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0

def delete_rejected_by_id(rejected_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM rejected_invoices WHERE id = ?", (rejected_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0

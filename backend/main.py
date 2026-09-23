import logging
import os
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from parser import extract_invoice_fields, missing_mandatory_fields, normalize_amount, normalize_date
from database import (
    init_db, save_invoice, get_all_invoices, save_rejected_invoice, export_invoices_to_excel,
    invoice_exists_in_any_table, update_invoice_by_id, delete_invoice_by_id, delete_rejected_by_id,
    get_invoice, store_upload, add_history, get_history_file, DATE_COLUMNS
)
from io import BytesIO
from pdf_utils import extract_text, SUPPORTED_EXTENSIONS
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("invoice_tool")

app = FastAPI(title="Invoice Tool")
init_db()
SUPPORTED_LANGUAGES = ['en', 'de']  # English and German for now
UNKNOWN_INVOICE_NUMBER = "UNKNOWN"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def clean_fields(fields: dict, language: str) -> dict:
    """Fields may have been edited by hand, e.g. "1.785,00", "28.07.2025" or "eur"."""
    fields = dict(fields)
    for key in ("total_amount", "vat_amount"):
        if key in fields:
            fields[key] = normalize_amount(str(fields.get(key) or ""), language)
    for key in ("date", "issue_date"):
        if key in fields:
            fields[key] = normalize_date(str(fields.get(key) or ""))
    if "currency" in fields:
        fields["currency"] = str(fields.get("currency") or "").strip().upper()
    if "invoice_number" in fields:
        fields["invoice_number"] = str(fields.get("invoice_number") or "").strip()
    return fields


def record_history(status: str, reason: str, fields: dict, data: dict):
    """Log the decision; a failure here must never lose the invoice itself."""
    try:
        add_history(
            status, reason, fields,
            language=data.get("language", ""),
            used_ocr=data.get("used_ocr", False),
            tags=data.get("tags") or [],
            original_filename=data.get("original_filename", ""),
            stored_filename=data.get("upload_id"),
        )
    except Exception:
        logger.exception("Could not write invoice history")


@app.post("/extract_fields")
async def extract_fields(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Please upload one of: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    file_bytes = await file.read()

    # OCR + PDF text extraction
    raw_text, used_ocr = extract_text(file_bytes, filename)
    logger.debug("Extracted text from %s:\n%s", filename, raw_text)

    result = extract_invoice_fields(raw_text)

    # language warning based on supported languages
    detected_lang = result.get("language", "unknown")
    if detected_lang not in SUPPORTED_LANGUAGES:
        result["language_warning"] = f"Invoice appears to be in an unsupported language: {detected_lang.upper()}"
    else:
        result["language_warning"] = ""

    logger.info("Processed %s: status=%s, language=%s, ocr=%s", filename, result["status"], detected_lang, used_ocr)

    # Keep the original file so the invoice history can link to it
    result["upload_id"] = store_upload(file_bytes, extension)
    result["original_filename"] = filename
    result["used_ocr"] = used_ocr
    return result

@app.post("/save_invoice")
async def save_invoice_api(data: dict = Body(...)):
    language = data.get("language", "")
    fields = clean_fields(data.get("fields", {}), language)
    invoice_number = fields.get("invoice_number", "")

    missing = missing_mandatory_fields(fields)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing mandatory fields: {', '.join(missing)}")

    if invoice_exists_in_any_table(invoice_number):
        raise HTTPException(status_code=409, detail="Invoice already exists in accepted or rejected invoices.")

    try:
        save_invoice(fields, used_ocr=bool(data.get("used_ocr")), language=language)
    except Exception:
        logger.exception("Could not save invoice %s", invoice_number)
        raise HTTPException(status_code=500, detail="Could not save the invoice.")

    record_history("accepted", "", fields, data)
    return {"status": "saved"}

@app.put("/update_invoice/{invoice_id}")
async def update_invoice(invoice_id: int, updated_fields: dict = Body(...)):
    existing = get_invoice(invoice_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    fields = clean_fields(updated_fields, existing.get("language") or "")

    # The UI calls the date "date"; the saved table calls it "issue_date"
    as_parsed = {("date" if k == "issue_date" else k): v for k, v in {**existing, **fields}.items()}
    missing = missing_mandatory_fields(as_parsed)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing mandatory fields: {', '.join(missing)}")

    new_number = fields.get("invoice_number")
    if new_number and invoice_exists_in_any_table(new_number, exclude_invoice_id=invoice_id):
        raise HTTPException(status_code=409, detail="Another invoice already uses this invoice number.")

    try:
        update_invoice_by_id(invoice_id, fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Could not update invoice %s", invoice_id)
        raise HTTPException(status_code=500, detail="Could not update the invoice.")
    return {"status": "updated"}

@app.delete("/delete_invoice/{invoice_id}")
async def delete_invoice(invoice_id: int = Path(...)):
    try:
        deleted = delete_invoice_by_id(invoice_id)
    except Exception:
        logger.exception("Could not delete invoice %s", invoice_id)
        raise HTTPException(status_code=500, detail="Could not delete the invoice.")
    if not deleted:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return {"status": "deleted"}

@app.delete("/delete_rejected/{rejected_id}")
async def delete_rejected(rejected_id: int = Path(...)):
    try:
        deleted = delete_rejected_by_id(rejected_id)
    except Exception:
        logger.exception("Could not delete rejected invoice %s", rejected_id)
        raise HTTPException(status_code=500, detail="Could not delete the rejected invoice.")
    if not deleted:
        raise HTTPException(status_code=404, detail="Rejected invoice not found.")
    return {"status": "deleted"}

@app.get("/get_invoices")
def api_get_all_invoices():
    try:
        return get_all_invoices()
    except Exception:
        logger.exception("Could not load invoices")
        raise HTTPException(status_code=500, detail="Could not load invoices.")

@app.get("/files/{history_id}")
def get_invoice_file(history_id: int):
    found = get_history_file(history_id)
    if not found:
        raise HTTPException(status_code=404, detail="No file stored for this invoice.")
    path, original_name = found
    # inline: the browser opens PDFs and images in a tab instead of downloading them
    return FileResponse(path, filename=original_name, content_disposition_type="inline")

@app.post("/reject_invoice")
async def reject_invoice(invoice: dict = Body(...)):
    fields = clean_fields(invoice.get("fields") or {}, invoice.get("language", ""))
    invoice_number = (
        str(invoice.get("invoice_number") or fields.get("invoice_number") or "").strip()
        or UNKNOWN_INVOICE_NUMBER
    )
    issue_date = invoice.get("issue_date") or fields.get("date", "")
    reason = invoice.get("reason") or "Missing mandatory fields"

    # Unreadable invoices all share "UNKNOWN", so they are never duplicates of each other
    if invoice_number != UNKNOWN_INVOICE_NUMBER and invoice_exists_in_any_table(invoice_number):
        raise HTTPException(status_code=409, detail="Invoice already exists in accepted or rejected invoices.")

    save_rejected_invoice(invoice_number, issue_date, reason)
    record_history("rejected", reason, {**fields, "invoice_number": invoice_number, "date": issue_date}, invoice)
    return {"message": "Invoice rejected"}

@app.post("/export_excel")
def export_excel(
    type: str = Form(...),
    from_date: Optional[str] = Form(None),
    to_date: Optional[str] = Form(None),
    date_type: str = Form("processing_date")
):
    if type not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="Type must be 'accepted' or 'rejected'")
    if date_type not in DATE_COLUMNS:
        raise HTTPException(status_code=400, detail=f"date_type must be one of: {', '.join(sorted(DATE_COLUMNS))}")

    logger.info("Exporting %s invoices from %s to %s using %s", type, from_date or "start", to_date or "today", date_type)
    try:
        excel_data = export_invoices_to_excel(type, from_date, to_date, date_type)
    except Exception:
        logger.exception("Excel export failed")
        raise HTTPException(status_code=500, detail="Export failed")

    return StreamingResponse(
        BytesIO(excel_data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={type}-invoice-excel.xlsx"}
    )

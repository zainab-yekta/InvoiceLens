from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from parser import extract_invoice_fields, assign_tags
from database import init_db, save_invoice, get_all_invoices, save_rejected_invoice, export_invoices_to_excel, invoice_exists_in_any_table
from datetime import datetime
from io import BytesIO
from pdf_utils import extract_text
from typing import Optional

app = FastAPI()
init_db()
SUPPORTED_LANGUAGES = ['en', 'de']  # English and German for now

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/extract_fields")
async def extract_fields(file: UploadFile = File(...)):
    file_bytes = await file.read()
    filename = file.filename

    # OCR + PDF text extraction
    raw_text, used_ocr = extract_text(file_bytes, filename)

    # 🔍 Debug: print the extracted text
    print("----- OCR/PDF TEXT START -----")
    print(raw_text)
    print("------ OCR/PDF TEXT END ------")

    result = extract_invoice_fields(raw_text)
    tags = assign_tags(raw_text)
    result["tags"] = tags


    # language warning based on supported languages
    detected_lang = result.get("language", "unknown")
    if detected_lang not in SUPPORTED_LANGUAGES:
        result["language_warning"] = f"⚠️ Invoice appears to be in unsupported language: {detected_lang.upper()}"
    else:
        result["language_warning"] = ""

    # 🔍 Debug: print extracted fields
    print("----- EXTRACTED FIELDS -----")
    print(result["fields"])
    print("Status:", result["status"])
    print("Reason:", result.get("reason", ""))
    print("Language:", result.get("language", "unknown"))
    print("Tags:", tags)
    print("Returned Result:", result)
    print("-----------------------------")

    result["used_ocr"] = used_ocr
    return result

@app.post("/save_invoice")
async def save_invoice_api(data: dict = Body(...)):
    try:
        fields = data.get("fields", {})
        accepted = data.get("accepted", True)
        reason = data.get("reason", "")
        used_ocr = data.get("used_ocr", False)
        invoice_number = fields.get("invoice_number", "")

        if not invoice_number or not fields.get("date") or not fields.get("total_amount"):
            raise HTTPException(status_code=400, detail="Missing mandatory fields (invoice_number, date, total_amount)")

        if invoice_exists_in_any_table(invoice_number):
            raise HTTPException(status_code=409, detail="Invoice already exists in accepted or rejected invoices.")

        save_invoice(fields, accepted, reason, used_ocr)
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/update_invoice/{invoice_id}")
async def update_invoice(invoice_id: int, updated_fields: dict = Body(...)):
    from database import update_invoice_by_id
    try:
        update_invoice_by_id(invoice_id, updated_fields)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_invoice/{invoice_id}")
async def delete_invoice(invoice_id: int = Path(...)):
    from database import delete_invoice_by_id
    try:
        delete_invoice_by_id(invoice_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_invoices")
def api_get_all_invoices():
    try:
        return get_all_invoices()
    except Exception as e:
        print(f"Error in /get_invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reject_invoice")
async def reject_invoice(invoice: dict = Body(...)):
    invoice_number = invoice.get("invoice_number", "UNKNOWN")
    issue_date = invoice.get("issue_date", "")
    reason = invoice.get("reason", "Missing mandatory fields")

    if invoice_exists_in_any_table(invoice_number):
        raise HTTPException(status_code=409, detail="Invoice already exists in accepted or rejected invoices.")

    save_rejected_invoice(invoice_number, issue_date, reason)
    return {"message": "Invoice rejected"}

@app.post("/export_excel")
def export_excel(
    type: str = Form(...),
    from_date: Optional[str] = Form(None),
    to_date: Optional[str] = Form(None),
    date_type: str = Form("processing_date")
):
    try:
        if not from_date or not to_date:
            raise HTTPException(status_code=400, detail="Missing from/to date")

        print(f"Exporting {type} invoices from {from_date} to {to_date} using {date_type}")

        excel_data = export_invoices_to_excel(type, from_date, to_date, date_type)

        return StreamingResponse(
            BytesIO(excel_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={type}-invoice-excel.xlsx"}
        )
    except Exception as e:
        print(f"[EXPORT ERROR] {e}")
        raise HTTPException(status_code=500, detail="Export failed")


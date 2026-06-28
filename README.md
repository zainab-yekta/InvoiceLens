# Invoice Processing Tool

An automated invoice processing system that extracts structured data from PDF and scanned invoices using OCR, validates the results, and exports accounting-ready Excel reports.

Built with **Python**, **FastAPI**, **OCR (Tesseract)**, and **SQLite**.

---

## What It Does

- Accepts PDF or scanned image invoices via a REST API
- Extracts key fields: invoice number, date, total amount, VAT, tax ID, supplier info
- Detects language (English and German supported)
- Validates mandatory fields and flags duplicates
- Saves accepted and rejected invoices to separate SQLite tables
- Exports filtered Excel reports by date range for accounting workflows
- Handles low-quality scans with OCR fallback logic

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, FastAPI |
| OCR & Text Extraction | Tesseract OCR, pdfplumber |
| Database | SQLite |
| Export | openpyxl (Excel .xlsx) |
| Frontend | React.js |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/extract_fields` | Upload invoice PDF/image, returns extracted fields |
| POST | `/save_invoice` | Save a validated invoice to the database |
| POST | `/reject_invoice` | Log a rejected invoice with reason |
| GET | `/get_invoices` | Retrieve all saved invoices |
| PUT | `/update_invoice/{id}` | Update an existing invoice record |
| DELETE | `/delete_invoice/{id}` | Delete an invoice by ID |
| POST | `/export_excel` | Export invoices to Excel by date range and type |

---

## Project Structure

```
Invoice-Tool/
├── backend/
│   ├── main.py          # FastAPI app and all route handlers
│   ├── parser.py        # OCR field extraction and tag assignment
│   ├── pdf_utils.py     # PDF text extraction and OCR logic
│   ├── database.py      # SQLite init, CRUD, and Excel export
│   └── check_schema.py  # Schema inspection utility
├── frontend/
│   └── src/             # React frontend for invoice upload and review
└── README.md
```

---

## Run Locally

### 1. Clone the repository
```bash
git clone https://github.com/zainab-yekta/InvoiceLens.git
cd InvoiceLens
```

### 2. Set up Python environment
```bash
cd backend
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install fastapi uvicorn pdfplumber pytesseract pillow openpyxl
```

> Make sure [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) is installed on your system.

### 3. Run the backend
```bash
uvicorn main:app --reload
```

### 4. Run the frontend
```bash
cd ../frontend
npm install
npm start
```

---

## Key Design Decisions

- **Dual extraction strategy**: tries pdfplumber first for digital PDFs; falls back to Tesseract OCR for scanned documents
- **Duplicate detection**: checks both accepted and rejected tables before saving
- **Language detection**: warns when invoice language is outside supported set (EN, DE)
- **Structured rejection logging**: rejected invoices are stored separately with reason codes for audit purposes

---

## Author

Built by **Zeinab Ramezani Yekta** — Full-Stack Developer  
[LinkedIn](https://linkedin.com/in/zeinab-ramezani) · [GitHub](https://github.com/zainab-yekta)

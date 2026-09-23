# Invoice Tool

Upload a German or English invoice (PDF or scanned image), check the fields the tool pulls out, then save or reject it. Saved invoices can be exported to Excel by date range for accounting.

## What it does

- Reads the text layer of digital PDFs with pdfplumber. If there isn't one (a scanned PDF or a photo), it runs Tesseract OCR instead.
- Extracts invoice number, invoice date, total, VAT amount, VAT rate, VAT ID, tax number and exemption reason, using rule-based patterns for German and English.
- Detects the invoice language and reads amounts in the right format: `1.785,00` on a German invoice and `1,785.00` on an English one are both stored as `1785.00`.
- Flags missing mandatory fields. You can fix them in the form, and the invoice becomes ready to upload as soon as they are filled in.
- Blocks duplicates across saved and rejected invoices.
- Tags invoices by keyword (consulting, software, travel, food, office).
- Exports saved or rejected invoices to Excel, filtered by processing date or issue date. Amounts are real number cells, so they can be summed.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, FastAPI |
| Text extraction | pdfplumber, Tesseract OCR (pytesseract, pdf2image) |
| Language detection | langdetect |
| Database | SQLite |
| Export | openpyxl |
| Frontend | React, axios, react-toastify |
| Tests | pytest |

## Run locally

### Prerequisites

- Python 3.10 or newer
- Node.js 18 or newer
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract), for scanned invoices
- [Poppler](https://poppler.freedesktop.org/), which pdf2image uses to turn scanned PDFs into images. On Windows, download a [release](https://github.com/oschwartz10612/poppler-windows/releases) and add its `Library/bin` folder to your PATH.

### Backend

```bash
git clone https://github.com/zainab-yekta/InvoiceLens.git
cd InvoiceLens/backend
python -m venv env
source env/bin/activate        # Windows: env\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API runs on http://127.0.0.1:8000, and interactive docs are at http://127.0.0.1:8000/docs. The SQLite database (`invoices.db`) is created next to `main.py` on first start.

### Frontend

```bash
cd frontend
npm install
npm start
```

The app opens on http://localhost:3000. To use a different backend address, set `REACT_APP_API_URL` before `npm start`.

### Tests

```bash
cd backend
pytest
```

The tests cover amount and date parsing in both formats, keyword tagging, and field extraction from sample German and English invoice text.

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/extract_fields` | Upload a PDF or image and get the extracted fields back |
| POST | `/save_invoice` | Save a reviewed invoice |
| POST | `/reject_invoice` | Store a rejected invoice with its reason |
| GET | `/get_invoices` | List saved and rejected invoices |
| POST | `/export_excel` | Download saved or rejected invoices for a date range as .xlsx |
| PUT | `/update_invoice/{id}` | Update fields of a saved invoice (API only, no UI yet) |
| DELETE | `/delete_invoice/{id}` | Delete a saved invoice (API only, no UI yet) |

## Project structure

```
invoice-tool/
├── backend/
│   ├── main.py            # FastAPI app and routes
│   ├── parser.py          # Field extraction, amount/date parsing, tags
│   ├── pdf_utils.py       # pdfplumber text extraction with OCR fallback
│   ├── database.py        # SQLite access and Excel export
│   ├── check_schema.py    # Prints the table columns, for debugging
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   └── src/
│       ├── App.js         # State and API calls
│       ├── format.js      # Number and date display helpers
│       └── components/    # UploadCard, ExtractedFields, InvoiceTable
```

## Design decisions

- **Text first, OCR second.** pdfplumber is fast and exact on digital PDFs. OCR only runs when a PDF has almost no text, or when the upload is an image.
- **Amount format comes from the number.** Whichever of `.` or `,` comes last is the decimal separator. The detected language only decides the truly ambiguous case, like `1.234`.
- **One list of mandatory fields.** The backend defines it once and sends it with every extraction result, so the frontend and backend always agree.
- **Column names are allow-listed.** User input never ends up in SQL as a column name.
- **Rejected invoices are kept.** They go to a separate table with the reason, so there's an audit trail.

## Limitations

- Extraction is rule-based. Invoice layouts the patterns don't cover will come back with missing fields for manual review.
- Dates with slashes are read day-first (`05/03/2024` is 5 March), which suits EU invoices.
- No user accounts. It's meant to run locally.

## Author

Built by **Zeinab Ramezani Yekta**, Full-Stack Developer
[LinkedIn](https://linkedin.com/in/zeinab-ramezani) · [GitHub](https://github.com/zainab-yekta)

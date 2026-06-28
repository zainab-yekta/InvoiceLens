import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image, ImageFilter, ImageOps
import io

def extract_text(file_bytes: bytes, filename: str) -> tuple[str, bool]:
    is_ocr_used = False
    text = ""

    filename = filename.lower()

    # ---------- Case 1: PDF Files ----------
    if filename.endswith(".pdf"):
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"[pdfplumber] Error: {e}")

        # Fallback to OCR if PDF has no extractable text
        if len(text.strip()) < 30:
            print("[OCR] Falling back to OCR for scanned PDF...")
            try:
                images = convert_from_bytes(file_bytes)
                for img in images:
                    gray = img.convert("L")
                    ocr_text = pytesseract.image_to_string(gray)
                    text += ocr_text + "\n"
                is_ocr_used = True
            except Exception as e:
                print(f"[OCR] PDF fallback failed: {e}")

    # ---------- Case 2: Image Files ----------
    elif filename.endswith((".jpg", ".jpeg", ".png", ".bmp")):
        try:
            image = Image.open(io.BytesIO(file_bytes)).convert("L")
            image = image.resize((image.width * 2, image.height * 2))  # Upscale
            image = ImageOps.autocontrast(image)  # Enhance contrast
            image = image.filter(ImageFilter.SHARPEN)  # Sharpen edges
            image = image.point(lambda x: 0 if x < 180 else 255, '1')  # Binarize
            text = pytesseract.image_to_string(image)
            is_ocr_used = True
        except Exception as e:
            print(f"[OCR] Image file extraction failed: {e}")

    return text.strip(), is_ocr_used

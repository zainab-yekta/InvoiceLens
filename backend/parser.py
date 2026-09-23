import logging
import re
from collections import Counter
from datetime import datetime
from langdetect import detect, DetectorFactory

# langdetect is random by default; a fixed seed gives the same answer every run
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

# One list used by the parser, the API and the frontend (sent in the /extract_fields response)
MANDATORY_FIELDS = ["invoice_number", "date", "total_amount", "tax_number", "vat_amount"]

CURRENCY_PATTERN = re.compile(r"[€$£]|EUR|USD|GBP|CHF", re.IGNORECASE)


def normalize_amount(value, language="en"):
    """Turn an amount written in German or English style into a plain number string.

    The decimal separator is worked out from the number itself:
      - both "." and "," present -> the last one is the decimal separator (1.234,56 / 1,234.56)
      - one separator repeated   -> thousands separator (1.234.567)
      - one separator, 1-2 digits after it -> decimal separator (285,00 / 150.00)
      - one separator, exactly 3 digits after it -> ambiguous, the invoice language decides
        (de: 1.234 = 1234, en: 1,234 = 1234)
    """
    if not value:
        return ""

    cleaned = CURRENCY_PATTERN.sub("", value)
    cleaned = re.sub(r"[\s\u00a0\u202f']", "", cleaned).strip(".,")
    if not re.fullmatch(r"-?[\d.,]+", cleaned):
        return value.strip()

    last_dot, last_comma = cleaned.rfind("."), cleaned.rfind(",")
    if last_dot != -1 and last_comma != -1:
        decimal = "." if last_dot > last_comma else ","
    elif last_dot == -1 and last_comma == -1:
        decimal = None
    else:
        separator = "." if last_dot != -1 else ","
        digits_after = len(cleaned) - cleaned.rfind(separator) - 1
        if cleaned.count(separator) > 1:
            decimal = None
        elif digits_after == 3:
            decimal = "," if language == "de" else "."
        else:
            decimal = separator

    for thousands in {".", ","} - {decimal}:
        cleaned = cleaned.replace(thousands, "")
    if decimal:
        cleaned = cleaned.replace(decimal, ".")

    try:
        return "{:.2f}".format(float(cleaned))
    except ValueError:
        return value.strip()


CURRENCY_MARKERS = re.compile(r"€|\$|£|\b(?:EUR|Euro|USD|GBP|CHF)\b", re.IGNORECASE)
CURRENCY_CODES = {"€": "EUR", "eur": "EUR", "euro": "EUR", "$": "USD", "usd": "USD", "£": "GBP", "gbp": "GBP", "chf": "CHF"}


def detect_currency(text: str, language: str) -> str:
    """The currency named most often on the invoice ("€", "EUR", "$", ...).

    German invoices without any marker are almost always in euro. For other
    languages we don't guess; the reviewer can fill it in.
    """
    counts = Counter(CURRENCY_CODES[m.group(0).lower()] for m in CURRENCY_MARKERS.finditer(text))
    if counts:
        return counts.most_common(1)[0][0]
    return "EUR" if language == "de" else ""


def detect_language(text: str) -> str:
    try:
        return detect(text)
    except Exception:
        return "unknown"


def normalize_date(value):
    value = value.strip().rstrip(".,")
    if not value:
        return ""

    month_map = {
        "januar": "01", "februar": "02", "märz": "03", "april": "04",
        "mai": "05", "juni": "06", "juli": "07", "august": "08",
        "september": "09", "oktober": "10", "november": "11", "dezember": "12"
    }
    # German date with month names (e.g. 8. Mai 2019)
    match = re.match(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", value)
    if match:
        day, month_str, year = match.groups()
        month = month_map.get(month_str.lower())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    # Numeric formats are day-first (EU); English month names (March 5, 2024 / 05 Jan 2024)
    value = re.sub(r"\s+", " ", value)
    formats = (
        "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%Y.%m.%d",
        "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y", "%d. %B %Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def assign_tags(text):
    tags = []
    tag_keywords = {
        "consulting": ["consulting", "advisory", "berater", "beratung"],
        "software": ["software", "lizenz", "license"],
        "travel": ["reise", "flug", "bahn"],
        "food": ["essen", "lebensmittel", "verpflegung"],
        "office": ["büro", "office", "stationery"]
    }

    text = text.lower()
    for tag, keywords in tag_keywords.items():
        # Match at the start of a word, so "Reisekosten" counts but "Preise" does not
        if any(re.search(r"\b" + re.escape(keyword), text) for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append("uncategorized")
    return tags


def missing_mandatory_fields(fields: dict) -> list:
    return [k for k in MANDATORY_FIELDS if not str(fields.get(k) or "").strip()]


# The captured number must contain at least one digit, so words like "Date" are never taken as the number
INVOICE_NUMBER_VALUE = r"((?=[A-Z0-9\-\/]*\d)[A-Z0-9][A-Z0-9\-\/]{2,})"

PATTERNS_BY_LANGUAGE = {
    "en": {
        "invoice_number": [
            r"Invoice\s*(?:Number|No\.?|#)?[\s:#\-]*" + INVOICE_NUMBER_VALUE
        ],
        "date": [
            r"(?:Date|Issue date)[\s:\/\-.]*([0-9]{1,4}[\./\- ][0-9]{1,2}[\./\- ][0-9]{1,4})",
            r"(?:Date|Issue date)[\s:\-]*(\d{1,2}\.?\s+[A-Za-z]{3,9}\.?,?\s+\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})"
        ],
        "total_amount": [
            r"(?:Total(?:\s*(?:Amount|Due))?|Total net price|Amount Due)[:\s$€]*[A-Z]{0,3}\s*([0-9.,]+)",
            r"Total:\s*[A-Z]{0,3}\s*([0-9.,]+)"
        ],
        "tax_number": [
            r"(?:Tax number|TAX ID)[\s:$]*([A-Za-z0-9\-\/]+)"
        ],
        "vat_amount": [
            r"(?:VAT|Tax)\s*\(\s*[0-9]{1,2}\s*%\s*\)[:\s$€]*[A-Z]{0,3}\s*([0-9.,]+)",  # VAT (20%): $200.00
            r"VAT(?:\s*Amount)?[:\s$€]*[A-Z]{0,3}\s*([0-9.,]+)"
        ],
        "vat_percent": [
            r"(?:VAT|Tax)\s*\(\s*([0-9]{1,2})\s*%\s*\)",
            r"VAT\s*[:\s]*([0-9]{1,2})\s*%"
        ],
        "vat_id": [
            r"(?:VAT ID|TAX ID)[\s:$]*([A-Za-z0-9\-]+)"
        ],
        "exemption_reason": [
            r"(?:Exempt(?:ion)?(?: reason)?|Reason for exemption)[:\s\-]*([A-Za-z\s]+)"
        ]
    },
    "de": {
        "invoice_number": [
            r"Rechnungs(?:nummer|nr\.?)[:\s\-#]*" + INVOICE_NUMBER_VALUE
        ],
        "date": [
            r"(?:Rechnungsdatum|Liefer- und Rechnungsdatum)[\s:\-]*([0-9]{1,2}\.\s*\w+\s*[0-9]{4})",  # e.g., 8. Mai 2019
            r"(?:Rechnungsdatum|Liefer- und Rechnungsdatum)[\s:\-]*([0-9]{1,4}[./\-][0-9]{1,2}[./\-][0-9]{1,4})"
        ],
        "total_amount": [
            r"(?:Rechnungssumme\s*brutto)[\s:$€]*([0-9.,]+)",
            r"(?:Gesamtbetrag|Bruttobetrag)[\s:$€]*([0-9.,]+)"
        ],
        "vat_amount": [
            r"(?:Umsatzsteuer\s*\(\s*\d{1,2}%\s*\))[:\s\-]*€?\s*([0-9.,]+)",                # Umsatzsteuer (19%): € 285,00
            r"(?:zuzüglich\s*\d{1,2}%\s*MwSt\.?)[:\s\-]*€?\s*([0-9.,]+)",                    # zuzüglich 19% MwSt. 160,55
            r"(?:MwSt(?:\s*\(\s*\d{1,2}%\s*\))?)[\s:]*€?\s*([0-9.,]+)",                      # MwSt (19%): €102,60 or MwSt 160,55
            r"(?:USt(?:[-\s]?Betrag)?|Mehrwertsteuer)[\s:]*€?\s*([0-9.,]+)",                 # fallback: USt Betrag: €285,00 or Mehrwertsteuer: €xx
            r"[0-9]{1,2}%\s*(?:MwSt|USt)[\s:]*€?\s*([0-9.,]+)"                               # 19% MwSt 285,00
        ],
        "vat_percent": [
            r"(?:USt|MwSt|Umsatzsteuer|Mehrwertsteuer)[\s\(]*([0-9]{1,2})\s*%",
            r"zzgl\.?\s*([0-9]{1,2})%\s*MwSt",
            r"zuzüglich\s+([0-9]{1,2})%\s+MwSt"
        ],
        "vat_id": [
            r"(?:USt-IdNr)[\s:.]*([A-Z]{2}[0-9]{8,12})",
            r"(DE[0-9]{9})"  # Fallback for DE numbers
        ],
        "tax_number": [
            r"(?:Steuernummer)[\s:$]*([A-Za-z0-9\-\/]+)"
        ],
        "exemption_reason": [
            r"(?:Befreiungsgrund(?:\s*\(.*?\))?)[:\s\-]*([^\n]+)",
            r"(?:Hinweis)[:\s\-]*([^\n]+)"
        ],
    },
}


def extract_invoice_fields(text: str):
    language = detect_language(text[:500]) if text.strip() else "unknown"
    pattern_set = PATTERNS_BY_LANGUAGE.get(language, PATTERNS_BY_LANGUAGE["en"])

    def search(patterns, prefer_last=False):
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return matches[-1].strip() if prefer_last else matches[0].strip()
        return ""

    fields = {}
    for field, patterns in pattern_set.items():
        prefer_last = field in ["total_amount", "vat_amount", "vat_percent"]
        raw_value = search(patterns, prefer_last=prefer_last)
        if field == "date":
            fields[field] = normalize_date(raw_value)
        elif field in ["total_amount", "vat_amount"]:
            fields[field] = normalize_amount(raw_value, language)
        else:
            fields[field] = raw_value
    fields["currency"] = detect_currency(text, language)

    missing_fields = missing_mandatory_fields(fields)
    status = "accepted" if not missing_fields else "rejected"
    reason = "Missing fields: " + ", ".join(missing_fields) if missing_fields else ""
    if not text.strip():
        reason = "No text could be read from this file"

    logger.debug("Extracted fields: %s | status=%s | reason=%s", fields, status, reason)

    return {
        "fields": fields,
        "status": status,
        "reason": reason,
        "language": language,
        "tags": assign_tags(text),
        "mandatory_fields": MANDATORY_FIELDS,
    }

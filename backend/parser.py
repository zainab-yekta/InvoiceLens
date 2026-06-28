import re
from datetime import datetime
from langdetect import detect

DEBUG = True  # Set to False in production

def normalize_amount(value):
    if not value:
        return ""
    value = value.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return "{:.2f}".format(float(value))
    except:
        return value

def detect_language(text: str) -> str:
    try:
        return detect(text)
    except:
        return "unknown"

def normalize_date(value):
    value = value.strip()
    month_map = {
        "januar": "01", "februar": "02", "märz": "03", "april": "04",
        "mai": "05", "juni": "06", "juli": "07", "august": "08",
        "september": "09", "oktober": "10", "november": "11", "dezember": "12"
    }
    try:
        # Check for German date with month names (e.g. 8. Mai 2019)
        match = re.match(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", value)
        if match:
            day, month_str, year = match.groups()
            month = month_map.get(month_str.lower())
            if month:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    except:
        pass

    # Try standard formats
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except:
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
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append("uncategorized")
    return tags

def extract_invoice_fields(text: str):
    language = detect_language(text[:500]) if text.strip() else "unknown"

    patterns_by_language = {
        "en": {
            "invoice_number": [
                r"(?:Invoice(?:\s*Number|\s*No|\s*#)?)[\s\-:#]*([A-Z]{1,4}[-]?\d{3,}[\/\d{0,4}]*)"
            ],
            "date": [
                r"(?:Date|Issue date)[\s:\/\-.]*([0-9]{1,4}[\./\- ][0-9]{1,2}[\./\- ][0-9]{1,4})"
            ],
            "total_amount": [
                r"(?:Total(?:\s*(?:Amount|Due))?|Total net price|Amount Due)[:\s$€]*[A-Z]{0,3}\s*([0-9.,]+)",
                r"Total:\s*[A-Z]{0,3}\s*([0-9.,]+)"
            ],
            "tax_number": [
                r"(?:Tax number|TAX ID)[\s:$]*([A-Za-z0-9\-\/]+)"
            ],
            "vat_amount": [
                r"(?:VAT(?:\s*Amount)?|Tax\s*\([0-9]{1,2}%\))[:\s$€]*[A-Z]{0,3}\s*([0-9.,]+)",
                r"Tax\s*\([0-9]{1,2}%\):\s*[A-Z]{0,3}\s*([0-9.,]+)"
            ],
            "vat_percent": [
                r"Tax\s*\(\s*([0-9]{1,2})\s*%\s*\)", 
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
                r"Rechnungs(?:nummer|nr\.?)[:\s\-#]*([A-Z0-9\-\/]+)"
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
                r"(?:USt|MwSt|Umsatzsteuer|Mehrwertsteuer)[\s\(]*([0-9]{1,2})[%]{0,1}[\s\)]*",
                r"zzgl\.?\s*([0-9]{1,2})%\s*MwSt",
                r"zuzüglich\s+([0-9]{1,2})%\s+MwSt"
            ],
            "vat_id": [
                r"(?:USt-IdNr)[\s:]*([A-Z]{2}[0-9]{8,12})",
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
        "es": {
            "invoice_number": [
                r"(?:Factura(?:\s*Número|\s*No)?)[:\s\-#]*([A-Z]{1,4}[-]?\d{3,}[\/\d{0,4}]*)"
            ],
            "date": [
                r"(?:Fecha emisión)[\s:/\-\.]*([0-9]{1,4}[./ \-][0-9]{1,2}[./ \-][0-9]{1,4})"
            ],
            "total_amount": [r"(?:Total|Total a pagar)[\s:$€]*([0-9.,]+)"],
            "tax_number": [r"(?:Número de impuesto|CIF)[\s:$]*([A-Za-z0-9\-\/]+)"],
            "vat_amount": [r"(?:IVA(?:\s*monto)?)[:\s]*([0-9.,]+)"],
            "vat_percent": [r"(?:Tipo de IVA)[\s:]*([0-9]+)[\s%]*"],
            "vat_id": [r"(?:CIF)[\s:$]*([A-Za-z0-9\-]+)"],
            "exemption_reason": [r"(?:Exento)[:\s\-]*([A-Za-z\s]+)"]
        }
    }

    pattern_set = patterns_by_language.get(language, patterns_by_language["en"])

    def search(patterns, prefer_last=False):
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    # Choose the first non-empty part from tuple
                    for part in matches[0]:
                        if part.strip():
                            return part.strip()
                return matches[-1].strip() if prefer_last else matches[0].strip()
        return ""

    fields = {}
    for field, patterns in pattern_set.items():
        prefer_last = field in ["total_amount", "vat_amount", "vat_percent"]
        raw_value = search(patterns, prefer_last=prefer_last)
        if field == "date":
            fields[field] = normalize_date(raw_value)
        elif field in ["total_amount", "vat_amount"]:
            fields[field] = normalize_amount(raw_value)
        else:
            fields[field] = raw_value

    mandatory = ["invoice_number", "date", "total_amount", "tax_number", "vat_amount"]
    missing_fields = [k for k in mandatory if not fields.get(k)]
    status = "accepted" if not missing_fields else "rejected"
    reason = "Missing fields: " + ", ".join(missing_fields) if missing_fields else ""

    tags = assign_tags(text)

    if DEBUG:
        print("---- Extracted Fields ----")
        for key, val in fields.items():
            print(f"{key}: {val}")
        print(f"Status: {status}")
        if reason:
            print(f"Reason: {reason}")
        print("--------------------------")

    return {
        "fields": fields,
        "status": status,
        "reason": reason,
        "language": language,
        "tags": tags
    }

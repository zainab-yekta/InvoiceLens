import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import normalize_amount, normalize_date, assign_tags, extract_invoice_fields


@pytest.mark.parametrize("raw, language, expected", [
    # German style
    ("1.234,56", "de", "1234.56"),
    ("285,00", "de", "285.00"),
    ("1.785,00 €", "de", "1785.00"),
    ("1.234", "de", "1234.00"),
    ("1.234.567", "de", "1234567.00"),
    # English style
    ("150.00", "en", "150.00"),
    ("1,234.56", "en", "1234.56"),
    ("$99.99", "en", "99.99"),
    ("1,234", "en", "1234.00"),
    ("EUR 1,200.50", "en", "1200.50"),
    # The separators alone decide, whatever language was detected
    ("1.234,56", "en", "1234.56"),
    ("1,234.56", "de", "1234.56"),
    ("", "de", ""),
])
def test_normalize_amount(raw, language, expected):
    assert normalize_amount(raw, language) == expected


@pytest.mark.parametrize("raw, expected", [
    ("28.07.2025", "2025-07-28"),
    ("8. Mai 2019", "2019-05-08"),
    ("2025-07-23", "2025-07-23"),
    ("05/03/2024", "2024-03-05"),
    ("March 5, 2024", "2024-03-05"),
    ("05 Jan 2024", "2024-01-05"),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


def test_tags_match_word_starts_only():
    assert assign_tags("Reisekosten nach Berlin") == ["travel"]
    assert "travel" not in assign_tags("Alle Preise inkl. MwSt")
    assert "food" not in assign_tags("Rechnungsadressen")


GERMAN_INVOICE = """
Rechnung
Rechnungsnummer: INV-2025-0917
Rechnungsdatum: 28.07.2025
Verkäufer: Muster GmbH, Hauptstraße 12, 10115 Berlin
USt-IdNr.: DE123456789
Steuernummer: 12/345/67890
Beratungsleistungen für das Projekt im Juli
Nettobetrag: 1.500,00 €
Umsatzsteuer (19%): 285,00 €
Gesamtbetrag: 1.785,00 €
"""

ENGLISH_INVOICE = """
INVOICE
Invoice Number: 12345
Date: 05/03/2024
Bill to: Example Ltd, 1 High Street, London
Tax number: 123-456-789
Consulting services for the month of February
Subtotal: $1,000.00
VAT (20%): $200.00
Total Due: $1,200.00
"""


def test_extract_german_invoice():
    result = extract_invoice_fields(GERMAN_INVOICE)
    fields = result["fields"]
    assert result["language"] == "de"
    assert fields["invoice_number"] == "INV-2025-0917"
    assert fields["date"] == "2025-07-28"
    assert fields["total_amount"] == "1785.00"
    assert fields["vat_amount"] == "285.00"
    assert fields["vat_percent"] == "19"
    assert fields["vat_id"] == "DE123456789"
    assert result["status"] == "accepted"


def test_extract_english_invoice():
    result = extract_invoice_fields(ENGLISH_INVOICE)
    fields = result["fields"]
    assert result["language"] == "en"
    assert fields["invoice_number"] == "12345"
    assert fields["date"] == "2024-03-05"
    assert fields["total_amount"] == "1200.00"
    assert fields["vat_amount"] == "200.00"
    assert result["status"] == "accepted"


def test_missing_fields_are_reported():
    result = extract_invoice_fields("Invoice Number: 12345\nThank you")
    assert result["status"] == "rejected"
    assert "total_amount" in result["reason"]

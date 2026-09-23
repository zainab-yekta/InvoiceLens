import pytest

from parser import normalize_amount, normalize_date, assign_tags, extract_invoice_fields, detect_currency


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


@pytest.mark.parametrize("text, language, expected", [
    ("Gesamtbetrag: 1.785,00 € (EUR)", "de", "EUR"),
    ("Total Due: $1,200.00", "en", "USD"),
    ("Amount: £50.00 GBP", "en", "GBP"),
    ("Betrag: CHF 90.00", "de", "CHF"),
    ("Summe 100,00", "de", "EUR"),   # German without a marker: euro
    ("Total 100.00", "en", ""),      # English without a marker: left for the reviewer
])
def test_detect_currency(text, language, expected):
    assert detect_currency(text, language) == expected


@pytest.mark.parametrize("text, expected", [
    ("Reisekosten nach Berlin", ["travel"]),
    ("2x Laptop Dell, 1x Monitor 27 Zoll", ["electronics"]),
    ("Business lunch at Restaurant Roma", ["food"]),
    ("Bewirtung von Geschäftspartnern", ["food"]),
    ("Microsoft 365 subscription, 12 months", ["software"]),
    ("Toner and copy paper", ["office"]),
    ("Office stationery and printer paper", ["office"]),
    ("HP LaserJet printer", ["electronics"]),
    ("Glasfaser Internet 500 Mbit", ["telecom"]),
    ("Diesel 45 Liter, Tankstelle Nord", ["vehicle"]),
    ("Hotel Adlon, 2 nights, and flight to Munich", ["travel"]),
    ("Beratung und Softwarelizenz", ["consulting", "software"]),
    ("Payment due within 14 days", ["uncategorized"]),
])
def test_tags(text, expected):
    assert assign_tags(text) == expected


@pytest.mark.parametrize("text", [
    "Alle Preise inkl. MwSt",               # "reise" inside "Preise"
    "Musterstraße 1, 45127 Essen",          # Essen is also a city
    "Bahnhofstraße 5, Flughafenstraße 9",   # street names
    "Registered office: 1 High Street",     # standard UK footer
    "Server monitoring service",            # not a monitor
])
def test_tags_ignore_look_alikes(text):
    assert assign_tags(text) == ["uncategorized"]


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
    assert fields["currency"] == "EUR"
    assert result["status"] == "accepted"


def test_extract_english_invoice():
    result = extract_invoice_fields(ENGLISH_INVOICE)
    fields = result["fields"]
    assert result["language"] == "en"
    assert fields["invoice_number"] == "12345"
    assert fields["date"] == "2024-03-05"
    assert fields["total_amount"] == "1200.00"
    assert fields["vat_amount"] == "200.00"
    assert fields["currency"] == "USD"
    assert result["status"] == "accepted"


def test_missing_fields_are_reported():
    result = extract_invoice_fields("Invoice Number: 12345\nThank you")
    assert result["status"] == "rejected"
    assert "total_amount" in result["reason"]

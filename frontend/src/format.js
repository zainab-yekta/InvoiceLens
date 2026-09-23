export const FIELD_LABELS = {
  invoice_number: 'Invoice Number',
  date: 'Invoice Date',
  total_amount: 'Total Amount',
  tax_number: 'Tax Number',
  vat_id: 'VAT ID',
  vat_percent: 'VAT %',
  vat_amount: 'VAT Amount',
  exemption_reason: 'Exemption Reason',
};

export const AMOUNT_FIELDS = ['total_amount', 'vat_amount'];

// Amounts are stored as plain numbers ("1785.00"); show them the way the invoice wrote them.
// German invoices get 1.785,00 and English ones get 1,785.00.
export function formatAmount(value, language) {
  if (value === null || value === undefined || value === '') return '–';
  const number = Number(value);
  if (Number.isNaN(number)) return value;
  return number.toLocaleString(language === 'de' ? 'de-DE' : 'en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// "2025-07-28" or "2025-07-28T21:06:51" -> "28.07.2025"
export function formatDate(value) {
  if (!value) return '–';
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[3]}.${match[2]}.${match[1]}` : value;
}

export function missingFields(fields, mandatory) {
  return mandatory.filter((key) => !String(fields[key] ?? '').trim());
}

export function errorText(err, fallback) {
  return err.response?.data?.detail || fallback;
}

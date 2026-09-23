import React, { useEffect, useState } from 'react';

// Saved invoices use the database column names (issue_date instead of date)
const EDIT_FIELDS = [
  ['invoice_number', 'Invoice Number'],
  ['issue_date', 'Invoice Date'],
  ['total_amount', 'Total Amount'],
  ['currency', 'Currency'],
  ['tax_number', 'Tax Number'],
  ['vat_id', 'VAT ID'],
  ['vat_percent', 'VAT %'],
  ['vat_amount', 'VAT Amount'],
  ['exemption_reason', 'Exemption Reason'],
];

function EditInvoiceModal({ invoice, onSave, onClose, saving }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(EDIT_FIELDS.map(([key]) => [key, invoice[key] ?? '']))
  );

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const handleSubmit = (e) => {
    e.preventDefault();
    // Only send what changed, so untouched values are saved exactly as they were
    const changed = Object.fromEntries(
      Object.entries(values).filter(([key, value]) => value !== (invoice[key] ?? ''))
    );
    onSave(changed);
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal card" role="dialog" aria-modal="true" aria-label="Edit invoice" onSubmit={handleSubmit}>
        <header className="card-header">
          <h2>Edit invoice {invoice.invoice_number}</h2>
        </header>
        <div className="card-body">
          <p className="modal-hint">
            Amounts and dates can be typed in German or English format (1.785,00 or 1,785.00, 28.07.2025).
          </p>
          <div className="field-grid">
            {EDIT_FIELDS.map(([key, label]) => (
              <label className={`field ${key === 'exemption_reason' ? 'span-4' : ''}`} key={key}>
                <span className="field-label">{label}</span>
                <input
                  type="text"
                  aria-label={label}
                  value={values[key]}
                  onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                />
              </label>
            ))}
          </div>
        </div>
        <footer className="card-footer">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={saving}>Save changes</button>
        </footer>
      </form>
    </div>
  );
}

export default EditInvoiceModal;

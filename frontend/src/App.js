import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import UploadCard from './components/UploadCard';
import ExtractedFields from './components/ExtractedFields';
import InvoiceTable from './components/InvoiceTable';
import { FIELD_LABELS, formatAmount, formatDate, missingFields, errorText } from './format';
import './App.css';

axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

const SAVED_COLUMNS = [
  { label: '#', render: (_, idx) => idx + 1 },
  { label: 'Processing Date', render: (inv) => formatDate(inv.processing_date) },
  { label: 'Invoice No', render: (inv) => inv.invoice_number },
  { label: 'Issue Date', render: (inv) => formatDate(inv.issue_date) },
  { label: 'Tax No', render: (inv) => inv.tax_number || '–' },
  { label: 'VAT %', render: (inv) => (inv.vat_percent ? `${inv.vat_percent} %` : '–') },
  { label: 'VAT Amount', render: (inv) => formatAmount(inv.vat_amount, inv.language) },
  { label: 'Total', render: (inv) => <b>{formatAmount(inv.total_amount, inv.language)}</b> },
  { label: 'Exemption Reason', render: (inv) => inv.exemption_reason || '–' },
];

const REJECTED_COLUMNS = [
  { label: '#', render: (_, idx) => idx + 1 },
  { label: 'Rejection Date', render: (inv) => formatDate(inv.rejection_date) },
  { label: 'Invoice No', render: (inv) => inv.invoice_number || '–' },
  { label: 'Issue Date', render: (inv) => formatDate(inv.issue_date) },
  { label: 'Reason', render: (inv) => inv.reason || '–' },
];

function App() {
  const [file, setFile] = useState(null);
  const [extracted, setExtracted] = useState(null);
  const [editedFields, setEditedFields] = useState({});
  const [fieldsBeforeEdit, setFieldsBeforeEdit] = useState({});
  const [editMode, setEditMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [invoices, setInvoices] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [dateRange, setDateRange] = useState({ from: '', to: '' });
  const [dateType, setDateType] = useState('processing_date');

  const mandatory = extracted?.mandatory_fields || [];
  const missing = extracted ? missingFields(editedFields, mandatory) : [];

  const fetchInvoices = useCallback(async () => {
    try {
      const res = await axios.get('/get_invoices');
      setInvoices(res.data.accepted || []);
      setRejected(res.data.rejected || []);
    } catch (err) {
      toast.error('Could not load invoices. Is the backend running on port 8000?');
    }
  }, []);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  const handleFileSelect = (selected) => {
    setFile(selected);
    setExtracted(null);
    setEditMode(false);
  };

  const handleProceed = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    try {
      const res = await axios.post('/extract_fields', formData);
      setExtracted(res.data);
      setEditedFields(res.data.fields || {});
      setEditMode(false);
    } catch (err) {
      toast.error(errorText(err, 'Something went wrong while reading the invoice.'));
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!extracted || missing.length > 0) return;
    setBusy(true);
    try {
      await axios.post('/save_invoice', {
        fields: editedFields,
        used_ocr: extracted.used_ocr || false,
        language: extracted.language,
      });
      toast.success(`Invoice ${editedFields.invoice_number} saved`);
      fetchInvoices();
      resetView();
    } catch (err) {
      toast.error(errorText(err, 'Could not save the invoice.'));
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    const reason = missing.length > 0
      ? `Missing fields: ${missing.map((key) => FIELD_LABELS[key]).join(', ')}`
      : 'Rejected by reviewer';

    setBusy(true);
    try {
      await axios.post('/reject_invoice', {
        invoice_number: editedFields.invoice_number || '',
        issue_date: editedFields.date || '',
        reason,
      });
      toast.info('Invoice moved to rejected invoices');
      fetchInvoices();
      resetView();
    } catch (err) {
      toast.error(errorText(err, 'Could not reject the invoice.'));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = () => {
    setFieldsBeforeEdit(editedFields);
    setEditMode(true);
  };

  const cancelEdit = () => {
    setEditedFields(fieldsBeforeEdit);
    setEditMode(false);
  };

  const resetView = () => {
    setExtracted(null);
    setFile(null);
    setEditMode(false);
    setEditedFields({});
  };

  const downloadExcel = async (type) => {
    if (!dateRange.from || !dateRange.to) {
      toast.warn('Please choose both a From and a To date first.');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('type', type);
      formData.append('date_type', dateType);
      formData.append('from_date', dateRange.from);
      formData.append('to_date', dateRange.to);

      const res = await axios.post('/export_excel', formData, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${type}_invoices_${dateRange.from}_${dateRange.to}.xlsx`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('Export failed. Please try again or check the server.');
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Invoice Tool</h1>
        <p>Extract, review and export German and English invoices</p>
      </header>

      <main className="app-main">
        <div className="grid-top">
          <UploadCard
            file={file}
            onFileSelect={handleFileSelect}
            onProceed={handleProceed}
            loading={loading}
          />
          <ExtractedFields
            extracted={extracted}
            fields={editedFields}
            missing={missing}
            editMode={editMode}
            busy={busy}
            onChange={(key, value) => setEditedFields((prev) => ({ ...prev, [key]: value }))}
            onEdit={startEdit}
            onDone={() => setEditMode(false)}
            onCancel={cancelEdit}
            onUpload={handleUpload}
            onReject={handleReject}
          />
        </div>

        <section className="card export-bar">
          <span className="export-bar-title">Export date range</span>
          <label>
            Filter by
            <select value={dateType} onChange={(e) => setDateType(e.target.value)}>
              <option value="processing_date">Processing Date</option>
              <option value="issue_date">Issue Date</option>
            </select>
          </label>
          <label>
            From
            <input
              type="date"
              value={dateRange.from}
              onChange={(e) => setDateRange((prev) => ({ ...prev, from: e.target.value }))}
            />
          </label>
          <label>
            To
            <input
              type="date"
              value={dateRange.to}
              onChange={(e) => setDateRange((prev) => ({ ...prev, to: e.target.value }))}
            />
          </label>
        </section>

        <div className="grid-bottom">
          <InvoiceTable
            title="Saved Invoices"
            count={invoices.length}
            columns={SAVED_COLUMNS}
            rows={invoices}
            emptyText="No saved invoices yet."
            exportLabel="Export Accepted"
            exportStyle="btn-primary"
            onExport={() => downloadExcel('accepted')}
          />
          <InvoiceTable
            title="Rejected Invoices"
            count={rejected.length}
            columns={REJECTED_COLUMNS}
            rows={rejected}
            emptyText="No rejected invoices."
            exportLabel="Export Rejected"
            exportStyle="btn-outline"
            onExport={() => downloadExcel('rejected')}
          />
        </div>
      </main>

      <ToastContainer position="bottom-right" autoClose={4000} newestOnTop />
    </div>
  );
}

export default App;

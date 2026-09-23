import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { ToastContainer, toast } from 'react-toastify';
import UploadCard from './components/UploadCard';
import ExtractedFields from './components/ExtractedFields';
import InvoiceTable from './components/InvoiceTable';
import EditInvoiceModal from './components/EditInvoiceModal';
import { FIELD_LABELS, formatAmount, formatDate, inDateRange, missingFields, errorText } from './format';
import './App.css';

axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

const LANGUAGE_NAMES = { de: 'German', en: 'English' };

// Tags are stored as "food, travel"; show each one as a small chip
function TagList({ tags }) {
  const list = (tags || '').split(',').map((t) => t.trim()).filter(Boolean);
  if (list.length === 0) return '';
  return (
    <span className="tag-list">
      {list.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
    </span>
  );
}

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
  const [history, setHistory] = useState([]);
  const [dateRange, setDateRange] = useState({ from: '', to: '' });
  const [dateType, setDateType] = useState('processing_date');
  const [editingInvoice, setEditingInvoice] = useState(null);

  const mandatory = extracted?.mandatory_fields || [];
  const missing = extracted ? missingFields(editedFields, mandatory) : [];

  const fetchInvoices = useCallback(async () => {
    try {
      const res = await axios.get('/get_invoices');
      setInvoices(res.data.accepted || []);
      setRejected(res.data.rejected || []);
      setHistory(res.data.history || []);
    } catch (err) {
      toast.error('Could not load invoices. Is the backend running on port 8000?');
    }
  }, []);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  // The date filter applies to all three tables and to the Excel export
  const filterActive = Boolean(dateRange.from || dateRange.to);
  const byDate = (row) => inDateRange(row[dateType], dateRange.from, dateRange.to);
  const shownInvoices = invoices.filter(byDate);
  const shownRejected = rejected.filter(byDate);
  const shownHistory = history.filter(byDate);

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

  // Sent with both Upload and Reject so the history keeps the full record and the original file
  const decisionDetails = () => ({
    fields: editedFields,
    language: extracted.language,
    used_ocr: extracted.used_ocr || false,
    tags: extracted.tags || [],
    upload_id: extracted.upload_id,
    original_filename: extracted.original_filename,
  });

  const handleUpload = async () => {
    if (!extracted || missing.length > 0) return;
    setBusy(true);
    try {
      await axios.post('/save_invoice', decisionDetails());
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
        ...decisionDetails(),
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

  const saveEditedInvoice = async (changes) => {
    if (Object.keys(changes).length === 0) {
      setEditingInvoice(null);
      return;
    }
    setBusy(true);
    try {
      await axios.put(`/update_invoice/${editingInvoice.id}`, changes);
      toast.success(`Invoice ${changes.invoice_number || editingInvoice.invoice_number} updated`);
      setEditingInvoice(null);
      fetchInvoices();
    } catch (err) {
      toast.error(errorText(err, 'Could not update the invoice.'));
    } finally {
      setBusy(false);
    }
  };

  const deleteRow = async (path, label) => {
    if (!window.confirm(`Delete ${label}? The record stays in the invoice history.`)) return;
    try {
      await axios.delete(path);
      toast.info(`${label} deleted`);
      fetchInvoices();
    } catch (err) {
      toast.error(errorText(err, `Could not delete ${label}.`));
    }
  };

  const downloadExcel = async (type) => {
    try {
      const formData = new FormData();
      formData.append('type', type);
      formData.append('date_type', dateType);
      if (dateRange.from) formData.append('from_date', dateRange.from);
      if (dateRange.to) formData.append('to_date', dateRange.to);

      const res = await axios.post('/export_excel', formData, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }));
      const range = filterActive ? `_${dateRange.from || 'start'}_${dateRange.to || 'today'}` : '_all';
      const link = document.createElement('a');
      link.href = url;
      link.download = `${type}_invoices${range}.xlsx`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error('Export failed. Please try again or check the server.');
    }
  };

  const savedColumns = [
    { label: '#', render: (_, idx) => idx + 1 },
    { label: 'Processing Date', render: (inv) => formatDate(inv.processing_date) },
    { label: 'Invoice No', render: (inv) => inv.invoice_number },
    { label: 'Tags', render: (inv) => <TagList tags={inv.tags} /> },
    { label: 'Issue Date', render: (inv) => formatDate(inv.issue_date) },
    { label: 'Tax No', render: (inv) => inv.tax_number || '' },
    { label: 'VAT %', render: (inv) => (inv.vat_percent ? `${inv.vat_percent} %` : '') },
    { label: 'VAT Amount', render: (inv) => formatAmount(inv.vat_amount, inv.language, inv.currency) },
    { label: 'Total', render: (inv) => <b>{formatAmount(inv.total_amount, inv.language, inv.currency)}</b> },
    {
      label: 'Actions',
      sticky: true,
      render: (inv) => (
        <span className="row-actions">
          <button className="btn btn-small btn-outline" onClick={() => setEditingInvoice(inv)}>Edit</button>
          <button
            className="btn btn-small btn-danger-outline"
            onClick={() => deleteRow(`/delete_invoice/${inv.id}`, `invoice ${inv.invoice_number}`)}
          >
            Delete
          </button>
        </span>
      ),
    },
  ];

  const rejectedColumns = [
    { label: '#', render: (_, idx) => idx + 1 },
    { label: 'Rejection Date', render: (inv) => formatDate(inv.rejection_date) },
    { label: 'Invoice No', render: (inv) => inv.invoice_number || '' },
    { label: 'Issue Date', render: (inv) => formatDate(inv.issue_date) },
    { label: 'Reason', render: (inv) => inv.reason || '', wrap: true },
    {
      label: 'Actions',
      sticky: true,
      render: (inv) => (
        <button
          className="btn btn-small btn-danger-outline"
          onClick={() => deleteRow(`/delete_rejected/${inv.id}`, `rejected invoice ${inv.invoice_number}`)}
        >
          Delete
        </button>
      ),
    },
  ];

  const historyColumns = [
    { label: '#', render: (_, idx) => idx + 1 },
    { label: 'Decided On', render: (h) => formatDate(h.processing_date) },
    {
      label: 'Status',
      render: (h) => (
        <span className={`status-pill ${h.status === 'accepted' ? 'status-ok' : 'status-bad'}`}>
          {h.status === 'accepted' ? 'Accepted' : 'Rejected'}
        </span>
      ),
    },
    { label: 'Invoice No', render: (h) => h.invoice_number || '' },
    { label: 'Issue Date', render: (h) => formatDate(h.issue_date) },
    { label: 'Total', render: (h) => formatAmount(h.total_amount, h.language, h.currency) },
    { label: 'Language', render: (h) => LANGUAGE_NAMES[h.language] || (h.language || '').toUpperCase() },
    { label: 'Tags', render: (h) => <TagList tags={h.tags} /> },
    { label: 'Reason', render: (h) => h.reason || '', wrap: true },
    {
      label: 'Original File',
      render: (h) => (h.has_file ? (
        <a
          className="file-link"
          href={`${axios.defaults.baseURL}/files/${h.id}`}
          target="_blank"
          rel="noreferrer"
          title={h.original_filename}
        >
          {h.original_filename || 'Open file'}
        </a>
      ) : ''),
    },
  ];

  const filteredEmpty = 'No invoices in this date range.';

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>InvoiceLens</h1>
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

        <section className="card export-bar" aria-label="Date filter">
          <span className="export-bar-title">
            Date filter
            <span className="export-bar-hint">Filters the tables below and the Excel export</span>
          </span>
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
              aria-label="From date"
              value={dateRange.from}
              onChange={(e) => setDateRange((prev) => ({ ...prev, from: e.target.value }))}
            />
          </label>
          <label>
            To
            <input
              type="date"
              aria-label="To date"
              value={dateRange.to}
              onChange={(e) => setDateRange((prev) => ({ ...prev, to: e.target.value }))}
            />
          </label>
          <button
            className="btn btn-ghost"
            onClick={() => setDateRange({ from: '', to: '' })}
            disabled={!filterActive}
          >
            Clear
          </button>
        </section>

        <div className="grid-bottom">
          <InvoiceTable
            title="Saved Invoices"
            total={invoices.length}
            columns={savedColumns}
            rows={shownInvoices}
            emptyText="No saved invoices yet."
            filteredEmptyText={filteredEmpty}
            exportLabel="Export Accepted"
            exportStyle="btn-primary"
            onExport={() => downloadExcel('accepted')}
          />
          <InvoiceTable
            title="Rejected Invoices"
            total={rejected.length}
            columns={rejectedColumns}
            rows={shownRejected}
            emptyText="No rejected invoices."
            filteredEmptyText={filteredEmpty}
            exportLabel="Export Rejected"
            exportStyle="btn-outline"
            onExport={() => downloadExcel('rejected')}
          />
        </div>

        <InvoiceTable
          title="Invoice History"
          subtitle="Every accepted and rejected invoice, with a link to the original file. Kept even when an invoice is edited or deleted above."
          total={history.length}
          columns={historyColumns}
          rows={shownHistory}
          emptyText="Invoices you upload or reject will be recorded here."
          filteredEmptyText={filteredEmpty}
        />
      </main>

      {editingInvoice && (
        <EditInvoiceModal
          invoice={editingInvoice}
          saving={busy}
          onSave={saveEditedInvoice}
          onClose={() => setEditingInvoice(null)}
        />
      )}

      <ToastContainer position="bottom-right" autoClose={4000} newestOnTop />
    </div>
  );
}

export default App;

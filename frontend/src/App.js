import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

axios.defaults.baseURL = 'http://127.0.0.1:8000';

function App() {
  const [file, setFile] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfVisible, setPdfVisible] = useState(true);
  const [extracted, setExtracted] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [rejected, setRejected] = useState([]);
  const [dateRange, setDateRange] = useState({ from: '', to: '' });
  const [dateType, setDateType] = useState('processing_date');
  const [errorMessage, setErrorMessage] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [editedFields, setEditedFields] = useState({});

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      const res = await axios.get('/get_invoices');
      setInvoices(res.data.accepted || []);
      setRejected(res.data.rejected || []);
    } catch (err) {
      setErrorMessage("Failed to load invoices");
    }
  };

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    setFile(selected);
    setPdfUrl(URL.createObjectURL(selected));
    setExtracted(null);
    setErrorMessage('');
  };

  const handleProceed = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('/extract_fields', formData);
      console.log("Extracted response:", res.data);
      setExtracted(res.data);
      setEditedFields(res.data.fields || {});
      if (res.data.status === 'rejected') {
        setErrorMessage('⚠️ Mandatory fields missing. Please reject or fix.');
      } else {
        setErrorMessage('');
      }
    } catch {
      setErrorMessage('An error occurred during extraction.');
    }
  };

  const handleUpload = async () => {
    if (!extracted || extracted.status !== 'accepted') return;

    const mandatoryFields = ['invoice_number', 'date', 'total_amount'];
    const missing = mandatoryFields.filter(field => !editedFields[field]);

    if (missing.length > 0) {
      setErrorMessage(`Missing fields: ${missing.join(', ')}`);
      return;
    }

    try {
      await axios.post('/save_invoice', {
        fields: editedFields,
        accepted: true,
        used_ocr: extracted.used_ocr || false,
      });
      fetchInvoices();
      resetView();
    } catch (err) {
      if (err.response?.status === 409) {
        setErrorMessage("❗ Invoice already exists.");
      } else {
        setErrorMessage("❌ Failed to save invoice: " + err.response?.data?.detail || 'Server error');
      }
    }
  };

  const handleReject = async () => {
    const mandatoryFields = ['invoice_number', 'issue_date', 'tax_number', 'vat_percent', 'vat_amount', 'vat_id', 'total_amount'];
    const missingFields = mandatoryFields.filter(field => !editedFields[field]);
    const reasonText = missingFields.length > 0
      ? `Missing fields: ${missingFields.join(', ')}`
      : 'Missing mandatory fields';

    try {
      await axios.post('/reject_invoice', {
        invoice_number: editedFields.invoice_number || "UNKNOWN",
        issue_date: editedFields.date || "",
        reason: reasonText,
      });
      fetchInvoices();
      resetView();
    } catch (err) {
      if (err.response?.status === 409) {
        setErrorMessage("❗ Invoice already exists.");
      } else {
        setErrorMessage("❌ Failed to reject invoice: " + err.response?.data?.detail || 'Server error');
      }
    }
  };

  const resetView = () => {
    setExtracted(null);
    setFile(null);
    setPdfUrl(null);
    setPdfVisible(false);
    setErrorMessage('');
    setEditMode(false);
    setEditedFields({});
  };

  const downloadExcel = async (type) => {
    if (!dateRange.from || !dateRange.to) {
      setErrorMessage("❗ Please select both From and To dates.");
      return;
    }

    try {
      const formData = new FormData();
      formData.append('type', type);
      formData.append('date_type', dateType);
      formData.append('from_date', dateRange.from);
      formData.append('to_date', dateRange.to);

      const res = await axios.post('/export_excel', formData, {
        responseType: 'blob',
      });

      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });

      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = `${type}_invoices.xlsx`;
      link.click();
      setErrorMessage('');
    } catch (err) {
      console.error("❌ Failed to download Excel:", err);
      setErrorMessage("Export failed. Please try again or check the server.");
    }
  };

  return (
    <div className="page-wrapper">
      <div className="sidebar">Invoice Tool</div>
      <div className="main-content">
        {errorMessage && <div className="alert-box">{errorMessage}</div>}

        {/* Upload Section */}
        <div className="card upload-card">
          <h2>Upload & Extract Invoice</h2>
          <input type="file" onChange={handleFileChange} />
          {pdfUrl && (
            <>
              <button onClick={() => setPdfVisible(!pdfVisible)}>
                {pdfVisible ? "Minimize PDF" : "Maximize PDF"}
              </button>
              {pdfVisible && (
                <div className="pdf-preview">
                  <embed src={pdfUrl} width="100%" height="400px" />
                  <button onClick={handleProceed}>Proceed</button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Extracted Fields Section */}
        {extracted && (
          <div className="card fields-section">
            <h3>
              Extracted Fields:
              {extracted.used_ocr && <span className="ocr-badge">OCR Used</span>}
              {extracted.language && (
                <span className="lang-badge">Language: {extracted.language.toUpperCase()}</span>
              )}
            </h3>

            <div className="tags-line">
              {extracted.tags?.length > 0 && (
                <p><b>Tags:</b> {extracted.tags.join(', ')}</p>
              )}
            </div>

            {editMode ? (
              <div>
                {Object.entries(editedFields).map(([key, val]) => (
                  <div className="form-row" key={key}>
                    <label>{key}:</label>
                    <input
                      type="text"
                      value={val || ''}
                      onChange={(e) =>
                        setEditedFields(prev => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                  </div>
                ))}
                <button onClick={() => {
                  setEditMode(false);
                }}>Save Changes</button>
                <button onClick={() => setEditMode(false)}>Cancel</button>
              </div>
            ) : (
              <ul className="field-list">
                {Object.entries(editedFields).map(([key, val]) => (
                  <li key={key}><b>{key}:</b> {val || '—'}</li>
                ))}
              </ul>
            )}

            <p>Status: <strong>{extracted.status}</strong></p>
            {extracted.language_warning && <p className="warning">{extracted.language_warning}</p>}
            {extracted.status === 'rejected' && extracted.reason && (
              <p className="error">Reason: {extracted.reason}</p>
            )}

            {!editMode && (
              <button onClick={() => setEditMode(true)}>Fix / Edit</button>
            )}
            <button onClick={handleUpload} disabled={extracted.status !== 'accepted'}>
              Upload
            </button>
            <button onClick={handleReject}>Reject</button>
          </div>
        )}

        {/* Date Filter Shared Section */}
        <div className="card export-section">
          <label><b>Filter by Date Type:</b></label>
          <select value={dateType} onChange={e => setDateType(e.target.value)}>
            <option value="processing_date">Processing Date</option>
            <option value="issue_date">Issue Date</option>
          </select>
          <input type="date" value={dateRange.from} onChange={e => setDateRange(prev => ({ ...prev, from: e.target.value }))} />
          <input type="date" value={dateRange.to} onChange={e => setDateRange(prev => ({ ...prev, to: e.target.value }))} />
        </div>

        {/* Saved Invoices Table */}
        <div className="card">
          <h3>Saved Invoices</h3>
          <div className="scrollable-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Processing Date</th>
                  <th>Invoice No</th>
                  <th>Issue Date</th>
                  <th>Tax No</th>
                  <th>VAT %</th>
                  <th>VAT Amount</th>
                  <th>Total</th>
                  <th>Exemption Reason</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, idx) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td>{inv.processing_date || '-'}</td>
                    <td>{inv.invoice_number}</td>
                    <td>{inv.issue_date}</td>
                    <td>{inv.tax_number}</td>
                    <td>{inv.vat_percent}</td>
                    <td>{inv.vat_amount}</td>
                    <td>{inv.total_amount}</td>
                    <td>{inv.exemption_reason || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button onClick={() => downloadExcel('accepted')}>Export Accepted</button>
        </div>

        {/* Rejected Invoices Table */}
        <div className="card">
          <h3>Rejected Invoices</h3>
          <div className="scrollable-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Rejection Date</th>
                  <th>Invoice No</th>
                  <th>Issue Date</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {rejected.map((inv, idx) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    <td>{inv.rejection_date || 'N/A'}</td>
                    <td>{inv.invoice_number || 'N/A'}</td>
                    <td>{inv.issue_date || 'N/A'}</td>
                    <td>{inv.reason || 'Invalid Fields'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button onClick={() => downloadExcel('rejected')}>Export Rejected</button>
        </div>
      </div>
    </div>
  );
}

export default App;

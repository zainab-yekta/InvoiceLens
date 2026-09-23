import React from 'react';
import { FIELD_LABELS, AMOUNT_FIELDS, formatAmount, formatDate } from '../format';

const WIDE_FIELDS = { invoice_number: 'span-2', exemption_reason: 'span-4' };

function displayValue(key, value, language) {
  if (AMOUNT_FIELDS.includes(key)) return formatAmount(value, language);
  if (key === 'date') return formatDate(value);
  if (key === 'vat_percent' && value) return `${value} %`;
  return value || '–';
}

function ExtractedFields({
  extracted, fields, missing, editMode, busy,
  onChange, onEdit, onDone, onCancel, onUpload, onReject,
}) {
  if (!extracted) {
    return (
      <section className="card">
        <header className="card-header">
          <h2>Extracted Fields</h2>
        </header>
        <div className="card-body empty-state">
          Choose an invoice and click <b>Proceed</b>. The fields found in it will show up here for review.
        </div>
      </section>
    );
  }

  const accepted = missing.length === 0;

  return (
    <section className="card">
      <header className="card-header">
        <h2>Extracted Fields</h2>
        <span className={`status-pill ${accepted ? 'status-ok' : 'status-bad'}`}>
          {accepted ? 'Ready to upload' : 'Needs review'}
        </span>
      </header>
      <div className="card-body">
        <div className="badges">
          {extracted.used_ocr && <span className="badge badge-ocr">OCR Used</span>}
          {extracted.language && (
            <span className="badge badge-lang">Language: {extracted.language.toUpperCase()}</span>
          )}
          {extracted.tags?.length > 0 && (
            <span className="tags">
              Tags:
              {extracted.tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}
            </span>
          )}
        </div>

        {extracted.language_warning && <p className="note note-warning">{extracted.language_warning}</p>}

        <div className="field-grid">
          {Object.keys(FIELD_LABELS).map((key) => {
            const isMissing = missing.includes(key);
            return (
              <label className={`field ${WIDE_FIELDS[key] || ''}`} key={key}>
                <span className="field-label">
                  {FIELD_LABELS[key]}
                  {isMissing && <span className="field-required"> · missing</span>}
                </span>
                <input
                  type="text"
                  className={isMissing ? 'input-missing' : ''}
                  readOnly={!editMode}
                  value={editMode ? fields[key] ?? '' : displayValue(key, fields[key], extracted.language)}
                  onChange={(e) => onChange(key, e.target.value)}
                />
              </label>
            );
          })}
        </div>

        {extracted.reason && !extracted.reason.startsWith('Missing') && (
          <p className="note note-warning">{extracted.reason}</p>
        )}
        {!accepted && (
          <p className="note note-error">
            Missing: {missing.map((k) => FIELD_LABELS[k]).join(', ')}.
            {' '}Click <b>Fix / Edit</b> to fill them in, or reject the invoice.
          </p>
        )}

        <div className="actions">
          {editMode ? (
            <>
              <button className="btn btn-outline" onClick={onDone}>Done</button>
              <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
            </>
          ) : (
            <button className="btn btn-outline" onClick={onEdit}>Fix / Edit</button>
          )}
          <span className="actions-spacer" />
          <button className="btn btn-primary" onClick={onUpload} disabled={!accepted || busy}>Upload</button>
          <button className="btn btn-danger-outline" onClick={onReject} disabled={busy}>Reject</button>
        </div>
      </div>
    </section>
  );
}

export default ExtractedFields;

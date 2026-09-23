import React from 'react';

// columns: [{ label, render(row) }]
function InvoiceTable({ title, count, columns, rows, emptyText, exportLabel, exportStyle, onExport }) {
  return (
    <section className="card">
      <header className="card-header">
        <h2>{title}</h2>
        <span className="count">{count}</span>
      </header>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((col) => <th key={col.label}>{col.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td className="empty-row" colSpan={columns.length}>{emptyText}</td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={row.id ?? idx}>
                  {columns.map((col) => <td key={col.label}>{col.render(row, idx)}</td>)}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <footer className="card-footer">
        <button className={`btn ${exportStyle}`} onClick={onExport}>
          {exportLabel}
        </button>
      </footer>
    </section>
  );
}

export default InvoiceTable;

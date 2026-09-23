import React from 'react';

// columns: [{ label, render(row, index), wrap, sticky }]
// wrap lets long text like reasons break lines; sticky keeps a column (Actions) pinned to the right edge
// total: number of rows before the date filter, so the header can say "2 of 5"
function InvoiceTable({
  title, subtitle, total, columns, rows, emptyText, filteredEmptyText,
  exportLabel, exportStyle, onExport,
}) {
  const filtered = rows.length !== total;

  return (
    <section className="card" aria-label={title}>
      <header className="card-header">
        <div>
          <h2>{title}</h2>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
        <span className="count" title={filtered ? 'Rows shown / all rows' : 'Rows'}>
          {filtered ? `${rows.length} of ${total}` : total}
        </span>
      </header>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((col) => <th key={col.label} className={col.sticky ? 'cell-sticky' : undefined}>{col.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td className="empty-row" colSpan={columns.length}>
                  {total > 0 ? filteredEmptyText : emptyText}
                </td>
              </tr>
            ) : (
              rows.map((row, idx) => (
                <tr key={row.id ?? idx}>
                  {columns.map((col) => (
                    <td key={col.label} className={[col.wrap && 'cell-wrap', col.sticky && 'cell-sticky'].filter(Boolean).join(' ') || undefined}>
                      {col.render(row, idx)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {exportLabel && (
        <footer className="card-footer">
          <button className={`btn ${exportStyle}`} onClick={onExport}>
            {exportLabel}
          </button>
        </footer>
      )}
    </section>
  );
}

export default InvoiceTable;

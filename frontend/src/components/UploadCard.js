import React, { useEffect, useRef, useState } from 'react';

const ACCEPTED_TYPES = '.pdf,.png,.jpg,.jpeg,.bmp';

function UploadCard({ file, onFileSelect, onProceed, loading }) {
  const inputRef = useRef(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      if (inputRef.current) inputRef.current.value = '';
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pickFile = (selected) => {
    // Cancelling the file dialog gives no file; keep the current one
    if (selected) onFileSelect(selected);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files[0]);
  };

  const isPdf = file?.type === 'application/pdf' || file?.name.toLowerCase().endsWith('.pdf');

  return (
    <section className="card">
      <header className="card-header">
        <h2>Upload Invoice</h2>
      </header>
      <div className="card-body">
        <label
          className={`dropzone${dragging ? ' dropzone-active' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            onChange={(e) => pickFile(e.target.files[0])}
          />
          <span className="dropzone-title">{file ? file.name : 'Choose file'}</span>
          <span className="dropzone-hint">
            {file ? 'Click to choose a different file' : 'or drag it here · PDF, PNG, JPG or BMP'}
          </span>
        </label>

        <button
          className="btn btn-primary btn-block"
          onClick={onProceed}
          disabled={!file || loading}
        >
          {loading && <span className="spinner" aria-hidden="true" />}
          {loading ? 'Reading invoice…' : 'Proceed'}
        </button>

        {previewUrl && (
          <div className="preview">
            {isPdf ? (
              <embed src={previewUrl} type="application/pdf" title="Invoice preview" />
            ) : (
              <img src={previewUrl} alt="Invoice preview" />
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export default UploadCard;

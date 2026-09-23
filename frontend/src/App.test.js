import React from 'react';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import App from './App';

// axios ships as an ES module that Jest can't load, so replace it completely
jest.mock('axios', () => ({
  __esModule: true,
  default: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn(), defaults: {} },
}));

const DATA = {
  accepted: [
    {
      id: 2, processing_date: '2025-06-01T10:00:00', invoice_number: 'RE-2', issue_date: '2025-05-20',
      tax_number: '12/345', vat_percent: '19', vat_amount: '285.00', total_amount: '1785.00',
      language: 'de', currency: 'EUR',
    },
    {
      id: 1, processing_date: '2025-01-10T09:00:00', invoice_number: 'INV-1', issue_date: '2024-12-30',
      tax_number: '555', vat_percent: '20', vat_amount: '200.00', total_amount: '1200.00',
      language: 'en', currency: 'USD',
    },
  ],
  rejected: [
    {
      id: 7, processing_date: '2025-06-02T08:00:00', rejection_date: '2025-06-02T08:00:00',
      invoice_number: 'RE-9', issue_date: '', reason: 'Missing fields: Tax Number',
    },
  ],
  history: [
    {
      id: 11, processing_date: '2025-06-02T08:00:00', status: 'rejected', invoice_number: 'RE-9',
      reason: 'Missing fields: Tax Number', language: 'de', tags: 'travel', has_file: true,
      original_filename: 'rechnung.pdf',
    },
    {
      id: 10, processing_date: '2025-01-10T09:00:00', status: 'accepted', invoice_number: 'INV-1',
      total_amount: '1200.00', language: 'en', currency: 'USD', has_file: false,
    },
  ],
};

const table = (name) => screen.getByRole('region', { name });

async function renderLoaded() {
  render(<App />);
  const saved = await screen.findByRole('region', { name: 'Saved Invoices' });
  await within(saved).findByText('RE-2');
  return saved;
}

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: DATA });
  window.URL.createObjectURL = jest.fn(() => 'blob:x');
  window.URL.revokeObjectURL = jest.fn();
});

test('amounts show the currency in the format of each invoice', async () => {
  const saved = await renderLoaded();
  expect(within(saved).getByText(/1\.785,00\s€/)).toBeInTheDocument();
  expect(within(saved).getByText('$1,200.00')).toBeInTheDocument();
});

test('the date filter narrows all three tables', async () => {
  await renderLoaded();

  fireEvent.change(screen.getByLabelText('From date'), { target: { value: '2025-03-01' } });

  expect(within(table('Saved Invoices')).queryByText('INV-1')).not.toBeInTheDocument();
  expect(within(table('Saved Invoices')).getByText('RE-2')).toBeInTheDocument();
  expect(within(table('Saved Invoices')).getByText('1 of 2')).toBeInTheDocument();
  expect(within(table('Rejected Invoices')).getByText('RE-9')).toBeInTheDocument();
  expect(within(table('Invoice History')).getByText('1 of 2')).toBeInTheDocument();

  // Filter by issue date instead: RE-2 was issued in 2025, INV-1 in 2024
  fireEvent.change(screen.getByDisplayValue('Processing Date'), { target: { value: 'issue_date' } });
  fireEvent.change(screen.getByLabelText('From date'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('To date'), { target: { value: '2024-12-31' } });
  expect(within(table('Saved Invoices')).getByText('INV-1')).toBeInTheDocument();
  expect(within(table('Saved Invoices')).queryByText('RE-2')).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Clear' }));
  expect(within(table('Saved Invoices')).getByText('RE-2')).toBeInTheDocument();
  expect(within(table('Saved Invoices')).getByText('INV-1')).toBeInTheDocument();
});

test('the export sends the same date range as the tables', async () => {
  axios.post.mockResolvedValue({ data: new Blob() });
  // jsdom can't follow the download link, so just record that it was clicked
  const download = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  await renderLoaded();

  fireEvent.change(screen.getByLabelText('From date'), { target: { value: '2025-03-01' } });
  fireEvent.click(screen.getByRole('button', { name: 'Export Accepted' }));

  await waitFor(() => expect(download).toHaveBeenCalled());
  const form = axios.post.mock.calls[0][1];
  expect(form.get('from_date')).toBe('2025-03-01');
  expect(form.get('to_date')).toBeNull();
  download.mockRestore();
});

test('the history links to the original file', async () => {
  await renderLoaded();
  const link = within(table('Invoice History')).getByRole('link', { name: 'rechnung.pdf' });
  expect(link).toHaveAttribute('href', expect.stringMatching(/\/files\/11$/));
  expect(link).toHaveAttribute('target', '_blank');
});

test('saved invoices can be edited and deleted, rejected ones deleted', async () => {
  axios.put.mockResolvedValue({ data: {} });
  axios.delete.mockResolvedValue({ data: {} });
  window.confirm = jest.fn(() => true);
  const saved = await renderLoaded();

  fireEvent.click(within(saved).getAllByRole('button', { name: 'Edit' })[0]);
  const dialog = screen.getByRole('dialog', { name: 'Edit invoice' });
  fireEvent.change(within(dialog).getByLabelText('Total Amount'), { target: { value: '2.000,00' } });
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save changes' }));
  await waitFor(() => expect(axios.put).toHaveBeenCalledWith('/update_invoice/2', { total_amount: '2.000,00' }));

  fireEvent.click(within(saved).getAllByRole('button', { name: 'Delete' })[1]);
  await waitFor(() => expect(axios.delete).toHaveBeenCalledWith('/delete_invoice/1'));

  fireEvent.click(within(table('Rejected Invoices')).getByRole('button', { name: 'Delete' }));
  await waitFor(() => expect(axios.delete).toHaveBeenCalledWith('/delete_rejected/7'));
});

test('fixing a missing field makes the invoice uploadable', async () => {
  axios.post.mockResolvedValueOnce({
    data: {
      status: 'rejected', language: 'en', used_ocr: false, tags: ['office'],
      reason: 'Missing fields: tax_number',
      mandatory_fields: ['invoice_number', 'date', 'total_amount', 'tax_number', 'vat_amount'],
      upload_id: 'abc.pdf', original_filename: 'invoice.pdf',
      fields: {
        invoice_number: 'INV-7', date: '2024-02-12', total_amount: '2940.00',
        tax_number: '', vat_amount: '490.00', currency: 'USD',
      },
    },
  });
  await renderLoaded();

  const input = document.querySelector('input[type="file"]');
  fireEvent.change(input, { target: { files: [new File(['x'], 'invoice.pdf', { type: 'application/pdf' })] } });
  fireEvent.click(screen.getByRole('button', { name: 'Proceed' }));

  const upload = await screen.findByRole('button', { name: 'Upload' });
  expect(upload).toBeDisabled();
  expect(screen.getByText('Needs review')).toBeInTheDocument();
  expect(screen.getByLabelText('Total Amount')).toHaveValue('$2,940.00');

  fireEvent.click(screen.getByRole('button', { name: 'Fix / Edit' }));
  fireEvent.change(screen.getByLabelText('Tax Number'), { target: { value: '98-765' } });
  expect(upload).toBeEnabled();

  // Cancel puts the original (empty) value back
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(upload).toBeDisabled();

  fireEvent.click(screen.getByRole('button', { name: 'Fix / Edit' }));
  fireEvent.change(screen.getByLabelText('Tax Number'), { target: { value: '98-765' } });
  axios.post.mockResolvedValueOnce({ data: { status: 'saved' } });
  fireEvent.click(upload);
  await waitFor(() => expect(axios.post).toHaveBeenLastCalledWith('/save_invoice', expect.objectContaining({
    upload_id: 'abc.pdf',
    original_filename: 'invoice.pdf',
    tags: ['office'],
    fields: expect.objectContaining({ tax_number: '98-765', currency: 'USD' }),
  })));
});

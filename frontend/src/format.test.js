import { formatAmount, formatDate, inDateRange, missingFields } from './format';

describe('formatAmount', () => {
  test('German invoices use German number format and the currency', () => {
    expect(formatAmount('1785.00', 'de', 'EUR')).toMatch(/^1\.785,00\s€$/);
  });

  test('English invoices use English number format and the currency', () => {
    expect(formatAmount('1200', 'en', 'USD')).toBe('$1,200.00');
    expect(formatAmount('50', 'en', 'GBP')).toBe('£50.00');
  });

  test('works without a currency', () => {
    expect(formatAmount('1785', 'de', '')).toBe('1.785,00');
  });

  test('keeps an unknown currency code readable instead of crashing', () => {
    expect(formatAmount('10', 'en', 'XX')).toBe('10.00 XX');
  });

  test('shows old unparsable values and blanks as they are', () => {
    expect(formatAmount('1.200.00', 'de', 'EUR')).toBe('1.200.00');
    expect(formatAmount('', 'de', 'EUR')).toBe('–');
  });
});

test('formatDate turns ISO dates into dd.mm.yyyy', () => {
  expect(formatDate('2025-07-28')).toBe('28.07.2025');
  expect(formatDate('2025-07-28T21:06:51.123')).toBe('28.07.2025');
  expect(formatDate('2014.04.22')).toBe('2014.04.22');
  expect(formatDate('')).toBe('–');
});

describe('inDateRange', () => {
  test('no range means everything matches', () => {
    expect(inDateRange('', '', '')).toBe(true);
  });

  test('both ends are inclusive and timestamps count by their day', () => {
    expect(inDateRange('2025-07-01T23:59:00', '2025-07-01', '2025-07-31')).toBe(true);
    expect(inDateRange('2025-07-31', '2025-07-01', '2025-07-31')).toBe(true);
    expect(inDateRange('2025-08-01', '2025-07-01', '2025-07-31')).toBe(false);
  });

  test('either end can be open', () => {
    expect(inDateRange('2030-01-01', '2025-01-01', '')).toBe(true);
    expect(inDateRange('2020-01-01', '', '2024-12-31')).toBe(true);
  });

  test('rows without a readable date are hidden while filtering', () => {
    expect(inDateRange('', '2025-01-01', '')).toBe(false);
    expect(inDateRange('2014.04.22', '2000-01-01', '')).toBe(false);
  });
});

test('missingFields treats blanks and spaces as missing', () => {
  expect(missingFields({ a: '1', b: ' ', c: null }, ['a', 'b', 'c', 'd'])).toEqual(['b', 'c', 'd']);
});

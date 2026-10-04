import { download } from './utils';
export function exportCSV(name: string, rows: (string | number | null)[][]) {
  const encode = (v: string | number | null) => { let text = String(v ?? ''); if (/^[=+@\-\t\r]/.test(text)) text = `'${text}`; return `"${text.replaceAll('"', '""')}"`; };
  download(name, rows.map(row => row.map(encode).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
}

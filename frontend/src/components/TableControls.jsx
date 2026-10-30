import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import './DashboardShell.css';

export default function TableControls({ rows, searchText, children, pageSize = 10, label = 'items' }) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => String(searchText(row) || '').toLocaleLowerCase().includes(needle));
  }, [rows, query, searchText]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount - 1);
  const visible = filtered.slice(safePage * pageSize, (safePage + 1) * pageSize);

  return <div>
    <div className="ts-table-tools">
      <label className="relative block w-full max-w-[340px]">
        <span className="sr-only">Search {label}</span>
        <Search size={16} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input className="ts-table-search pl-9" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder={`Search ${label}…`} />
      </label>
      <span className="whitespace-nowrap text-xs text-slate-500">{filtered.length} {label}</span>
    </div>
    {children(visible)}
    <div className="ts-table-pagination" aria-label={`${label} pagination`}>
      <span>Page {safePage + 1} of {pageCount}</span>
      <button type="button" className="ts-page-button" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>Previous</button>
      <button type="button" className="ts-page-button" disabled={safePage + 1 >= pageCount} onClick={() => setPage(safePage + 1)}>Next</button>
    </div>
  </div>;
}

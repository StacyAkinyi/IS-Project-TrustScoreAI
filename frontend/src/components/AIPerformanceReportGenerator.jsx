import React, { useEffect, useState } from 'react';

const API = 'http://127.0.0.1:8000/api/v1';
const GROUP_LABELS = {
  operational_quality: 'Operational quality',
  delivery_timeliness: 'Delivery and timeliness',
  customer_outcomes: 'Customer outcomes',
  risk_controls: 'Risk and controls',
};
const DIMENSION_LABELS = {
  communication: 'Communication',
  collaboration: 'Collaboration',
  compliance_awareness: 'Compliance awareness',
  learning_development: 'Learning and development',
};

export default function AIPerformanceReportGenerator() {
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState('');
  const [periodType, setPeriodType] = useState('semiannual');
  const [periodNumber, setPeriodNumber] = useState('1');
  const [year, setYear] = useState(new Date().getFullYear());
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [error, setError] = useState('');
  const role = localStorage.getItem('user_role') || 'employee';
  const token = localStorage.getItem('access_token');
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => {
    fetch(`${API}/reporting/employees`, { headers })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not load report access.');
        const rows = Array.isArray(data) ? data : [];
        setEmployees(rows);
        if (rows.length) setEmployeeId(String(rows[0].employee_id));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoadingEmployees(false));
  }, []);

  useEffect(() => {
    if (!employeeId) return;
    fetch(`${API}/ai-reports/${employeeId}`, { headers })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Could not load saved reports.');
        setReports(Array.isArray(data) ? data : []);
        setSelectedReport((current) => current || (Array.isArray(data) && data.length ? data[0] : null));
      })
      .catch((err) => setError(err.message));
  }, [employeeId]);

  const generate = async (event) => {
    event.preventDefault();
    if (!employeeId || loading) return;
    setLoading(true);
    setError('');
    try {
      const payload = { employee_id: Number(employeeId), period_type: periodType, year: Number(year) };
      if (periodType !== 'annual') payload.period_number = Number(periodNumber);
      const response = await fetch(`${API}/ai-reports/generate`, {
        method: 'POST', headers, body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not generate this report.');
      setSelectedReport(data);
      setReports((current) => [data, ...current.filter((row) => row.report_id !== data.report_id)]);
    } catch (err) {
      setError(err.message || 'Could not generate this report.');
    } finally {
      setLoading(false);
    }
  };

  const label = (id) => employees.find((item) => String(item.employee_id) === String(id))?.full_name || `Employee ${id}`;
  const options = periodType === 'quarterly' ? [1, 2, 3, 4] : [1, 2];
  const monthLabel = (code) => code?.replace('-Q', ' · Quarter ').replace('-H', ' · Half-year ') || '';

  return <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
    <div>
      <h3 className="text-lg font-bold text-blue-900">AI performance report</h3>
      <p className="mt-1 text-sm text-slate-600">Generate a quarterly, semiannual, or annual report from the available telemetry and work-related feedback.</p>
    </div>
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
      Feedback text is sent to the configured AI service after basic identifier masking. AI ratings are draft suggestions, not human-reviewed labels or employment decisions. Missing evidence is shown as unrated. Do not enter customer or account details in feedback.
    </div>
    <form onSubmit={generate} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {role !== 'employee' && <label className="text-xs font-semibold text-slate-700">Employee<select value={employeeId} onChange={(event) => { setEmployeeId(event.target.value); setSelectedReport(null); }} className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm" disabled={loadingEmployees || !employees.length}>{employees.map((item) => <option key={item.employee_id} value={item.employee_id}>{item.full_name} · {item.role}</option>)}</select></label>}
      <label className="text-xs font-semibold text-slate-700">Report period<select value={periodType} onChange={(event) => { setPeriodType(event.target.value); setPeriodNumber('1'); }} className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"><option value="quarterly">Quarterly</option><option value="semiannual">Semiannual</option><option value="annual">Annual</option></select></label>
      {periodType !== 'annual' && <label className="text-xs font-semibold text-slate-700">{periodType === 'quarterly' ? 'Quarter' : 'Half-year'}<select value={periodNumber} onChange={(event) => setPeriodNumber(event.target.value)} className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm">{options.map((number) => <option key={number} value={number}>{periodType === 'quarterly' ? `Quarter ${number}` : `Half ${number}`}</option>)}</select></label>}
      <label className="text-xs font-semibold text-slate-700">Year<input type="number" min="2000" max={new Date().getFullYear() + 1} value={year} onChange={(event) => setYear(event.target.value)} className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm" /></label>
      <button disabled={loading || loadingEmployees || !employeeId} className="self-end rounded bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-400">{loading ? 'Generating…' : 'Generate report'}</button>
    </form>
    {error && <p role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {reports.length > 0 && <label className="block text-xs font-semibold text-slate-700">Saved reports<select value={selectedReport?.report_id || ''} onChange={(event) => setSelectedReport(reports.find((row) => String(row.report_id) === event.target.value) || null)} className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm">{reports.map((row) => <option key={row.report_id} value={row.report_id}>{monthLabel(row.period_code)} · {label(row.employee_id)} · {new Date(row.generated_at).toLocaleString()}</option>)}</select></label>}
    {selectedReport && <div className="space-y-4 rounded-lg border border-slate-200 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-bold text-slate-900">{label(selectedReport.employee_id)} · {monthLabel(selectedReport.period_code) || selectedReport.period_code}</h4><span className="rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-900">AI draft · human review needed</span></div>
      <p className="text-sm leading-6 text-slate-700">{selectedReport.narrative?.summary}</p>
      <div><h5 className="mb-2 text-sm font-bold text-blue-900">Telemetry groups</h5><div className="grid gap-2 sm:grid-cols-2">{Object.entries(selectedReport.telemetry_groups || {}).map(([key, group]) => <div key={key} className="rounded border border-slate-200 p-3"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-slate-800">{GROUP_LABELS[key] || group.label}</span><StateBadge state={group.state} /></div><p className="mt-1 text-sm text-slate-600">Group score: {group.score_0_100 == null ? 'No data' : `${group.score_0_100}/100`}</p><ul className="mt-2 space-y-1 text-xs text-slate-600">{(group.metrics || []).map((metric) => <li key={metric.key}>{metric.label}: {metric.mean == null ? 'No data' : `${metric.mean}${metric.unit}`} · {metric.state}</li>)}</ul></div>)}</div></div>
      <div><h5 className="mb-2 text-sm font-bold text-blue-900">Feedback dimensions · provisional AI ratings</h5><div className="grid gap-2 sm:grid-cols-2">{Object.entries(DIMENSION_LABELS).map(([key, title]) => { const item = selectedReport.feedback_dimensions?.[key]; return <div key={key} className="rounded border border-slate-200 p-3"><div className="flex items-center justify-between gap-2"><span className="font-semibold text-slate-800">{title}</span><span className="text-sm font-bold text-blue-800">{item?.score_1_5 == null ? 'Unrated' : `${item.score_1_5}/5`}</span></div><p className="mt-1 text-xs text-slate-600">{item?.evidence_summary || 'No feedback evidence available.'}</p></div>; })}</div></div>
      {selectedReport.narrative?.strengths?.length > 0 && <div><h5 className="font-bold text-slate-800">Evidence-backed strengths</h5><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">{selectedReport.narrative.strengths.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
      {selectedReport.narrative?.development_priorities?.length > 0 && <div><h5 className="font-bold text-slate-800">Development priorities</h5><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">{selectedReport.narrative.development_priorities.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
      <p className="border-t pt-2 text-xs text-slate-500">Coverage: {selectedReport.data_coverage?.telemetry_record_count || 0} telemetry records across {selectedReport.data_coverage?.telemetry_months_covered || 0} months; {selectedReport.data_coverage?.feedback_item_count || 0} feedback items. Sources: {(selectedReport.data_coverage?.data_sources || []).join(', ') || 'none'}.</p>
    </div>}
    {!selectedReport && !loading && <p className="text-xs text-slate-500">Choose a period and generate a report. Saved reports appear here.</p>}
  </section>;
}

function StateBadge({ state }) {
  const classes = state === 'Safe' ? 'bg-green-100 text-green-800' : state === 'Warning' ? 'bg-orange-100 text-orange-800' : state === 'Danger' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600';
  return <span className={`rounded px-2 py-1 text-xs font-bold ${classes}`}>{state || 'No data'}</span>;
}

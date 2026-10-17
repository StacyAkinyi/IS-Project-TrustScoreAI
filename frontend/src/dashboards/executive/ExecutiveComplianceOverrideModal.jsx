import React, { useState } from 'react';

const API = 'http://127.0.0.1:8000/api/v1';

export default function ExecutiveComplianceOverrideModal({ report, executiveId, onClose, onUpdated }) {
  const [justification, setJustification] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const isApplying = !report.compliance_override_status;

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true); setError('');
    try {
      const response = await fetch(`${API}/executives/override-compliance`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          report_id: report.report_id,
          executive_id: executiveId,
          compliance_override_status: isApplying,
          justification: justification.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not update the compliance override');
      onUpdated(data);
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4" role="presentation">
    <section role="dialog" aria-modal="true" aria-labelledby="compliance-override-title" className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div><h2 id="compliance-override-title" className="text-xl font-bold text-blue-900">Regulatory compliance override</h2><p className="mt-1 text-sm text-slate-600">Report #{report.report_id} · Employee #{report.employee_id} · Trust score {Number(report.unified_trust_score).toFixed(1)}%</p></div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-slate-900">✕</button>
      </div>
      <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">This records an executive compliance exception. It does not change the calculated trust score, telemetry, or source records. Use the reason field for the decision basis and supporting reference.</p>
      <form onSubmit={submit} className="mt-5 space-y-4">
        <label className="block text-sm font-semibold text-slate-800">{isApplying ? 'Reason for applying the override' : 'Reason for removing the override'}
          <textarea required minLength={10} maxLength={2000} rows={4} value={justification} onChange={(event) => setJustification(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm font-normal" placeholder="Explain the regulatory exception and include a policy, case, or evidence reference where available." />
          <span className="mt-1 block text-xs font-normal text-slate-500">10–2,000 characters. Each change is recorded with the executive and timestamp.</span>
        </label>
        {report.compliance_override_reason && <div className="rounded-lg bg-slate-50 p-3 text-sm"><p className="font-semibold text-slate-700">Most recent action reason</p><p className="mt-1 whitespace-pre-wrap text-slate-600">{report.compliance_override_reason}</p>{report.compliance_override_updated_at && <p className="mt-1 text-xs text-slate-500">{new Date(report.compliance_override_updated_at).toLocaleString()}</p>}</div>}
        <div><h3 className="text-sm font-bold text-slate-800">Override history</h3>{(report.override_audit || []).length === 0 ? <p className="mt-1 text-sm text-slate-500">No override actions have been recorded.</p> : <ol className="mt-2 max-h-48 space-y-2 overflow-y-auto">{report.override_audit.map((event) => <li key={event.audit_id} className="rounded border border-slate-200 p-3 text-sm"><p className="font-semibold text-slate-800">{event.new_status ? 'Override applied' : 'Override removed'} · Executive #{event.executive_id}</p><p className="mt-1 whitespace-pre-wrap text-slate-600">{event.justification}</p><p className="mt-1 text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</p></li>)}</ol>}</div>
        {error && <p role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
        <div className="flex justify-end gap-3 border-t pt-4"><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button type="submit" disabled={saving || justification.trim().length < 10} className={`rounded-lg px-4 py-2 text-sm font-bold text-white disabled:opacity-50 ${isApplying ? 'bg-amber-700' : 'bg-slate-700'}`}>{saving ? 'Saving…' : isApplying ? 'Apply override' : 'Remove override'}</button></div>
      </form>
    </section>
  </div>;
}

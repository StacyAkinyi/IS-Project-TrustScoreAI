import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

function localDateTimeMinimum() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

export default function ScheduleAppraisalMeetingModal({ appraisal, supervisorId, onClose, onSuccess }) {
  const [scheduledAt, setScheduledAt] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !saving) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, saving]);

  const submit = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/appraisals/${appraisal.appraisal_id}/meetings`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ scheduled_at: new Date(scheduledAt).toISOString() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Could not book the meeting (HTTP ${response.status})`);
      onSuccess?.(data);
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  return createPortal(<div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-950/70 p-4">
    <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
      <div className="mb-4 flex items-start justify-between gap-4"><div><h2 className="text-xl font-bold text-blue-900">Schedule appraisal meeting</h2><p className="mt-1 text-sm text-slate-600">{appraisal.employee_name} · {appraisal.period_code}</p></div><button type="button" onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-slate-900">✕</button></div>
      <p className="mb-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-900">Choose a future date and time. The booking will appear prominently in the employee’s appraisal section, where they can confirm it.</p>
      {error && <p role="alert" className="mb-4 rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <form onSubmit={submit} className="space-y-4"><label className="block text-sm font-semibold text-slate-800">Meeting date and time<input type="datetime-local" required min={localDateTimeMinimum()} value={scheduledAt} onChange={(event) => setScheduledAt(event.target.value)} className="mt-2 block w-full rounded-lg border border-slate-300 p-3" /></label><div className="flex justify-end gap-3"><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button type="submit" disabled={saving || !scheduledAt} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{saving ? 'Booking…' : 'Book meeting'}</button></div></form>
    </div>
  </div>, document.body);
}

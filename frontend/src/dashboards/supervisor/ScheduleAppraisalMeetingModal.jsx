import React, { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';

const pad = (value) => String(value).padStart(2, '0');
const asDateKey = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const startOfDay = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

function initialMeetingDate() {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return asDateKey(tomorrow);
}

export default function ScheduleAppraisalMeetingModal({ employee, appraisal = null, supervisorId, onClose, onSuccess }) {
  const [selectedDate, setSelectedDate] = useState(initialMeetingDate);
  const [time, setTime] = useState('10:00');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const selected = useMemo(() => new Date(`${selectedDate}T00:00:00`), [selectedDate]);
  const month = useMemo(() => new Date(selected.getFullYear(), selected.getMonth(), 1), [selected]);
  const today = startOfDay(new Date());
  const firstMondayIndex = (month.getDay() + 6) % 7;
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const calendarCells = [
    ...Array(firstMondayIndex).fill(null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];
  while (calendarCells.length % 7) calendarCells.push(null);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && !saving) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, saving]);

  const changeMonth = (amount) => {
    const next = new Date(month.getFullYear(), month.getMonth() + amount, 1);
    const firstDay = new Date(next.getFullYear(), next.getMonth(), 1);
    if (amount < 0 && new Date(next.getFullYear(), next.getMonth() + 1, 0) < today) return;
    if (amount > 0 || firstDay >= new Date(today.getFullYear(), today.getMonth(), 1)) {
      setSelectedDate(asDateKey(new Date(next.getFullYear(), next.getMonth(), Math.max(1, selected.getDate()))));
    }
  };

  const submit = async (event) => {
    event?.preventDefault();
    if (saving) return;
    setSaving(true);
    setError('');
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 15000);
    try {
      if (!selectedDate || !time) throw new Error('Choose a meeting date and time.');
      const meetingDate = new Date(`${selectedDate}T${time}:00`);
      if (Number.isNaN(meetingDate.getTime())) throw new Error('Choose a valid meeting date and time.');
      if (meetingDate <= new Date()) throw new Error('Choose a future date and time.');
      const endpoint = appraisal
        ? `http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/appraisals/${appraisal.appraisal_id}/meetings`
        : `http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/employees/${employee.employee_id}/meetings`;
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ scheduled_at: meetingDate.toISOString() }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Could not book the meeting (HTTP ${response.status})`);
      onSuccess?.(data);
    } catch (err) {
      setError(err.name === 'AbortError'
        ? 'The booking request timed out. Please check that the API is running, then try again.'
        : err.message);
    } finally {
      window.clearTimeout(timeoutId);
      setSaving(false);
    }
  };

  const monthLabel = month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const formattedDate = selected.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });

  return createPortal(<div className="fixed inset-0 z-[9999] flex items-center justify-center overflow-y-auto bg-slate-950/70 p-4" role="presentation">
    <section role="dialog" aria-modal="true" aria-labelledby="schedule-meeting-title" className="my-auto w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 id="schedule-meeting-title" className="text-xl font-bold text-blue-900">{appraisal ? 'Schedule appraisal meeting' : 'Schedule a check-in meeting'}</h2>
          <p className="mt-1 text-sm text-slate-600">{employee.full_name}{appraisal ? ` · ${appraisal.period_code}` : ` · Employee #${employee.employee_id}`}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="text-slate-500 hover:text-slate-900">✕</button>
      </div>
      <p className="mb-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-900">Select a future date below. The booking will appear in the employee’s appraisal section for confirmation.</p>
      {error && <p role="alert" className="mb-4 rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      <form onSubmit={(event) => event.preventDefault()} className="space-y-4">
        <div className="rounded-xl border border-slate-200 p-4">
          <div className="mb-4 flex items-center justify-between">
            <button type="button" onClick={() => changeMonth(-1)} aria-label="Previous month" className="rounded-lg border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-50">‹</button>
            <h3 className="font-semibold text-slate-800">{monthLabel}</h3>
            <button type="button" onClick={() => changeMonth(1)} aria-label="Next month" className="rounded-lg border border-slate-300 px-3 py-2 text-slate-700 hover:bg-slate-50">›</button>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-500">
            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => <div key={day} className="py-2">{day}</div>)}
            {calendarCells.map((day, index) => {
              if (!day) return <div key={`empty-${index}`} />;
              const date = new Date(month.getFullYear(), month.getMonth(), day);
              const dateKey = asDateKey(date);
              const isPast = startOfDay(date) < today;
              const isSelected = dateKey === selectedDate;
              return <button key={dateKey} type="button" disabled={isPast} aria-pressed={isSelected} onClick={() => setSelectedDate(dateKey)} className={`rounded-lg py-2.5 text-sm transition ${isSelected ? 'bg-blue-700 font-bold text-white' : isPast ? 'cursor-not-allowed text-slate-300' : 'text-slate-700 hover:bg-blue-50'}`}>{day}</button>;
            })}
          </div>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <p className="text-sm font-medium text-slate-700">Selected: {formattedDate}</p>
          <label className="text-sm font-semibold text-slate-800">Time<input type="time" value={time} onChange={(event) => setTime(event.target.value)} className="mt-1 block rounded-lg border border-slate-300 p-2.5" /></label>
        </div>
        <div className="flex justify-end gap-3 border-t border-slate-100 pt-4">
          <button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">Cancel</button>
          <button type="button" onClick={submit} disabled={saving} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">{saving ? 'Booking…' : 'Book meeting'}</button>
        </div>
      </form>
    </section>
  </div>, document.body);
}

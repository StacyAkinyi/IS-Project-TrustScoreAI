import React, { useEffect, useState } from 'react';

export default function SemiannualAppraisalModal({ employee, supervisorId, onClose, onSuccess }) {
  const [template, setTemplate] = useState(null);
  const [answers, setAnswers] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    fetch(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/appraisal-template`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load the appraisal form');
      setTemplate(data);
    }).catch((err) => setError(err.message)).finally(() => setLoading(false));
  }, [supervisorId, token]);

  const setAnswer = (id, answer) => setAnswers((current) => ({ ...current, [id]: answer }));
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true); setError('');
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/appraisals`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ employee_id: employee.employee_id, answers: template.questions.map((question) => ({ question_id: question.id, answer: answers[question.id] })) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not save this appraisal');
      onSuccess?.(data);
      onClose();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  };

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4">
    <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
      <div className="mb-5 flex items-start justify-between gap-4"><div><h2 className="text-xl font-bold text-blue-900">Semiannual performance appraisal</h2><p className="mt-1 text-sm text-slate-600">{employee.full_name} · Employee #{employee.employee_id} · {template?.period_code || 'Loading period…'}</p></div><button type="button" onClick={onClose} className="text-slate-500 hover:text-slate-900" aria-label="Close">✕</button></div>
      <p className="mb-5 rounded-lg bg-blue-50 p-3 text-sm text-blue-900">Use the same questions for every employee. Base answers on work evidence and role expectations. Avoid assumptions about personality, health, family, age, or other personal traits. When submitted, this form is saved against this employee and appears in their dashboard, where they can request clarification.</p>
      {loading && <p className="text-slate-600">Loading questions…</p>}
      {error && <p role="alert" className="mb-4 rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {template && <form onSubmit={submit} className="space-y-6">
        <section className="space-y-4"><h3 className="font-bold text-slate-800">5 Yes / No questions</h3>{template.questions.filter((q) => q.type === 'yes_no').map((q, i) => <fieldset key={q.id} className="rounded-lg border border-slate-200 p-4"><legend className="px-1 text-sm font-medium text-slate-800">{i + 1}. {q.prompt}</legend><div className="mt-3 flex gap-5">{[true, false].map((value) => <label key={String(value)} className="flex items-center gap-2 text-sm"><input type="radio" name={q.id} checked={answers[q.id] === value} onChange={() => setAnswer(q.id, value)} required />{value ? 'Yes' : 'No'}</label>)}</div></fieldset>)}</section>
        <section className="space-y-4"><h3 className="font-bold text-slate-800">5 Open-ended questions</h3>{template.questions.filter((q) => q.type === 'open').map((q, i) => <label key={q.id} className="block text-sm font-medium text-slate-800">{i + 1}. {q.prompt}<textarea required minLength={10} maxLength={3000} rows={3} value={answers[q.id] || ''} onChange={(e) => setAnswer(q.id, e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm font-normal" /></label>)}</section>
        <div className="flex justify-end gap-3"><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button type="submit" disabled={saving || loading || template.questions.some((q) => answers[q.id] === undefined)} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-400">{saving ? 'Saving…' : 'Submit appraisal'}</button></div>
      </form>}
    </div>
  </div>;
}

import React, { useEffect, useState } from 'react';

export default function SupervisorAppraisalInbox({ employeeId }) {
  const [items, setItems] = useState([]); const [drafts, setDrafts] = useState({}); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const load = async () => {
    const response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/supervisor-appraisals`, { headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Could not load supervisor appraisals'); setItems(data);
  };
  useEffect(() => { load().catch((e) => setError(e.message)).finally(() => setLoading(false)); }, [employeeId]);
  const ask = async (id) => {
    setError(''); setNotice('');
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/supervisor-appraisals/${id}/review-request`, { method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ message: drafts[id] || '' }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || 'Could not send the request');
      setNotice(data.message); await load();
    } catch (e) { setError(e.message); }
  };
  if (loading) return <p className="p-4 text-slate-600">Loading supervisor reviews…</p>;
  return <div className="space-y-4">{notice && <p role="status" className="rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}{error && <p role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}{items.length === 0 && <p className="rounded-lg bg-white p-5 text-sm text-slate-600">No supervisor appraisal has been submitted for you yet.</p>}{items.map((item) => <article key={item.appraisal_id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap justify-between gap-2"><h3 className="font-bold text-blue-900">Supervisor appraisal · {item.period_code}</h3><span className="text-sm text-slate-500">Yes answers: {item.yes_count}/5</span></div><p className="mt-1 text-xs text-slate-500">Submitted {new Date(item.created_at).toLocaleDateString()}</p><div className="mt-4 space-y-3">{item.answers.map((answer) => <div key={answer.id} className="border-t pt-3"><p className="text-sm font-semibold text-slate-800">{answer.prompt}</p><p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{typeof answer.answer === 'boolean' ? (answer.answer ? 'Yes' : 'No') : answer.answer}</p></div>)}</div>{item.review_requested_at ? <p className="mt-4 rounded bg-amber-50 p-3 text-sm text-amber-900">Clarification requested: {item.review_request_text}</p> : <div className="mt-4 border-t pt-4"><label className="block text-sm font-semibold text-slate-800">Need clarification? Send your supervisor a question<textarea minLength={10} maxLength={2000} rows={3} value={drafts[item.appraisal_id] || ''} onChange={(e) => setDrafts((d) => ({ ...d, [item.appraisal_id]: e.target.value }))} className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm font-normal" placeholder="Which part would you like explained?" /></label><button onClick={() => ask(item.appraisal_id)} disabled={(drafts[item.appraisal_id] || '').trim().length < 10} className="mt-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-bold text-white disabled:bg-slate-400">Request clarification</button></div>}</article>)}</div>;
}

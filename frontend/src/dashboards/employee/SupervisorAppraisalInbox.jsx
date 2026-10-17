import React, { useEffect, useState } from 'react';

export default function SupervisorAppraisalInbox({ employeeId }) {
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = async () => {
    const response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/supervisor-appraisals`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not load supervisor appraisals');
    setItems(data);
  };

  useEffect(() => {
    load().catch((e) => setError(e.message)).finally(() => setLoading(false));
  }, [employeeId]);

  const requestReview = async (item) => {
    setBusyId(item.appraisal_id); setError(''); setNotice('');
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/supervisor-appraisals/${item.appraisal_id}/review-request`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: drafts[item.appraisal_id] || '' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not send the review request');
      setNotice(data.message); setExpanded(null); await load();
    } catch (e) { setError(e.message); }
    finally { setBusyId(null); }
  };

  const markSatisfied = async (item) => {
    if (!window.confirm('Mark this appraisal as satisfied? It will be closed and cannot be changed.')) return;
    setBusyId(item.appraisal_id); setError(''); setNotice('');
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/supervisor-appraisals/${item.appraisal_id}/satisfied`, {
        method: 'POST', headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not close this appraisal');
      setNotice(data.message); setExpanded(null); await load();
    } catch (e) { setError(e.message); }
    finally { setBusyId(null); }
  };

  if (loading) return <p className="p-4 text-slate-600">Loading supervisor reviews…</p>;
  return <div className="space-y-4">
    {notice && <p role="status" className="rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
    {error && <p role="alert" className="rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
    {items.length === 0 ? <p className="rounded-lg bg-white p-5 text-sm text-slate-600">No supervisor appraisal has been submitted for you yet.</p> :
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[620px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-3">Appraisal</th><th className="p-3">Submitted</th><th className="p-3">Score</th><th className="p-3">Status</th><th className="p-3">Action</th></tr></thead>
          <tbody>{items.map((item) => {
            const status = item.status || (item.satisfied_at ? 'satisfied' : item.review_requested_at ? 'review_requested' : 'awaiting_employee');
            const statusLabel = { satisfied: 'Satisfied · closed', review_requested: 'Review requested', reviewed: 'Revised · awaiting you', awaiting_employee: 'Awaiting your response' }[status];
            const canMarkSatisfied = status === 'awaiting_employee' || status === 'reviewed';
            const canRequestReview = status === 'awaiting_employee';
            return <React.Fragment key={item.appraisal_id}>
              <tr className="border-t">
                <td className="p-3 font-semibold text-blue-900">Supervisor appraisal · {item.period_code}</td>
                <td className="p-3 text-slate-600">{new Date(item.created_at).toLocaleDateString()}</td>
                <td className="p-3 text-slate-600">Yes {item.yes_count}/5</td>
                <td className="p-3"><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${status === 'satisfied' ? 'bg-green-100 text-green-800' : status === 'review_requested' ? 'bg-amber-100 text-amber-800' : 'bg-blue-50 text-blue-800'}`}>{statusLabel}</span></td>
                <td className="p-3"><button type="button" onClick={() => setExpanded(expanded === item.appraisal_id ? null : item.appraisal_id)} className="font-semibold text-blue-700 hover:underline">{expanded === item.appraisal_id ? 'Hide details' : 'View appraisal'}</button></td>
              </tr>
              {expanded === item.appraisal_id && <tr className="border-t bg-slate-50"><td colSpan="5" className="p-4">
                <div className="space-y-3">{item.answers.map((answer) => <div key={answer.id} className="border-b border-slate-200 pb-3 last:border-0"><p className="font-semibold text-slate-800">{answer.prompt}</p><p className="mt-1 whitespace-pre-wrap text-slate-700">{typeof answer.answer === 'boolean' ? (answer.answer ? 'Yes' : 'No') : answer.answer}</p></div>)}</div>
                {item.review_request_text && <p className="mt-3 rounded bg-amber-100 p-3 text-sm text-amber-900">Your review request: {item.review_request_text}</p>}
                {status === 'review_requested' && <p className="mt-3 text-sm text-amber-800">Your supervisor can revise this appraisal once. You can mark it satisfied after the revision is returned.</p>}
                {status === 'satisfied' && <p className="mt-3 text-sm text-green-800">You marked this appraisal satisfied on {new Date(item.satisfied_at).toLocaleDateString()}. It is now closed.</p>}
                {canMarkSatisfied && <div className="mt-4 flex flex-wrap items-end justify-between gap-4 border-t pt-4">
                  {canRequestReview && <div className="min-w-[260px] flex-1"><label className="block text-sm font-semibold text-slate-800">Need a review? Your supervisor may revise it once.<textarea minLength={10} maxLength={2000} rows={2} value={drafts[item.appraisal_id] || ''} onChange={(e) => setDrafts((d) => ({ ...d, [item.appraisal_id]: e.target.value }))} className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3 text-sm font-normal" placeholder="Explain what needs a review (10–2,000 characters)." /></label><button type="button" onClick={() => requestReview(item)} disabled={busyId === item.appraisal_id || (drafts[item.appraisal_id] || '').trim().length < 10} className="mt-2 rounded-lg border border-blue-700 px-4 py-2 text-sm font-bold text-blue-700 disabled:opacity-50">{busyId === item.appraisal_id ? 'Sending…' : 'Request review'}</button></div>}
                  <button type="button" onClick={() => markSatisfied(item)} disabled={busyId === item.appraisal_id} className="rounded-lg bg-green-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">I am satisfied</button>
                </div>}
              </td></tr>}
            </React.Fragment>;
          })}</tbody>
        </table>
      </div>}
  </div>;
}

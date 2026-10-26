import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

const API = 'http://127.0.0.1:8000';
const LABELS = {
  communication: 'Communication',
  collaboration: 'Collaboration',
  compliance_awareness: 'Compliance awareness',
  learning_development: 'Learning and development',
};

export default function FeedbackReviewQueue({ supervisorId, onChanged }) {
  const [rows, setRows] = useState([]);
  const [decisions, setDecisions] = useState({});
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [year, setYear] = useState(new Date().getFullYear());
  const [half, setHalf] = useState(new Date().getMonth() < 6 ? 1 : 2);
  const token = localStorage.getItem('access_token');

  const loadQueue = useCallback(async () => {
    if (!supervisorId || !token) return;
    setLoading(true);
    setError('');
    try {
      const response = await axios.get(
        API + '/api/v1/supervisors/' + supervisorId + '/feedback-classifications/pending',
        { headers: { Authorization: 'Bearer ' + token } },
      );
      setRows(response.data || []);
      setDecisions((current) => {
        const next = { ...current };
        (response.data || []).forEach((row) => {
          if (!next[row.classification_id]) next[row.classification_id] = row.predicted_direction;
        });
        return next;
      });
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not load feedback awaiting review.');
    } finally {
      setLoading(false);
    }
  }, [supervisorId, token]);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  const runPipeline = async () => {
    setRunning(true);
    setError('');
    setNotice('');
    try {
      const response = await axios.post(
        API + '/api/v1/supervisors/' + supervisorId + '/trust-score-runs',
        { period_type: 'semiannual', year: Number(year), period_number: Number(half) },
        { headers: { Authorization: 'Bearer ' + token } },
      );
      setNotice(
        'Classified appraisal text for ' + response.data.employees_processed +
        ' team members. ' + response.data.awaiting_review +
        ' score run(s) are waiting for review.',
      );
      await loadQueue();
      onChanged?.();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'The appraisal classification could not be completed.');
    } finally {
      setRunning(false);
    }
  };

  const saveDecision = async (row) => {
    setError('');
    setNotice('');
    try {
      await axios.patch(
        API + '/api/v1/feedback-classifications/' + row.classification_id + '/review',
        { decision: decisions[row.classification_id] || row.predicted_direction },
        { headers: { Authorization: 'Bearer ' + token } },
      );
      setRows((current) => current.filter((item) => item.classification_id !== row.classification_id));
      setNotice('Review saved. Confirmed positive or negative evidence can contribute to the score.');
      onChanged?.();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not save this review.');
    }
  };

  return (
    <section className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-blue-900">Appraisal feedback classification</h3>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            The model classifies supervisor and employee answers by competency and direction.
            Review each suggestion. Mixed and neutral answers do not receive a numerical score.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-semibold text-slate-600">Year
            <input className="mt-1 block w-24 rounded border border-slate-300 px-2 py-2 text-sm" type="number" min="2000" max="9998" value={year} onChange={(event) => setYear(event.target.value)} />
          </label>
          <label className="text-xs font-semibold text-slate-600">Half
            <select className="mt-1 block rounded border border-slate-300 px-2 py-2 text-sm" value={half} onChange={(event) => setHalf(event.target.value)}>
              <option value={1}>H1 · Jan–Jun</option>
              <option value={2}>H2 · Jul–Dec</option>
            </select>
          </label>
          <button type="button" onClick={runPipeline} disabled={running || loading} className="rounded bg-indigo-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
            {running ? 'Classifying…' : 'Classify team appraisals'}
          </button>
        </div>
      </div>
      {error && <p role="alert" className="mt-3 rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {notice && <p role="status" className="mt-3 rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-700">{loading ? 'Loading review queue…' : rows.length + ' answers awaiting review'}</p>
        <button type="button" onClick={loadQueue} disabled={loading} className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50">Refresh</button>
      </div>
      {!loading && rows.length === 0 ? (
        <p className="mt-3 rounded bg-slate-50 p-4 text-sm text-slate-600">No model suggestions are waiting for review. Run classification after appraisal answers are available.</p>
      ) : (
        <div className="mt-3 max-h-[620px] space-y-3 overflow-y-auto pr-1">
          {rows.map((row) => (
            <article key={row.classification_id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <strong className="text-slate-800">{row.employee_name}</strong>
                <span className="rounded-full bg-blue-50 px-2 py-1 font-semibold text-blue-800">{LABELS[row.category] || row.category}</span>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-600">{row.source_type === 'supervisor_appraisal' ? 'Supervisor' : 'Employee'} answer</span>
                <span className="text-slate-500">Model suggests {row.predicted_direction} · {Math.round(row.confidence * 100)}% confidence</span>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{row.statement_text}</p>
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="text-xs font-semibold text-slate-600">Your reviewed label
                  <select
                    className="mt-1 block rounded border border-slate-300 px-3 py-2 text-sm"
                    value={decisions[row.classification_id] || row.predicted_direction}
                    onChange={(event) => setDecisions((current) => ({ ...current, [row.classification_id]: event.target.value }))}
                  >
                    <option value="positive">Positive evidence</option>
                    <option value="negative">Negative evidence</option>
                    <option value="mixed">Mixed evidence · no numerical score</option>
                    <option value="neutral">Neutral evidence · no numerical score</option>
                    <option value="exclude">Exclude as not useful evidence</option>
                  </select>
                </label>
                <button type="button" onClick={() => saveDecision(row)} className="rounded bg-blue-700 px-4 py-2 text-sm font-bold text-white">Save review</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
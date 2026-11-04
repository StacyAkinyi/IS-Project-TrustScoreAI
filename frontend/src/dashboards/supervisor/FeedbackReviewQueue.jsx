import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

const API = 'http://127.0.0.1:8000';
const LABELS = {
  communication: 'Communication',
  collaboration: 'Collaboration',
  compliance_awareness: 'Compliance awareness',
  learning_development: 'Learning and development',
};

const KPI_UNITS = {
  transaction_accuracy: '%',
  error_frequencies: ' errors',
  workplan_completion: '%',
  task_deadline_fulfillment_pct: '%',
  loan_processing_turnaround_hours: ' hrs',
  customer_satisfaction: ' / 5',
  complaint_resolution_rate_pct: '%',
  non_performing_credit_pct: '%',
  cash_reconciliation_errors: ' errors',
  compliance_incidents: ' incidents',
};

const periodCode = (year, half) => `${year}-H${half}`;

export default function FeedbackReviewQueue({ supervisorId, onChanged, refreshKey }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [choices, setChoices] = useState({});
  const [savingId, setSavingId] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [half, setHalf] = useState(new Date().getMonth() < 6 ? 1 : 2);
  const token = localStorage.getItem('access_token');

  const loadRuns = useCallback(async () => {
    if (!supervisorId || !token) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        year: String(year), period_type: 'semiannual', period_number: String(half),
      });
      const response = await axios.get(
        `${API}/api/v1/supervisors/${supervisorId}/trust-score-runs?${params.toString()}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      setRuns(response.data || []);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not load automatic classification results.');
    } finally {
      setLoading(false);
    }
  }, [supervisorId, token, year, half, refreshKey]);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  const refreshResults = async () => {
    setNotice('');
    await loadRuns();
    setNotice('Showing the latest automatically classified supervisor answers.');
  };

  const saveCorrection = async (row) => {
    const decision = choices[row.classification_id];
    if (!decision) return;
    setSavingId(row.classification_id);
    setError('');
    try {
      await axios.patch(
        API + '/api/v1/feedback-classifications/' + row.classification_id + '/review',
        { decision },
        { headers: { Authorization: 'Bearer ' + token } },
      );
      setChoices((current) => ({ ...current, [row.classification_id]: '' }));
      await loadRuns();
      onChanged?.();
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not save the supervisor correction.');
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-blue-900">Automatic appraisal classification</h3>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            The model assigns each supervisor answer to zero or more competencies, then predicts its direction within each one. These are automatic results; no answer-by-answer approval is required.
          </p>
          <p className="mt-1 max-w-3xl text-xs text-slate-500">
            Employee self-questionnaires are shown separately as context and are not classified or included in the Trust Score. Mixed and neutral direction predictions do not receive a numeric score. You may correct a label below; corrections are saved for a future training update and do not retrain the model immediately.
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
          <button type="button" onClick={refreshResults} disabled={loading} className="rounded bg-indigo-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
            Refresh results
          </button>
        </div>
      </div>
      {error && <p role="alert" className="mt-3 rounded bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
      {notice && <p role="status" className="mt-3 rounded bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-700">{loading ? 'Loading classification results…' : `${runs.length} employee result(s) · ${periodCode(year, half)}`}</p>
      </div>
      {!loading && runs.length === 0 ? (
        <p className="mt-3 rounded bg-slate-50 p-4 text-sm text-slate-600">No saved results for this period yet. New supervisor forms are classified automatically when submitted; use the H1 seeding command for a one-time synthetic backfill.</p>
      ) : (
        <div className="mt-3 max-h-[680px] space-y-3 overflow-y-auto pr-1">
          {runs.map((run) => (
            <article key={run.run_id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div><strong className="text-slate-800">{run.employee_name || `Employee #${run.employee_id}`}</strong><span className="ml-2 text-xs text-slate-500">{run.period_code}</span></div>
                <span className={`rounded-full px-2 py-1 text-xs font-semibold ${run.score_status === 'ready' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
                  {run.score_status === 'ready' ? `Trust Score ${Number(run.trust_score).toFixed(1)}%` : 'Score incomplete'}
                </span>
              </div>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {Object.entries(run.feedback_groups || {}).map(([category, group]) => (
                  <div key={category} className="rounded bg-slate-50 px-3 py-2 text-xs">
                    <strong className="text-slate-700">{LABELS[category] || category}</strong>
                    <span className="ml-2 font-semibold text-blue-800">{group.score_0_100 == null ? 'No score' : `${Number(group.score_0_100).toFixed(1)}%`}</span>
                    <span className="mt-1 block text-slate-500">+{group.positive_count || 0} positive · −{group.negative_count || 0} negative · {group.mixed_or_neutral_count || 0} mixed/neutral</span>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <h4 className="text-sm font-bold text-slate-800">Telemetry KPI groups</h4>
                <p className="mt-1 text-xs text-slate-500">Each group contributes one of the four KPI scores in the Trust Score.</p>
                <div className="mt-2 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {Object.entries(run.kpi_groups || {}).map(([groupKey, group]) => (
                    <section key={groupKey} className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="flex items-start justify-between gap-2">
                        <strong className="text-xs text-slate-700">{group.label || groupKey.replaceAll('_', ' ')}</strong>
                        <span className="text-xs font-bold text-blue-800">{group.score_0_100 == null ? 'No score' : Number(group.score_0_100).toFixed(1) + '%'}</span>
                      </div>
                      <span className={'mt-2 inline-block rounded px-2 py-0.5 text-[11px] font-semibold ' + (group.state === 'Safe' ? 'bg-green-100 text-green-800' : group.state === 'Warning' ? 'bg-orange-100 text-orange-800' : group.state === 'Danger' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600')}>{group.state || 'No data'}</span>
                      <div className="mt-2 space-y-2">
                        {(group.metrics || []).map((metric) => (
                          <div key={metric.key} className="border-t border-slate-100 pt-2">
                            <div className="flex items-start justify-between gap-2 text-xs">
                              <span className="text-slate-600">{metric.label}</span>
                              <span className="shrink-0 font-semibold text-slate-800">
                                {metric.mean == null ? 'No data' : Number(metric.mean).toLocaleString(undefined, { maximumFractionDigits: 2 }) + (KPI_UNITS[metric.key] || '')}
                              </span>
                            </div>
                            <div className="mt-1 flex items-center justify-between gap-2 text-[11px]">
                              <span className={'rounded px-1.5 py-0.5 font-semibold ' + (metric.state === 'Safe' ? 'bg-green-100 text-green-800' : metric.state === 'Warning' ? 'bg-orange-100 text-orange-800' : metric.state === 'Danger' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600')}>{metric.state || 'No data'}</span>
                              <span className="text-slate-400">n={metric.sample_count || 0}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                {run.data_coverage?.supervisor_answer_count || 0} supervisor answers · {run.data_coverage?.classified_answer_category_count || 0} competency assignments · {run.data_coverage?.unassigned_supervisor_answer_count || 0} answers below every category cutoff
              </p>
              {run.score_status !== 'ready' && (
                <p className="mt-2 rounded bg-amber-50 p-3 text-xs text-amber-900">
                  Trust Score incomplete. Groups without a score: <strong>{[
                    ...Object.values(run.kpi_groups || {}),
                    ...Object.values(run.feedback_groups || {}),
                  ].filter((group) => group.score_0_100 == null).map((group) => group.label).filter(Boolean).join(', ') || 'one or more required groups'}</strong>. Mixed and neutral feedback does not receive a numeric score.
                </p>
              )}
              {(run.data_coverage?.supervisor_answer_count || 0) === 0 && (
                <p className="mt-2 rounded bg-amber-50 p-3 text-xs text-amber-900">
                  No supervisor appraisal answers are available for this period. Category scores and the Trust Score will appear after a completed supervisor form is classified.
                </p>
              )}
              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-semibold text-indigo-700">Show automatic answer classifications ({(run.classifications || []).length})</summary>
                <div className="mt-2 space-y-2">
                  {(run.classifications || []).map((row) => (
                    <div key={row.classification_id} className="rounded border border-slate-100 p-3">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded-full bg-blue-50 px-2 py-1 font-semibold text-blue-800">{LABELS[row.category] || row.category}</span>{row.synthetic_demo && <span className="rounded-full bg-violet-50 px-2 py-1 font-semibold text-violet-800">Synthetic demo</span>}
                        <span className={`rounded-full px-2 py-1 font-semibold ${row.predicted_direction === 'negative' ? 'bg-red-100 text-red-800' : row.predicted_direction === 'positive' ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-700'}`}>{row.predicted_direction} evidence</span>
                        <span className="text-slate-500">Competency {Math.round((row.probabilities?.competency_probability || 0) * 100)}% · direction {Math.round((row.confidence || 0) * 100)}%</span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{row.statement_text}</p>
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        {row.review_status === 'confirmed' && <span className="text-xs text-emerald-700">Supervisor label: {row.confirmed_direction}</span>}
                        {row.review_status === 'excluded' && <span className="text-xs text-slate-500">Excluded by supervisor</span>}
                        <select
                          value={choices[row.classification_id] || ''}
                          onChange={(event) => setChoices((current) => ({ ...current, [row.classification_id]: event.target.value }))}
                          aria-label={'Correct classification for ' + (LABELS[row.category] || row.category)}
                          className="rounded border border-slate-300 bg-white px-2 py-1.5 text-xs"
                        >
                          <option value="">Confirm or correct…</option>
                          <option value="positive">Positive</option>
                          <option value="negative">Negative</option>
                          <option value="mixed">Mixed</option>
                          <option value="neutral">Neutral</option>
                          <option value="exclude">Exclude from scoring</option>
                        </select>
                        <button
                          type="button"
                          onClick={() => saveCorrection(row)}
                          disabled={!choices[row.classification_id] || savingId === row.classification_id}
                          className="rounded bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                        >
                          {savingId === row.classification_id ? 'Saving…' : 'Save correction'}
                        </button>
                      </div>
                    </div>
                  ))}
                  {run.data_coverage?.unassigned_supervisor_answer_count > 0 && <p className="rounded bg-slate-50 p-3 text-xs text-slate-600">Some supervisor answers did not reach any category cutoff, so they were not assigned to a competency.</p>}
                </div>
              </details>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

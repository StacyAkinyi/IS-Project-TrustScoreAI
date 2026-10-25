import React, { useEffect, useState } from 'react';

const API = 'http://127.0.0.1:8000';
const CATEGORY_LABELS = {
  communication: 'Communication',
  collaboration: 'Collaboration',
  learning_development: 'Learning and development',
  compliance_awareness: 'Compliance awareness',
};

export default function AppraisalForm({ userId, employee }) {
  const employeeId = userId ?? employee?.employee_id;
  const [questionnaire, setQuestionnaire] = useState(null);
  const [responses, setResponses] = useState({});
  const [loading, setLoading] = useState(true);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const token = localStorage.getItem('access_token');

  const loadQuestionnaire = async () => {
    if (!employeeId) {
      setError('The employee ID is missing, so the self-questionnaire cannot be loaded.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetch(`${API}/api/v1/employees/${employeeId}/generate-prompt`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load the follow-up questions.');
      setQuestionnaire(data);
      setResponses({});
    } catch (err) {
      setError(err.message || 'Could not load the follow-up questions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadQuestionnaire(); }, [employeeId, token]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!questionnaire?.available) return;
    setSubmitLoading(true);
    setResult(null);
    setError('');
    try {
      const payload = {
        supervisor_appraisal_id: questionnaire.supervisor_appraisal_id,
        generated_questions: questionnaire.questions,
        question_snapshot: questionnaire.question_snapshot,
        responses: questionnaire.question_snapshot.map((question) => ({
          question_id: question.id,
          category: question.category,
          answer: responses[question.id] || '',
        })),
      };
      const response = await fetch(`${API}/evaluate-employee/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not save your self-questionnaire.');
      setResult(data);
      setQuestionnaire({ available: false, questions: [], message: 'Your follow-up for this appraisal has been submitted.' });
    } catch (err) {
      setError(err.message || 'Could not save your self-questionnaire.');
    } finally {
      setSubmitLoading(false);
    }
  };

  return <div className="mx-auto max-w-4xl space-y-6">
    {result && <div role="status" className="space-y-2 rounded-lg border border-green-200 bg-green-50 p-5">
      <h3 className="text-lg font-bold text-green-900">Self-questionnaire submitted</h3>
      <p className="text-sm text-slate-700">{result.message}</p>
    </div>}
    {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
    {loading ? <div className="rounded-lg border border-blue-200 bg-blue-50 p-8 text-center text-blue-900">Preparing your appraisal follow-up…</div> : null}
    {!loading && !error && questionnaire?.available && <>
      <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-5">
        <h2 className="text-xl font-bold text-indigo-900">Follow-up self-questionnaire</h2>
        <p className="mt-1 text-sm text-indigo-800">Based on your supervisor’s Form {questionnaire.form_number} for {questionnaire.period_code}. Your responses are saved with that specific appraisal.</p>
        <p className="mt-2 text-xs text-slate-600">Answer all four open-ended questions. They invite your context and evidence; they do not assign a score.</p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-5">
        {questionnaire.question_snapshot.map((question) => <label key={question.id} className="block rounded-lg border border-slate-200 bg-white p-5 text-sm font-semibold text-slate-800">
          <span className="mb-2 block text-xs font-bold uppercase tracking-wide text-indigo-700">{CATEGORY_LABELS[question.category] || question.category_label}</span>
          {question.text}
          <textarea required minLength={10} maxLength={3000} rows={4} value={responses[question.id] || ''} onChange={(event) => setResponses((current) => ({ ...current, [question.id]: event.target.value }))} placeholder="Add your context, an example, or the support that would help…" className="mt-3 w-full rounded-lg border border-slate-300 p-3 text-sm font-normal focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200" />
        </label>)}
        <button type="submit" disabled={submitLoading} className="w-full rounded-lg bg-blue-700 py-3 font-bold text-white shadow-sm disabled:cursor-not-allowed disabled:bg-blue-400">
          {submitLoading ? 'Saving responses…' : 'Submit self-questionnaire'}
        </button>
      </form>
    </>}
    {!loading && !error && !questionnaire?.available && !result && <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-700">
      {questionnaire?.message || 'A supervisor appraisal must be submitted before your follow-up questionnaire is available.'}
    </div>}
  </div>;
}

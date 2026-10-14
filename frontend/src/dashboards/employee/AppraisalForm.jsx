import React, { useState, useEffect } from 'react';

export default function AppraisalForm({ userId, employee }) {
  const employeeId = userId ?? employee?.employee_id;
  const [aiQuestions, setAiQuestions] = useState([]);
  const [questionSnapshot, setQuestionSnapshot] = useState([]);
  const [formData, setFormData] = useState({ narrative_feedback: '' });
  const [loading, setLoading] = useState(true);
  const [submitLoading, setSubmitLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const token = localStorage.getItem('access_token');

  useEffect(() => {
    const getDynamicPrompt = async () => {
      try {
        setLoading(true);
        setError('');

        const controller = new AbortController();
        const timeoutId = window.setTimeout(() => controller.abort(), 10000);
        let response;
        try {
          response = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/generate-prompt`, {
            headers: { 'Authorization': `Bearer ${token}` },
            signal: controller.signal,
          });
        } finally {
          window.clearTimeout(timeoutId);
        }

        if (!response.ok) throw new Error('Failed to load the appraisal question bank.');

        const data = await response.json();
        // Keep the exact questions returned for this appraisal response.
        console.log("Appraisal questions received:", data);

        // 2. Bulletproof state setting: Handle both new 'questions' array and old 'prompt' string
        if (data.questions && Array.isArray(data.questions)) {
          setAiQuestions(data.questions);
          setQuestionSnapshot(Array.isArray(data.question_snapshot) ? data.question_snapshot : data.questions.map((text) => ({ text, state: "unknown", metric_key: null, metric_label: null, value: null, bank_version: 1 })));
        } else if (data.prompt) {
          // Fallback just in case the backend hasn't updated properly
          const splitQuestions = data.prompt.split('|').map(q => q.trim()).filter(q => q);
          setAiQuestions(splitQuestions.length > 0 ? splitQuestions : [data.prompt]);
        } else {
          setAiQuestions(["Please reflect on your overall performance."]);
        }

      } catch (err) {
        console.error(err);
        setError(err.name === 'AbortError'
          ? 'Loading questions timed out. Check that FastAPI and PostgreSQL are running, then reopen this page.'
          : 'Could not load the appraisal questions. Check that FastAPI and PostgreSQL are running.');
      } finally {
        setLoading(false);
      }
    };

    if (employeeId) {
      getDynamicPrompt();
    } else {
      setError('The employee ID is missing, so appraisal questions cannot be loaded.');
      setLoading(false);
    }
  }, [employeeId, token]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitLoading(true);
    setResult(null);

    try {
      const payload = {
        generated_questions: aiQuestions,
        question_snapshot: questionSnapshot,
        feedback_text: formData.narrative_feedback
      };

      const response = await fetch('http://127.0.0.1:8000/evaluate-employee/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Failed to save your reflection.');

      setResult(data);
      setFormData({ narrative_feedback: '' });
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setSubmitLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {result && (
        <div className="bg-green-50 border border-green-200 p-5 rounded-lg space-y-2 mb-4">
          <h4 className="font-extrabold text-green-900 text-lg">Appraisal Successfully Logged</h4>
          <p className="text-sm text-slate-700">{result.message}</p>
        </div>
      )}

      <div className="my-4">
        {/* ENHANCED LOADING STATE */}
        {loading && (
          <div className="bg-indigo-50 border border-indigo-200 p-8 rounded-lg shadow-sm text-center space-y-4">
            <div className="animate-spin inline-block w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full"></div>
            <div>
              <p className="italic text-indigo-800 font-bold text-lg animate-pulse">
                Reviewing recent telemetry...
              </p>
              <p className="text-sm text-indigo-600 mt-2">
                Preparing three reflection questions from your latest monthly reading and its Safe, Warning, or Danger bands. These prompts support discussion; they do not produce an appraisal score.
              </p>
            </div>
          </div>
        )}

        {/* ERROR STATE */}
        {error && (
          <div className="bg-red-50 border border-red-200 p-5 rounded-lg text-red-700 text-sm shadow-sm">
            <p className="font-bold text-base mb-1">AI Generation Failed</p>
            <p>{error}</p>
          </div>
        )}

        {/* QUESTIONS AND FORM - ONLY VISIBLE WHEN LOADING IS FINISHED */}
        {!loading && !error && aiQuestions.length > 0 && (
          <div className="space-y-6">
            <div className="bg-indigo-50 border border-indigo-200 p-6 rounded-lg shadow-sm">
              <h4 className="text-xs font-extrabold text-indigo-800 uppercase tracking-wider mb-4 border-b border-indigo-200 pb-2">
                Telemetry-informed reflection questions
              </h4>
              <ul className="space-y-3">
                {aiQuestions.map((q, index) => (
                  <li key={index} className="text-sm text-indigo-900 font-medium leading-relaxed">
                    {q}
                  </li>
                ))}
              </ul>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-bold text-slate-700 mb-2">Your Responses & Self-Appraisal</label>
                <textarea 
                  name="narrative_feedback" 
                  rows="6" 
                  value={formData.narrative_feedback} 
                  onChange={handleChange}
                  placeholder="Address the 3 questions above and share your perspective on your performance..."
                  required 
                  className="w-full p-4 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none leading-relaxed shadow-sm"
                />
              </div>

              <button 
                type="submit" 
                disabled={submitLoading}
                className={`w-full py-3 text-white font-bold rounded transition shadow-md ${
                  submitLoading ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-700 hover:bg-blue-800'
                }`}
              >
                {submitLoading ? 'Logging to Database...' : 'Submit Appraisal Responses'}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

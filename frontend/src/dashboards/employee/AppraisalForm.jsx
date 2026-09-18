import React, { useState, useEffect } from 'react';

export default function AppraisalForm({ userId, supervisorId }) {
  const [formData, setFormData] = useState({
    narrative_feedback: ''
  });
  
  const [aiPrompt, setAiPrompt] = useState('Loading your personalized appraisal context...');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const token = localStorage.getItem('access_token');

  // Fetch the AI-generated question when the component loads
  useEffect(() => {
    // In the future, this will hit your FastAPI endpoint that generates questions via NLP.
    // For now, we simulate the AI analyzing their database KPIs and asking a tailored question:
    setTimeout(() => {
      setAiPrompt("Based on your database telemetry, you have consistently hit your loan volume targets this quarter, but your system error frequency spiked slightly last month. How are you finding the current workload, and what operational bottlenecks can we help you resolve?");
    }, 800);
  }, [userId]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResult(null);

    try {
      // We now only send the textual reflection. The backend will automatically 
      // pull the numerical KPIs from the database to run the final ML ensemble!
      const response = await fetch('http://127.0.0.1:8000/evaluate-employee/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          employee_code: `EMP-${userId}`,
          feedback_text: formData.narrative_feedback
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Failed to process qualitative feedback.');

      setResult(data);
    } catch (err) {
      console.error("Appraisal submission error:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded text-sm font-semibold">
          {error}
        </div>
      )}

      {result && (
        <div className="bg-green-50 border border-green-200 p-5 rounded-lg space-y-2">
          <h4 className="font-extrabold text-green-900 text-lg">Reflection Successfully Processed</h4>
          <p className="text-sm text-slate-700"><strong>Sentiment & Trait Alignment:</strong> {result.evaluation_result}</p>
          <p className="text-sm text-slate-700"><strong>NLP Confidence:</strong> {result.confidence_score}%</p>
          <p className="text-xs text-slate-500 mt-1">Your reflection has been merged with your quantitative telemetry to update your unified reliability score.</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* AI Prompt Section */}
        <div className="bg-indigo-50 border border-indigo-200 p-5 rounded-lg">
          <h4 className="text-xs font-bold text-indigo-800 uppercase tracking-wider mb-2">
            AI-Generated Reflection Prompt
          </h4>
          <p className="text-sm text-indigo-900 font-medium italic">
            "{aiPrompt}"
          </p>
        </div>

        {/* Employee Input Section */}
        <div>
          <label className="block text-sm font-bold text-slate-700 mb-2">Your Self-Appraisal & Feedback</label>
          <textarea 
            name="narrative_feedback" 
            rows="6" 
            value={formData.narrative_feedback} 
            onChange={handleChange}
            placeholder="Share your perspective on your performance, workplace challenges, and support needs..."
            required 
            className="w-full p-4 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none leading-relaxed"
          />
        </div>

        <button 
          type="submit" 
          disabled={loading}
          className={`w-full py-3 text-white font-bold rounded transition ${
            loading ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-700 hover:bg-blue-800 shadow-md'
          }`}
        >
          {loading ? 'Analyzing Qualitative Traits via NLP...' : 'Submit Self-Appraisal'}
        </button>
      </form>
    </div>
  );
}
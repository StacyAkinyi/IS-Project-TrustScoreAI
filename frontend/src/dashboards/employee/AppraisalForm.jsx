import React, { useState } from 'react';
import axios from 'axios';

export default function AppraisalForm({ employeeId, supervisorId, onSubmissionSuccess }) {
  const [formData, setFormData] = useState({
    loan_volumes: 100,
    transaction_accuracy: 95.0,
    workplan_completion: 90.0,
    error_frequencies: 1,
    narrative_text: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const token = localStorage.getItem('access_token');
    const payload = {
      ...formData,
      employee_id: employeeId,
      supervisor_id: supervisorId
    };

    try {
      const res = await axios.post('http://127.0.0.1:8000/api/v1/submit-appraisal', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.status === 200) {
        onSubmissionSuccess(res.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to calculate appraisal score.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-md">
      <h3 className="text-lg font-bold text-teal-400 mb-4">Submit AI-Driven Appraisal</h3>
      {error && <p className="text-rose-400 text-sm mb-3 bg-rose-950/50 p-2 rounded">{error}</p>}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Loan Volume Count</label>
            <input
              type="number"
              value={formData.loan_volumes}
              onChange={(e) => setFormData({ ...formData, loan_volumes: parseInt(e.target.value) || 0 })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 focus:outline-none focus:border-teal-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Transaction Accuracy (%)</label>
            <input
              type="number"
              step="0.1"
              value={formData.transaction_accuracy}
              onChange={(e) => setFormData({ ...formData, transaction_accuracy: parseFloat(e.target.value) || 0 })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 focus:outline-none focus:border-teal-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Workplan Completion Rate (%)</label>
            <input
              type="number"
              step="0.1"
              value={formData.workplan_completion}
              onChange={(e) => setFormData({ ...formData, workplan_completion: parseFloat(e.target.value) || 0 })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 focus:outline-none focus:border-teal-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Error Frequency Count</label>
            <input
              type="number"
              value={formData.error_frequencies}
              onChange={(e) => setFormData({ ...formData, error_frequencies: parseInt(e.target.value) || 0 })}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 focus:outline-none focus:border-teal-500"
              required
            />
          </div>
        </div>

        <div>
          <label className="block text-xs text-slate-400 mb-1">Qualitative Narrative Self-Review</label>
          <textarea
            rows="3"
            value={formData.narrative_text}
            onChange={(e) => setFormData({ ...formData, narrative_text: e.target.value })}
            placeholder="Summarize key accomplishments, KYC adherence, and operational challenges..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 focus:outline-none focus:border-teal-500"
            required
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-teal-500 hover:bg-teal-600 disabled:bg-slate-700 text-slate-950 font-bold py-3 px-4 rounded-lg transition"
        >
          {loading ? 'Processing Model Inference...' : 'Run TrustScore AI Engine'}
        </button>
      </form>
    </div>
  );
}
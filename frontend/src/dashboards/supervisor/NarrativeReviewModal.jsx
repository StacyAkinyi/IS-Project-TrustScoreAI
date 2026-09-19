import React, { useState } from 'react';
import axios from 'axios';

export default function NarrativeReviewModal({ employee, supervisorId, onClose, onSuccess }) {
  const [narrativeText, setNarrativeText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!employee) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const token = localStorage.getItem('access_token');
    const payload = {
      employee_id: employee.employee_id,
      supervisor_id: parseInt(supervisorId),
      narrative_text: narrativeText,
      loan_volumes: 100,
      transaction_accuracy: 98.0,
      workplan_completion: 92.0,
      error_frequencies: 0
    };

    try {
      const res = await axios.post('http://127.0.0.1:8000/api/v1/submit-appraisal', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.status === 200) {
        onSuccess(res.data);
        onClose();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to parse qualitative review.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 w-full max-w-lg shadow-2xl">
        <h3 className="text-lg font-bold text-teal-400 mb-1">
          Narrative Performance Review
        </h3>
        <p className="text-xs text-slate-400 mb-4">Target Employee: {employee.full_name} (#{employee.employee_id})</p>

        {error && <p className="text-rose-400 text-sm mb-3 bg-rose-950/50 p-2 rounded">{error}</p>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Supervisor Observation Narrative</label>
            <textarea
              rows="4"
              value={narrativeText}
              onChange={(e) => setNarrativeText(e.target.value)}
              placeholder="Describe adherence to compliance, leadership traits, and operational accuracy..."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-100 text-sm focus:outline-none focus:border-teal-500"
              required
            />
          </div>

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-lg text-sm font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="bg-teal-500 hover:bg-teal-600 disabled:bg-slate-700 text-slate-950 font-bold px-4 py-2 rounded-lg text-sm"
            >
              {loading ? 'Processing NLP Pipeline...' : 'Submit to Sentiment Engine'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
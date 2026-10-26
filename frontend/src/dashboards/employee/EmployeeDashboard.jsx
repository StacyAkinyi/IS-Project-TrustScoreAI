import React, { useState, useEffect } from 'react';
import PerformanceCharts from './PerformanceCharts';
import AppraisalForm from './AppraisalForm';
import AIPerformanceReportGenerator from '../../components/AIPerformanceReportGenerator';
import SupervisorAppraisalInbox from './SupervisorAppraisalInbox';
import AIQuestionGenerator from './AIQuestionGenerator';



export default function EmployeeDashboard({ userId }) {
  const [employeeData, setEmployeeData] = useState(null);
  const [performanceRecords, setPerformanceRecords] = useState([]);
  const [reviewCount, setReviewCount] = useState(0);
  const [reports, setReports] = useState([]);
  const [trustScoreRuns, setTrustScoreRuns] = useState([]);
  const [activeView, setActiveView] = useState('home'); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const token = localStorage.getItem('access_token');

  useEffect(() => {
    const fetchEmployeeData = async () => {
      try {
        setLoading(true);
        const headers = {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        };

        // Resolve the database employee ID from the validated token, not stale browser state.
        const empRes = await fetch('http://127.0.0.1:8000/api/v1/auth/me', { headers });
        const empJson = await empRes.json();
        if (!empRes.ok) throw new Error(empJson.detail || `Profile request failed (${empRes.status})`);
        setEmployeeData(empJson);
        const employeeId = empJson.employee_id;
        try {
          const reviewRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/supervisor-appraisals`, { headers });
          if (reviewRes.ok) { const reviewData = await reviewRes.json(); setReviewCount(reviewData.length); }
        } catch (reviewError) { console.warn('Could not load appraisal notice count:', reviewError); }

        // 2. Fetch Performance Records
        const perfRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/performance`, { headers });
        if (perfRes.ok) {
          const perfJson = await perfRes.json();
          // Extract array even if backend wraps it in { data: [...] }
          const recordsArray = Array.isArray(perfJson) ? perfJson : perfJson.data || [];
          setPerformanceRecords(recordsArray);
        } else {
          console.warn(`Performance API returned status: ${perfRes.status}`);
        }

        // 3. Fetch Reports
        const repRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/reports`, { headers });
        if (repRes.ok) {
          const repJson = await repRes.json();
          setReports(Array.isArray(repJson) ? repJson : repJson.data || []);
        }

        // The Trust Score pipeline is separate from historical legacy appraisal reports.
        const scoreRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${employeeId}/trust-score-runs`, { headers });
        if (scoreRes.ok) {
          const scoreJson = await scoreRes.json();
          setTrustScoreRuns(Array.isArray(scoreJson) ? scoreJson : []);
        } else {
          console.warn(`Trust Score API returned status: ${scoreRes.status}`);
        }

      } catch (err) {
        console.error("Dashboard fetch error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (userId) fetchEmployeeData();
  }, [userId, token]);

  if (loading) return <div className="p-8 text-center text-slate-600 font-semibold">Loading secure profile...</div>;
  if (error) return <div className="p-8 text-center text-red-600 font-semibold">Error: {error}</div>;

  const latestTrustRun = trustScoreRuns[0] || null;
  const latestScore = latestTrustRun?.score_status === 'ready' && latestTrustRun.trust_score != null
    ? `${Number(latestTrustRun.trust_score).toFixed(1)}%`
    : latestTrustRun?.score_status === 'awaiting_review'
      ? 'Awaiting review'
      : latestTrustRun?.score_status === 'incomplete'
        ? 'Incomplete data'
        : 'Not generated';

  return (
    <div className="space-y-6">
      {/* Back button */}
      {activeView !== 'home' && (
        <button 
          onClick={() => setActiveView('home')}
          className="text-sm font-bold text-blue-700 hover:underline flex items-center gap-1 mb-2"
        >
          &larr; Back to Dashboard Home
        </button>
      )}

      {/* 1. Landing Home View */}
      {activeView === 'home' && (
        <div className="space-y-6">
          <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 text-center space-y-3">
            <h2 className="text-3xl font-extrabold text-blue-900">Welcome, {employeeData?.full_name}</h2>
            <p className="text-slate-600 text-sm">
              Role: <span className="font-semibold text-slate-800">{employeeData?.job_title || employeeData?.role}</span> | Branch: <span className="font-semibold text-slate-800">{employeeData?.branch_location || 'Not assigned'}</span>
            </p>
            <p className="text-slate-600 text-sm">Supervisor: <span className="font-semibold text-slate-800">{employeeData?.supervisor_name || 'Not assigned'}</span></p>
            <div className="inline-block mt-2 bg-blue-50 border border-blue-200 px-6 py-2 rounded-full">
              <span className="text-xs font-bold text-blue-600 uppercase tracking-wider">Latest Trust Score: </span>
              <span className="text-lg font-extrabold text-blue-900">{latestScore}</span>
              {latestTrustRun && <span className="mt-1 block text-xs text-slate-500">{latestTrustRun.period_code} · based on four KPI groups and four reviewed feedback groups</span>}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
            <div 
              onClick={() => setActiveView('kpis')}
              className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2"
            >
              <h3 className="text-lg font-bold text-blue-900">Performance Overview & KPIs</h3>
              <p className="text-slate-500 text-sm">View monthly trends, regression predictions, and appraisal history.</p>
            </div>

            <div 
              onClick={() => setActiveView('appraisals')}
              className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2"
            >
              <h3 className="text-lg font-bold text-blue-900">Appraisal Follow-up</h3>
              <p className="text-slate-500 text-sm">Answer open-ended follow-up questions linked to a completed supervisor appraisal.</p>
            </div>

            <div onClick={() => setActiveView('reviews')} className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2">
              <h3 className="text-lg font-bold text-blue-900">Appraisal Log {reviewCount > 0 ? `(${reviewCount})` : ''}</h3>
              <p className="text-slate-500 text-sm">Review your submitted semiannual supervisor forms, follow-up status, and meeting bookings.</p>
            </div>

            <div 
              onClick={() => setActiveView('chatbot')}
              className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2"
            >
              <h3 className="text-lg font-bold text-blue-900">AI Performance Report</h3>
              <p className="text-slate-500 text-sm">Generate a period report from telemetry and feedback dimensions.</p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Sub-Page: Performance Overview & KPIs */}
      {activeView === 'kpis' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
            <h3 className="text-xl font-bold text-blue-900 mb-4">Performance Overview & KPI Traffic Light</h3>
            <PerformanceCharts performanceRecords={performanceRecords} />
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
            <h3 className="text-lg font-bold text-blue-900 mb-2">Grouped Trust Score history</h3>
            <p className="mb-4 text-xs text-slate-500">A score appears only after the four KPI groups are available and feedback suggestions have been reviewed. Mixed and neutral feedback does not add a numeric score.</p>
            {trustScoreRuns.length === 0 ? (
              <p className="text-slate-500 text-sm">No Trust Score run has been generated for you yet. Your supervisor can run the appraisal classification for your team.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead><tr className="bg-slate-100 text-slate-700"><th className="p-3 border-b">Period</th><th className="p-3 border-b">Trust Score</th><th className="p-3 border-b">KPI groups</th><th className="p-3 border-b">Feedback groups</th><th className="p-3 border-b">Updated</th></tr></thead>
                  <tbody>{trustScoreRuns.map((run) => {
                    const statusLabel = run.score_status === 'ready' ? `${Number(run.trust_score).toFixed(1)}%` : run.score_status === 'awaiting_review' ? 'Awaiting review' : 'Incomplete';
                    const groups = Object.values(run.kpi_groups || {});
                    const feedback = Object.values(run.feedback_groups || {});
                    const groupCell = (values) => values.filter((item) => item.score_0_100 != null).length + ' / ' + values.length + ' scored';
                    return <tr key={run.run_id} className="hover:bg-slate-50"><td className="p-3 border-b font-semibold">{run.period_code}</td><td className="p-3 border-b font-bold text-blue-700">{statusLabel}</td><td className="p-3 border-b">{groupCell(groups)}</td><td className="p-3 border-b">{groupCell(feedback)}</td><td className="p-3 border-b text-slate-500">{new Date(run.generated_at).toLocaleDateString()}</td></tr>;
                  })}</tbody>
                </table>
              </div>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
            <h3 className="text-lg font-bold text-blue-900 mb-4">Historical Appraisal Reports Log</h3>
            {reports.length === 0 ? (
              <p className="text-slate-500 text-sm">No appraisal history recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700">
                      <th className="p-3 border-b">Report ID</th>
                      <th className="p-3 border-b">Unified Trust Score</th>
                      <th className="p-3 border-b">Compliance Status</th>
                      <th className="p-3 border-b">Generation Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((rep) => (
                      <tr key={rep.report_id} className="hover:bg-slate-50">
                        <td className="p-3 border-b">#{rep.report_id}</td>
                        <td className="p-3 border-b font-bold text-blue-700">{rep.unified_trust_score}%</td>
                        <td className="p-3 border-b">
                          {rep.compliance_override_status ? (
                            <span className="bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-semibold">Overridden</span>
                          ) : (
                            <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-semibold">Verified</span>
                          )}
                        </td>
                        <td className="p-3 border-b text-slate-500">{new Date(rep.generation_date).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. Sub-Page: AI Appraisals */}
      {activeView === 'appraisals' && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <h3 className="text-xl font-bold text-blue-900 mb-2">Follow-up Self-Questionnaire</h3>
          <p className="text-slate-600 text-sm mb-6">After a supervisor submits a semiannual form, answer four open-ended questions tied to that specific appraisal.</p>
          {activeView === 'appraisals' && (
            <AppraisalForm 
              employee={employeeData}  
              onBack={() => setActiveView('home')} 
            />
          )}
        </div>
      )}

      {activeView === 'reviews' && (
        <section className="space-y-4"><h3 className="text-xl font-bold text-blue-900">Appraisal Log</h3><p className="text-sm text-slate-600">Each submitted supervisor form appears here with its own review status and linked self-questionnaire status. You can request clarification or mark a form satisfied.</p><SupervisorAppraisalInbox employeeId={employeeData?.employee_id} /></section>
      )}

      {/* 4. Sub-Page: AI Chatbot */}
      {activeView === 'chatbot' && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <h3 className="text-xl font-bold text-blue-900 mb-2">AI Performance Report Generator</h3>
          <p className="text-slate-600 text-sm mb-4">Choose a quarter, half-year, or year to generate a report from your performance data.</p>
          <AIPerformanceReportGenerator />
        </div>
      )}
    </div>
  );
}

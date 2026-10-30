import React, { useState, useEffect } from 'react';
import PerformanceCharts from './PerformanceCharts';
import AppraisalForm from './AppraisalForm';
import AIPerformanceReportGenerator from '../../components/AIPerformanceReportGenerator';
import SupervisorAppraisalInbox from './SupervisorAppraisalInbox';
import AIQuestionGenerator from './AIQuestionGenerator';
import DashboardSidebar from '../../components/DashboardSidebar';
import TableControls from '../../components/TableControls';

const EMPLOYEE_NAV = [
  { id: 'home', label: 'Overview', icon: 'home' },
  { id: 'kpis', label: 'Performance', icon: 'performance' },
  { id: 'appraisals', label: 'Follow-up', icon: 'appraisals' },
  { id: 'reviews', label: 'Appraisal log', icon: 'team' },
  { id: 'chatbot', label: 'Reports', icon: 'reports' },
];



export default function EmployeeDashboard({ userId }) {
  const [employeeData, setEmployeeData] = useState(null);
  const [performanceRecords, setPerformanceRecords] = useState([]);
  const [reviewCount, setReviewCount] = useState(0);
  const [reports, setReports] = useState([]);
  const [trustScoreRuns, setTrustScoreRuns] = useState([]);
  const [trustScoreDetailsOpen, setTrustScoreDetailsOpen] = useState(false);
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
    <div className="ts-dashboard-shell">
      <DashboardSidebar items={EMPLOYEE_NAV} activeId={activeView} onSelect={(item) => setActiveView(item.id)} />
      <div className="ts-dashboard-content space-y-6">
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
            <button
              type="button"
              onClick={() => setTrustScoreDetailsOpen(true)}
              aria-haspopup="dialog"
              className="mt-2 inline-block rounded-full border border-blue-200 bg-blue-50 px-6 py-3 text-left transition hover:border-blue-400 hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <span className="block text-xs font-bold uppercase tracking-wider text-blue-600">Latest Trust Score</span>
              <span className="text-lg font-extrabold text-blue-900">{latestScore}</span>
              {latestTrustRun && <span className="mt-1 block text-xs text-slate-500">{latestTrustRun.period_code} · View how the 8 groups are populated</span>}
              {!latestTrustRun && <span className="mt-1 block text-xs text-slate-500">Click to see how the score is calculated</span>}
            </button>
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
              <TableControls rows={trustScoreRuns} label="Trust Score periods" searchText={(run) => `${run.period_code} ${run.score_status} ${run.generated_at}`}>
                {(pageRows) => <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead><tr className="bg-slate-100 text-slate-700"><th className="p-3 border-b">Period</th><th className="p-3 border-b">Trust Score</th><th className="p-3 border-b">KPI groups</th><th className="p-3 border-b">Feedback groups</th><th className="p-3 border-b">Updated</th></tr></thead>
                  <tbody>{pageRows.map((run) => {
                    const statusLabel = run.score_status === 'ready' ? `${Number(run.trust_score).toFixed(1)}%` : run.score_status === 'awaiting_review' ? 'Awaiting review' : 'Incomplete';
                    const groups = Object.values(run.kpi_groups || {});
                    const feedback = Object.values(run.feedback_groups || {});
                    const groupCell = (values) => values.filter((item) => item.score_0_100 != null).length + ' / ' + values.length + ' scored';
                    return <tr key={run.run_id} className="hover:bg-slate-50"><td className="p-3 border-b font-semibold">{run.period_code}</td><td className="p-3 border-b font-bold text-blue-700">{statusLabel}</td><td className="p-3 border-b">{groupCell(groups)}</td><td className="p-3 border-b">{groupCell(feedback)}</td><td className="p-3 border-b text-slate-500">{new Date(run.generated_at).toLocaleDateString()}</td></tr>;
                  })}</tbody>
                </table>
              </div>}
              </TableControls>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
            <h3 className="text-lg font-bold text-blue-900 mb-4">Historical Appraisal Reports Log</h3>
            {reports.length === 0 ? (
              <p className="text-slate-500 text-sm">No appraisal history recorded yet.</p>
            ) : (
              <TableControls rows={reports} label="historical appraisal reports" searchText={(report) => `${report.report_id} ${report.unified_trust_score} ${report.compliance_override_status ? 'overridden' : 'verified'} ${report.generation_date}`}>
                {(pageRows) => <div className="overflow-x-auto">
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
                    {pageRows.map((rep) => (
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
              </div>}
              </TableControls>
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
      {trustScoreDetailsOpen && <TrustScoreBreakdown run={latestTrustRun} onClose={() => setTrustScoreDetailsOpen(false)} />}
      </div>
    </div>
  );
}


const KPI_GROUPS = [
  ['operational_quality', 'Operational quality'],
  ['delivery_timeliness', 'Delivery and timeliness'],
  ['customer_outcomes', 'Customer outcomes'],
  ['risk_controls', 'Risk and controls'],
];
const FEEDBACK_GROUPS = [
  ['communication', 'Communication'],
  ['collaboration', 'Collaboration'],
  ['compliance_awareness', 'Compliance awareness'],
  ['learning_development', 'Learning and development'],
];
const METRIC_UNITS = {
  transaction_accuracy: '%', workplan_completion: '%', task_deadline_fulfillment_pct: '%',
  complaint_resolution_rate_pct: '%', non_performing_credit_pct: '%', customer_satisfaction: ' / 5',
  error_frequencies: ' / month', loan_processing_turnaround_hours: ' hours',
  cash_reconciliation_errors: ' / month', compliance_incidents: ' / month',
};
const SOURCE_LABELS = {
  supervisor_appraisal: 'Supervisor form',
};

function TrustScoreBreakdown({ run, onClose }) {
  const classifications = run?.classifications || [];
  const scoreLabel = run?.score_status === 'ready' && run.trust_score != null
    ? `${Number(run.trust_score).toFixed(1)}%`
    : run?.score_status === 'awaiting_review' ? 'Awaiting review'
      : run?.score_status === 'incomplete' ? 'Incomplete' : 'Not generated';

  const countsFor = (category, sourceType) => {
    const rows = classifications.filter((item) => item.category === category && (!sourceType || item.source_type === sourceType));
    return {
      positive: rows.filter((item) => item.review_status === 'auto_classified' && item.predicted_direction === 'positive').length,
      negative: rows.filter((item) => item.review_status === 'auto_classified' && item.predicted_direction === 'negative').length,
      mixedNeutral: rows.filter((item) => item.review_status === 'auto_classified' && ['mixed', 'neutral'].includes(item.predicted_direction)).length,
    };
  };
  const sourceScore = (counts) => {
    const scored = counts.positive + counts.negative;
    return scored ? `${((counts.positive / scored) * 100).toFixed(1)}%` : '—';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-xl bg-white p-5 shadow-2xl sm:p-7" role="dialog" aria-modal="true" aria-labelledby="trust-score-breakdown-title">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-blue-700">{run?.period_code || 'Trust Score'}</p>
            <h2 id="trust-score-breakdown-title" className="mt-1 text-2xl font-bold text-blue-950">How your Trust Score is populated</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">The score is the equal-weight average of four KPI group scores and four automatically classified supervisor feedback groups. Each group is scored from 0 to 100.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50" aria-label="Close Trust Score breakdown">Close</button>
        </div>

        <div className="mt-5 rounded-lg bg-blue-50 p-4">
          <span className="text-sm font-semibold text-blue-900">Overall Trust Score: </span>
          <span className="text-lg font-bold text-blue-900">{scoreLabel}</span>
          <p className="mt-1 text-xs text-blue-800">A numeric score is available when all eight groups have enough data to calculate a score.</p>
        </div>

        <h3 className="mb-3 mt-6 text-lg font-bold text-slate-900">KPI groups</h3>
        <div className="grid gap-3 md:grid-cols-2">
          {KPI_GROUPS.map(([key, label]) => {
            const group = run?.kpi_groups?.[key];
            const metrics = group?.metrics || [];
            return (
              <article key={key} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div><h4 className="font-bold text-slate-800">{label}</h4><p className="text-xs text-slate-500">Mean of available metric scores in this group</p></div>
                  <strong className="whitespace-nowrap text-blue-800">{group?.score_0_100 == null ? 'Not scored' : `${Number(group.score_0_100).toFixed(1)}%`}</strong>
                </div>
                {metrics.length ? <ul className="mt-3 divide-y divide-slate-100">{metrics.map((metric) => (
                  <li key={metric.key} className="flex items-start justify-between gap-3 py-2 text-sm">
                    <span className="text-slate-700">{metric.label}<small className="block text-xs text-slate-500">Observed: {metric.mean == null ? 'No data' : `${metric.mean}${METRIC_UNITS[metric.key] || ''}`} · {metric.sample_count} record(s)</small>
                      {metric.zero_tolerance_breach && <small className="block font-semibold text-red-700">Zero-tolerance cash error detected</small>}
                    </span>
                    <span className="whitespace-nowrap font-semibold text-slate-800">{metric.score_0_100 == null ? '—' : `${Number(metric.score_0_100).toFixed(1)}%`}</span>
                  </li>
                ))}</ul> : <p className="mt-3 text-sm text-slate-500">No KPI records for this group.</p>}
              </article>
            );
          })}
        </div>

        <h3 className="mb-3 mt-7 text-lg font-bold text-slate-900">Supervisor feedback groups</h3>
        <p className="mb-3 text-xs text-slate-600">For supervisor answers assigned to each competency, positive predictions count as 100 and negative predictions as 0. Mixed and neutral predictions are displayed but do not enter that competency percentage. Employee self-questionnaires are not classified or scored.</p>
        <div className="grid gap-3 md:grid-cols-2">
          {FEEDBACK_GROUPS.map(([key, label]) => {
            const group = run?.feedback_groups?.[key];
            const combined = countsFor(key);
            return (
              <article key={key} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-3"><div><h4 className="font-bold text-slate-800">{label}</h4><p className="text-xs text-slate-500">Automatic positive/negative predictions only</p></div><strong className="whitespace-nowrap text-blue-800">{group?.score_0_100 == null ? 'Not scored' : `${Number(group.score_0_100).toFixed(1)}%`}</strong></div>
                <div className="mt-3 space-y-2">
                  {Object.entries(SOURCE_LABELS).map(([sourceType, sourceLabel]) => {
                    const counts = countsFor(key, sourceType);
                    const total = counts.positive + counts.negative + counts.mixedNeutral;
                    return <div key={sourceType} className="rounded bg-slate-50 px-3 py-2 text-xs">
                      <div className="flex justify-between gap-2"><strong className="text-slate-700">{sourceLabel}</strong><strong className="text-slate-800">{total ? sourceScore(counts) : 'No answers'}</strong></div>
                      <p className="mt-1 text-slate-600">Positive {counts.positive} · Negative {counts.negative} · Mixed/neutral {counts.mixedNeutral}</p>
                    </div>;
                  })}
                </div>
                <p className="mt-2 text-xs text-slate-600">Group status: {group?.state || 'No data'} · {combined.positive + combined.negative} scored answer(s)</p>
              </article>
            );
          })}
        </div>
        {!run && <p className="mt-5 rounded bg-amber-50 p-3 text-sm text-amber-900">No Trust Score run has been generated yet. Your supervisor can run classification after the appraisal answers are available.</p>}
      </section>
    </div>
  );
}

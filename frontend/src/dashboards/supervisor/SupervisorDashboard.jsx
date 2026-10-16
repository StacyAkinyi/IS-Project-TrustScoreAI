import React, { useState, useEffect } from 'react';
import axios from 'axios';
import StaffDirectory from './StaffDirectory';
import SemiannualAppraisalModal from './SemiannualAppraisalModal';
import SupervisorCoachingChat from './SupervisorCoachingChat';

const metricKeys = ['transaction_accuracy','workplan_completion','task_deadline_fulfillment_pct','complaint_resolution_rate_pct','customer_satisfaction','error_frequencies','loan_processing_turnaround_hours','non_performing_credit_pct','cash_reconciliation_errors','compliance_incidents'];
const metricLabels = ['Accuracy','Workplan','On-time','Complaints','Satisfaction','Errors','Loan time','NPL','Cash errors','Compliance'];
const currentPeriod = () => { const d = new Date(); return `${d.getFullYear()}-H${d.getMonth() < 6 ? 1 : 2}`; };

export default function SupervisorDashboard() {
  const [teamMembers, setTeamMembers] = useState([]);
  const [supervisor, setSupervisor] = useState(null);
  const [teamReports, setTeamReports] = useState([]);
  const [teamOverview, setTeamOverview] = useState([]);
  const [teamAggregate, setTeamAggregate] = useState([]);
  const [appraisals, setAppraisals] = useState([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const supervisorId = localStorage.getItem('user_id');
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    let cancelled = false;
    const fetchDashboard = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [profile, team, reports, overview, appraisalRows] = await Promise.all([
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team-reports`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team-overview`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/appraisals`, { headers }),
        ]);
        if (!cancelled) {
          setSupervisor(profile.data);
          setTeamMembers(team.data);
          setTeamReports(reports.data);
          setTeamOverview(overview.data.employees || []);
          setTeamAggregate(overview.data.aggregate || []);
          setAppraisals(appraisalRows.data || []);
        }
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.detail || 'Could not load your team.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (supervisorId && token) fetchDashboard();
    else { setError('Please sign in again to load your supervisor profile.'); setLoading(false); }
    return () => { cancelled = true; };
  }, [supervisorId, token, refreshKey]);

  if (loading) return <div className="p-8 text-center text-slate-600">Loading Supervisor Portal...</div>;
  const averageScore = teamReports.length
    ? (teamReports.reduce((sum, report) => sum + Number(report.unified_trust_score || 0), 0) / teamReports.length).toFixed(1)
    : '—';
  return <div className="space-y-6">
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-2xl font-bold text-blue-900">Welcome, {supervisor?.full_name || 'Supervisor'}</h2>
      <p className="mt-1 text-sm text-slate-600">{supervisor?.department_code || 'Department not assigned'} · {supervisor?.branch_code || 'Branch not assigned'} · Executive #{supervisor?.executive_id ?? '—'}</p>
    </section>
    {error && <p role="alert" className="rounded bg-rose-100 p-3 text-sm text-rose-800">{error}</p>}
    <section className="grid gap-4 sm:grid-cols-3">
      <SummaryCard label="Direct reports" value={teamMembers.length} />
      <SummaryCard label="Appraisal reports" value={teamReports.length} />
      <SummaryCard label="Average team trust score" value={averageScore === '—' ? averageScore : `${averageScore}%`} />
    </section>
    <StaffDirectory teamMembers={teamMembers} branchCode={supervisor?.branch_code} onSelectEmployee={setSelectedEmployee} />
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="text-lg font-bold text-blue-900">Team telemetry · {currentPeriod()}</h3><p className="mb-4 mt-1 text-xs text-slate-500">Green = safe, orange = warning, red = danger. Thresholds are initial demonstration bands.</p><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-xs"><thead><tr className="border-b text-slate-500"><th className="p-2">Employee</th><th className="p-2">Trust score</th>{metricLabels.map((label) => <th key={label} className="p-2">{label}</th>)}</tr></thead><tbody><tr className="border-b bg-blue-50"><td className="p-2 font-bold text-blue-900">Team average</td><td className="p-2">—</td>{metricKeys.map((key) => { const metric = teamAggregate.find((item) => item.key === key); return <td key={key} className="p-2">{metric?.value == null ? <span className="text-slate-400">No data</span> : <span title={`Mean across ${metric.sample_count} employees`} className={`inline-block rounded px-2 py-1 font-semibold ${metric.state === 'Safe' ? 'bg-green-100 text-green-800' : metric.state === 'Warning' ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'}`}>{metric.state} · {Number(metric.value).toFixed(1)}{metric.unit}</span>}</td>; })}</tr>{teamOverview.map((employee) => <tr key={employee.employee_id} className="border-b last:border-0"><td className="p-2 font-semibold text-slate-800">{employee.full_name}<span className="block text-[10px] font-normal text-slate-500">{employee.role}</span></td><td className="p-2">{employee.trust_score == null ? '—' : `${Number(employee.trust_score).toFixed(1)}%`}</td>{metricKeys.map((key) => { const metric = employee.metrics.find((item) => item.key === key); return <td key={key} className="p-2">{metric ? <span title={`${metric.label}: ${metric.value}${metric.unit}`} className={`inline-block rounded px-2 py-1 font-semibold ${metric.state === 'Safe' ? 'bg-green-100 text-green-800' : metric.state === 'Warning' ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'}`}>{metric.state} · {Number(metric.value).toFixed(1)}{metric.unit}</span> : <span className="text-slate-400">No data</span>}</td>; })}</tr>)}</tbody></table>{teamOverview.length === 0 && <p className="p-4 text-sm text-slate-500">No employees are assigned to this branch yet.</p>}</div></section>
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-3 text-lg font-bold text-blue-900">Semiannual appraisals and clarification requests</h3>{appraisals.length === 0 ? <p className="text-sm text-slate-500">No supervisor forms have been submitted yet.</p> : <div className="space-y-3">{appraisals.map((item) => <div key={item.appraisal_id} className="flex flex-wrap justify-between gap-3 rounded-lg border p-3 text-sm"><div><p className="font-semibold text-slate-800">{item.employee_name} · {item.period_code}</p><p className="text-slate-500">Yes answers: {item.yes_count}/5</p>{item.review_request_text && <p className="mt-2 rounded bg-amber-50 p-2 text-amber-900">Clarification requested: {item.review_request_text}</p>}</div><div className="text-right text-xs text-slate-500">{item.review_requested_at ? 'Needs response' : 'Submitted'}</div></div>)}</div>}</section>
    <SupervisorCoachingChat supervisorId={supervisorId} />
    {selectedEmployee && <SemiannualAppraisalModal employee={selectedEmployee} supervisorId={supervisorId} onClose={() => setSelectedEmployee(null)} onSuccess={() => { setSelectedEmployee(null); setRefreshKey((value) => value + 1); }} />}
  </div>;
}

function SummaryCard({ label, value }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-3xl font-bold text-blue-900">{value}</p></div>;
}

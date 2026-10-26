import React, { useState, useEffect } from 'react';
import axios from 'axios';
import StaffDirectory from './StaffDirectory';
import SemiannualAppraisalModal from './SemiannualAppraisalModal';
import AIPerformanceReportGenerator from '../../components/AIPerformanceReportGenerator';
import ScheduleAppraisalMeetingModal from './ScheduleAppraisalMeetingModal';
import FeedbackReviewQueue from './FeedbackReviewQueue';

const metricKeys = ['transaction_accuracy','workplan_completion','task_deadline_fulfillment_pct','complaint_resolution_rate_pct','customer_satisfaction','error_frequencies','loan_processing_turnaround_hours','non_performing_credit_pct','cash_reconciliation_errors','compliance_incidents'];
const metricLabels = ['Accuracy','Workplan','On-time','Complaints','Satisfaction','Errors','Loan time','NPL','Cash errors','Compliance'];
const currentPeriod = () => { const d = new Date(); return `${d.getFullYear()}-H${d.getMonth() < 6 ? 1 : 2}`; };

async function downloadAppraisal(appraisalId) {
  const response = await fetch(`http://127.0.0.1:8000/api/v1/supervisor-appraisals/${appraisalId}/download`, { headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` } });
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || 'Could not download this appraisal'); }
  const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = `supervisor-appraisal-${appraisalId}.pdf`; anchor.click(); URL.revokeObjectURL(url);
}

export default function SupervisorDashboard() {
  const [teamMembers, setTeamMembers] = useState([]);
  const [supervisor, setSupervisor] = useState(null);
  const [teamReports, setTeamReports] = useState([]);
  const [teamOverview, setTeamOverview] = useState([]);
  const [teamAggregate, setTeamAggregate] = useState([]);
  const [appraisals, setAppraisals] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [scheduleTarget, setScheduleTarget] = useState(null);
  const [downloadBusyId, setDownloadBusyId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [selectedAppraisal, setSelectedAppraisal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const supervisorId = localStorage.getItem('user_id');
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    let cancelled = false;
    const fetchDashboard = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [profile, team, reports, overview, appraisalRows, meetingRows] = await Promise.all([
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team-reports`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team-overview`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/appraisals`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/meetings`, { headers }),
        ]);
        if (!cancelled) {
          setSupervisor(profile.data);
          setTeamMembers(team.data);
          setTeamReports(reports.data);
          setTeamOverview(overview.data.employees || []);
          setTeamAggregate(overview.data.aggregate || []);
          setAppraisals(appraisalRows.data || []);
          setMeetings(meetingRows.data || []);
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

  useEffect(() => {
    if (!supervisorId || !token) return undefined;
    const timer = window.setInterval(() => {
      axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/meetings`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((response) => setMeetings(response.data || [])).catch(() => {});
    }, 20000);
    return () => window.clearInterval(timer);
  }, [supervisorId, token]);

  if (loading) return <div className="p-8 text-center text-slate-600">Loading Supervisor Portal...</div>;
  const readyTrustRuns = teamOverview.filter((employee) => employee.trust_score_status === 'ready' && employee.trust_score != null);
  const averageScore = readyTrustRuns.length
    ? (readyTrustRuns.reduce((sum, employee) => sum + Number(employee.trust_score), 0) / readyTrustRuns.length).toFixed(1)
    : '—';
  const awaitingTrustReview = teamOverview.filter((employee) => employee.trust_score_status === 'awaiting_review').length;
  return <div className="space-y-6">
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-2xl font-bold text-blue-900">Welcome, {supervisor?.full_name || 'Supervisor'}</h2>
      <p className="mt-1 text-sm text-slate-600">{supervisor?.department_code || 'Department not assigned'} · {supervisor?.branch_code || 'Branch not assigned'} · Executive #{supervisor?.executive_id ?? '—'}</p>
    </section>
    {error && <p role="alert" className="rounded bg-rose-100 p-3 text-sm text-rose-800">{error}</p>}
    <section className="grid gap-4 sm:grid-cols-3">
      <SummaryCard label="Direct reports" value={teamMembers.length} />
      <SummaryCard label="Appraisal reports" value={teamReports.length} />
      <SummaryCard label="Average team Trust Score" value={averageScore === '—' ? averageScore : `${averageScore}%`} />
      <SummaryCard label="Runs awaiting feedback review" value={awaitingTrustReview} />
    </section>
    <StaffDirectory teamMembers={teamMembers} branchCode={supervisor?.branch_code} onSelectEmployee={setSelectedEmployee} onScheduleMeeting={(employee) => setScheduleTarget({ employee, appraisal: null })} />
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="text-lg font-bold text-blue-900">Team telemetry · {currentPeriod()}</h3><p className="mb-4 mt-1 text-xs text-slate-500">Green = safe, orange = warning, red = danger. Thresholds are initial demonstration bands.</p><div className="overflow-x-auto"><table className="w-full min-w-[1100px] text-left text-xs"><thead><tr className="border-b text-slate-500"><th className="p-2">Employee</th><th className="p-2">Trust score</th>{metricLabels.map((label) => <th key={label} className="p-2">{label}</th>)}</tr></thead><tbody><tr className="border-b bg-blue-50"><td className="p-2 font-bold text-blue-900">Team average</td><td className="p-2">—</td>{metricKeys.map((key) => { const metric = teamAggregate.find((item) => item.key === key); return <td key={key} className="p-2">{metric?.value == null ? <span className="text-slate-400">No data</span> : <span title={`Mean across ${metric.sample_count} employees`} className={`inline-block rounded px-2 py-1 font-semibold ${metric.state === 'Safe' ? 'bg-green-100 text-green-800' : metric.state === 'Warning' ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'}`}>{metric.state} · {Number(metric.value).toFixed(1)}{metric.unit}</span>}</td>; })}</tr>{teamOverview.map((employee) => <tr key={employee.employee_id} className="border-b last:border-0"><td className="p-2 font-semibold text-slate-800">{employee.full_name}<span className="block text-[10px] font-normal text-slate-500">{employee.role}</span></td><td className="p-2">{employee.trust_score_status === 'ready' && employee.trust_score != null ? <span title={employee.trust_score_period || ''}>{Number(employee.trust_score).toFixed(1)}%</span> : <span className="text-slate-500">{employee.trust_score_status === 'awaiting_review' ? 'Awaiting review' : employee.trust_score_status === 'incomplete' ? 'Incomplete' : 'Not generated'}</span>}</td>{metricKeys.map((key) => { const metric = employee.metrics.find((item) => item.key === key); return <td key={key} className="p-2">{metric ? <span title={`${metric.label}: ${metric.value}${metric.unit}`} className={`inline-block rounded px-2 py-1 font-semibold ${metric.state === 'Safe' ? 'bg-green-100 text-green-800' : metric.state === 'Warning' ? 'bg-orange-100 text-orange-800' : 'bg-red-100 text-red-800'}`}>{metric.state} · {Number(metric.value).toFixed(1)}{metric.unit}</span> : <span className="text-slate-400">No data</span>}</td>; })}</tr>)}</tbody></table>{teamOverview.length === 0 && <p className="p-4 text-sm text-slate-500">No employees are assigned to this branch yet.</p>}</div></section>
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-3 flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-lg font-bold text-blue-900">Appraisal meetings</h3><p className="text-xs text-slate-500">Employee confirmations appear here after they respond to the booking.</p></div><button type="button" onClick={() => setRefreshKey((value) => value + 1)} className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Refresh meetings</button></div>{meetings.length === 0 ? <p className="text-sm text-slate-500">No meetings have been booked yet.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-3">Employee</th><th className="p-3">Meeting</th><th className="p-3">Date and time</th><th className="p-3">Confirmation</th></tr></thead><tbody>{meetings.map((meeting) => <tr key={meeting.meeting_id} className="border-t"><td className="p-3 font-semibold text-slate-800">{meeting.employee_name}</td><td className="p-3">{meeting.period_code ? `Appraisal · ${meeting.period_code}` : 'Check-in'}</td><td className="p-3">{new Date(meeting.scheduled_at).toLocaleString()}</td><td className="p-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${meeting.status === 'confirmed' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>{meeting.status === 'confirmed' ? `Confirmed${meeting.confirmed_at ? ` · ${new Date(meeting.confirmed_at).toLocaleString()}` : ''}` : 'Awaiting employee'}</span></td></tr>)}</tbody></table></div>}</section>
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="mb-3 text-lg font-bold text-blue-900">Semiannual appraisals and review requests</h3>{appraisals.length === 0 ? <p className="text-sm text-slate-500">No supervisor forms have been submitted yet.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="p-3">Employee / period</th><th className="p-3">Responses</th><th className="p-3">Status</th><th className="p-3">Review note</th><th className="p-3">Meeting</th><th className="p-3">Actions</th></tr></thead><tbody>{appraisals.map((item) => <tr key={item.appraisal_id} className="border-t"><td className="p-3 font-semibold text-slate-800">{item.employee_name}<span className="block text-xs font-normal text-slate-500">Form {item.form_number || 1} · {item.period_code}</span></td><td className="p-3">{item.question_count ?? item.answers?.length ?? 0}</td><td className="p-3 text-xs">{item.satisfied_at ? 'Satisfied · closed' : item.review_requested_at && !item.review_edit_count ? 'Review requested' : item.review_edit_count ? 'Revised once' : 'Submitted'}</td><td className="max-w-xs p-3 text-xs text-amber-900">{item.review_request_text || '—'}</td><td className="p-3 text-xs">{item.meeting ? `${new Date(item.meeting.scheduled_at).toLocaleString()} · ${item.meeting.status === 'confirmed' ? 'Confirmed' : 'Awaiting confirmation'}` : 'Not booked'}</td><td className="p-3"><div className="flex flex-wrap gap-2">{item.review_requested_at && !item.review_edit_count && !item.satisfied_at && <button type="button" onClick={() => setSelectedAppraisal(item)} className="rounded bg-blue-700 px-3 py-2 text-xs font-bold text-white">Revise once</button>}{!item.meeting && !item.satisfied_at && <button type="button" onClick={() => setScheduleTarget({ employee: { employee_id: item.employee_id, full_name: item.employee_name }, appraisal: item })} className="rounded border border-blue-700 px-3 py-2 text-xs font-bold text-blue-700">Schedule meeting</button>}<button type="button" onClick={async () => { setDownloadBusyId(item.appraisal_id); setError(''); try { await downloadAppraisal(item.appraisal_id); } catch (err) { setError(err.message); } finally { setDownloadBusyId(null); } }} disabled={downloadBusyId === item.appraisal_id} className="rounded border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-50">Download PDF</button></div></td></tr>)}</tbody></table></div>}</section>
    <FeedbackReviewQueue supervisorId={supervisorId} onChanged={() => setRefreshKey((value) => value + 1)} />
    <AIPerformanceReportGenerator />
    {(selectedEmployee || selectedAppraisal) && <SemiannualAppraisalModal employee={selectedEmployee || { employee_id: selectedAppraisal.employee_id, full_name: selectedAppraisal.employee_name }} appraisal={selectedAppraisal} supervisorId={supervisorId} onClose={() => { setSelectedEmployee(null); setSelectedAppraisal(null); }} onSuccess={() => { setSelectedEmployee(null); setSelectedAppraisal(null); setRefreshKey((value) => value + 1); }} />}
    {scheduleTarget && <ScheduleAppraisalMeetingModal key={scheduleTarget.appraisal?.appraisal_id || scheduleTarget.employee.employee_id} employee={scheduleTarget.employee} appraisal={scheduleTarget.appraisal} existingMeetings={meetings} supervisorId={supervisorId} onClose={() => setScheduleTarget(null)} onSuccess={() => { setScheduleTarget(null); setRefreshKey((value) => value + 1); }} />}
  </div>;
}

function SummaryCard({ label, value }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-3xl font-bold text-blue-900">{value}</p></div>;
}

import React, { useEffect, useState } from 'react';
import AIPerformanceReportGenerator from '../../components/AIPerformanceReportGenerator';
import ExecutiveComplianceOverrideModal from './ExecutiveComplianceOverrideModal';

const API = 'http://127.0.0.1:8000/api/v1';

export default function ExecutiveDashboard({ executiveId }) {
  const [profile, setProfile] = useState(null);
  const [supervisors, setSupervisors] = useState([]);
  const [reports, setReports] = useState([]);
  const [expandedSupervisorId, setExpandedSupervisorId] = useState(null);
  const [formsBySupervisor, setFormsBySupervisor] = useState({});
  const [loadingFormsId, setLoadingFormsId] = useState(null);
  const [formsError, setFormsError] = useState('');
  const [selectedOverrideReport, setSelectedOverrideReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const loadOverview = async () => {
      setLoading(true);
      setError('');
      const token = localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      try {
        const paths = [
          `${API}/executives/${executiveId}`,
          `${API}/executives/${executiveId}/supervisors`,
          `${API}/executives/${executiveId}/reports`,
        ];
        const responses = await Promise.all(paths.map((url) => fetch(url, { headers })));
        const bodies = await Promise.all(responses.map((response) => response.json()));
        const failedIndex = responses.findIndex((response) => !response.ok);
        if (failedIndex !== -1) {
          throw new Error(bodies[failedIndex]?.detail || `Dashboard request failed (${responses[failedIndex].status})`);
        }
        if (!cancelled) {
          setProfile(bodies[0]);
          setSupervisors(Array.isArray(bodies[1]) ? bodies[1] : []);
          setReports(Array.isArray(bodies[2]) ? bodies[2] : []);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load the executive dashboard.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    if (executiveId) loadOverview();
    return () => { cancelled = true; };
  }, [executiveId]);

  const toggleSupervisorForms = async (supervisor) => {
    if (expandedSupervisorId === supervisor.supervisor_id) { setExpandedSupervisorId(null); return; }
    setExpandedSupervisorId(supervisor.supervisor_id); setFormsError('');
    if (formsBySupervisor[supervisor.supervisor_id]) return;
    setLoadingFormsId(supervisor.supervisor_id);
    try {
      const response = await fetch(`${API}/executives/${executiveId}/supervisors/${supervisor.supervisor_id}/appraisals`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load this supervisor’s forms');
      setFormsBySupervisor((current) => ({ ...current, [supervisor.supervisor_id]: data }));
    } catch (err) { setFormsError(err.message); }
    finally { setLoadingFormsId(null); }
  };

  const downloadAppraisal = async (appraisalId) => {
    const response = await fetch(`${API}/supervisor-appraisals/${appraisalId}/download`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
    });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.detail || 'Could not download this appraisal'); }
    const url = URL.createObjectURL(await response.blob()); const anchor = document.createElement('a');
    anchor.href = url; anchor.download = `supervisor-appraisal-${appraisalId}.pdf`; anchor.click(); URL.revokeObjectURL(url);
  };

  if (loading) return <div className="p-8 text-center text-slate-600">Loading executive overview...</div>;

  const averageScore = reports.length
    ? (reports.reduce((sum, report) => sum + Number(report.unified_trust_score || 0), 0) / reports.length).toFixed(1)
    : '—';
  const overrideCount = reports.filter((report) => report.compliance_override_status).length;
  const handleOverrideUpdated = (data) => {
    setReports((current) => current.map((report) => report.report_id === data.report_id ? {
      ...report,
      compliance_override_status: data.override_status,
      compliance_override_reason: data.reason,
      compliance_override_updated_at: data.audit_event.created_at,
      overriding_executive_id: data.override_status ? executiveId : null,
      override_audit: [data.audit_event, ...(report.override_audit || [])],
    } : report));
    setSelectedOverrideReport(null);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-blue-900">Welcome, {profile?.full_name || 'Executive Manager'}</h2>
        <p className="mt-1 text-sm text-slate-600">Oversight region: {profile?.oversight_region || 'Not assigned'}</p>
      </section>
      {error && <p role="alert" className="rounded bg-rose-100 p-3 text-sm text-rose-800">{error}</p>}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryCard label="Supervisors" value={supervisors.length} />
        <SummaryCard label="Employees in reports" value={new Set(reports.map((report) => report.employee_id)).size} />
        <SummaryCard label="Generated appraisal reports" value={reports.length} />
        <SummaryCard label="Supervisor appraisals" value={supervisors.reduce((sum, item) => sum + Number(item.supervisor_appraisal_count || 0), 0)} />
        <SummaryCard label="Average trust score" value={averageScore === '—' ? averageScore : `${averageScore}%`} />
      </section>
      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-1 text-lg font-bold text-blue-900">Supervisors in your region</h3>
          <p className="mb-4 text-xs text-slate-500">KPI averages use each employee’s latest telemetry record and the same safe, warning, and danger bands as the supervisor dashboard.</p>
          {supervisors.length === 0 ? <p className="text-sm text-slate-500">No supervisor profiles are assigned to this region.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-sm">
                <thead><tr className="border-b text-slate-500"><th className="p-2">Supervisor</th><th className="p-2">Department</th><th className="p-2">Branch</th><th className="p-2">Team KPI averages</th><th className="p-2">Supervisor forms</th></tr></thead>
                <tbody>{supervisors.map((item) => <React.Fragment key={item.supervisor_id}>
                  <tr className="border-b last:border-0">
                    <td className="p-2 font-medium text-slate-800">{item.full_name || `Supervisor #${item.supervisor_id}`}</td>
                    <td className="p-2 text-slate-600">{item.department_code || '—'}</td>
                    <td className="p-2 text-slate-600">{item.branch_code || '—'}</td>
                    <td className="p-2">{!item.employees_with_telemetry ? <span className="text-xs text-slate-400">No team telemetry</span> : <details><summary className="cursor-pointer font-semibold text-blue-700">View averages · {item.employees_with_telemetry}/{item.team_size} with telemetry</summary><div className="mt-2 grid min-w-[300px] gap-2 sm:grid-cols-2">{(item.team_kpi_averages || []).map((metric) => <div key={metric.key} className="rounded border border-slate-200 bg-white p-2 text-xs"><span className="font-semibold text-slate-700">{metric.label}: </span>{metric.value == null ? <span className="text-slate-400">No data</span> : <><span>{Number(metric.value).toFixed(1)}{metric.unit}</span><span className={`ml-2 rounded px-1.5 py-0.5 font-semibold ${metric.state === 'Safe' ? 'bg-green-100 text-green-800' : metric.state === 'Warning' ? 'bg-orange-100 text-orange-800' : metric.state === 'Danger' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-600'}`}>{metric.state}</span><span className="ml-1 text-slate-400">n={metric.sample_count}</span></>}</div>)}</div></details>}</td>
                    <td className="p-2"><button type="button" onClick={() => toggleSupervisorForms(item)} className="rounded border border-blue-700 px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-50">{loadingFormsId === item.supervisor_id ? 'Loading…' : `${item.supervisor_appraisal_count || 0} forms · ${expandedSupervisorId === item.supervisor_id ? 'Hide' : 'View'}`}</button></td>
                  </tr>
                  {expandedSupervisorId === item.supervisor_id && <tr className="border-b bg-slate-50"><td colSpan="5" className="p-3">{formsError && <p role="alert" className="mb-2 rounded bg-rose-50 p-2 text-xs text-rose-800">{formsError}</p>}{loadingFormsId === item.supervisor_id ? <p className="text-xs text-slate-500">Loading supervisor forms…</p> : (formsBySupervisor[item.supervisor_id] || []).length === 0 ? <p className="text-xs text-slate-500">No semiannual supervisor appraisal forms for this team yet.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-left text-xs"><thead><tr className="border-b text-slate-500"><th className="p-2">Employee</th><th className="p-2">Period</th><th className="p-2">Responses</th><th className="p-2">Status</th><th className="p-2">Download</th></tr></thead><tbody>{formsBySupervisor[item.supervisor_id].map((form) => <tr key={form.appraisal_id} className="border-b last:border-0"><td className="p-2">{form.employee_name}</td><td className="p-2">Form {form.form_number || 1} · {form.period_code}</td><td className="p-2">{form.question_count ?? form.answers?.length ?? 0}</td><td className="p-2">{form.satisfied_at ? 'Satisfied' : form.review_requested_at && !form.review_edit_count ? 'Review requested' : form.review_edit_count ? 'Revised once' : 'Awaiting employee'}</td><td className="p-2"><button type="button" onClick={async () => { setFormsError(''); try { await downloadAppraisal(form.appraisal_id); } catch (err) { setFormsError(err.message); } }} className="font-semibold text-blue-700 hover:underline">Download PDF</button></td></tr>)}</tbody></table></div>}</td></tr>}
                </React.Fragment>)}</tbody>
              </table>
            </div>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-bold text-blue-900">Recent appraisal reports</h3>
          {reports.length === 0 ? <p className="text-sm text-slate-500">No appraisal reports are available yet.</p> : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white"><tr className="border-b text-slate-500"><th className="p-2">Employee</th><th className="p-2">Trust score</th><th className="p-2">Report status</th><th className="p-2">Compliance override</th></tr></thead>
                <tbody>{[...reports].sort((a, b) => new Date(b.generation_date) - new Date(a.generation_date)).slice(0, 12).map((report) => <tr key={report.report_id} className="border-b last:border-0">
                  <td className="p-2 text-slate-700">#{report.employee_id}</td>
                  <td className="p-2 font-semibold text-slate-800">{Number(report.unified_trust_score).toFixed(1)}%</td>
                  <td className="p-2 text-slate-600">{report.report_status}</td>
                  <td className="p-2"><span className={`mr-2 rounded px-2 py-1 text-xs font-semibold ${report.compliance_override_status ? 'bg-amber-100 text-amber-900' : 'bg-slate-100 text-slate-600'}`}>{report.compliance_override_status ? 'Active' : 'None'}</span><button type="button" onClick={() => setSelectedOverrideReport(report)} className="whitespace-nowrap font-semibold text-blue-700 hover:underline">{report.compliance_override_status ? 'Review / remove' : 'Apply override'}</button></td>
                </tr>)}</tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-slate-500">Compliance overrides applied: {overrideCount}</p>
        </div>
      </section>
      <AIPerformanceReportGenerator />
      {selectedOverrideReport && <ExecutiveComplianceOverrideModal report={selectedOverrideReport} executiveId={executiveId} onClose={() => setSelectedOverrideReport(null)} onUpdated={handleOverrideUpdated} />}
    </div>
  );
}

function SummaryCard({ label, value }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-3xl font-bold text-blue-900">{value}</p></div>;
}

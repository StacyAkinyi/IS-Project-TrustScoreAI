import React, { useEffect, useState } from 'react';
import ExecutiveCoachingChat from './ExecutiveCoachingChat';

const API = 'http://127.0.0.1:8000/api/v1';

export default function ExecutiveDashboard({ executiveId }) {
  const [profile, setProfile] = useState(null);
  const [supervisors, setSupervisors] = useState([]);
  const [reports, setReports] = useState([]);
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

  if (loading) return <div className="p-8 text-center text-slate-600">Loading executive overview...</div>;

  const averageScore = reports.length
    ? (reports.reduce((sum, report) => sum + Number(report.unified_trust_score || 0), 0) / reports.length).toFixed(1)
    : '—';
  const overrideCount = reports.filter((report) => report.compliance_override_status).length;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-2xl font-bold text-blue-900">Welcome, {profile?.full_name || 'Executive Manager'}</h2>
        <p className="mt-1 text-sm text-slate-600">Oversight region: {profile?.oversight_region || 'Not assigned'}</p>
      </section>
      {error && <p role="alert" className="rounded bg-rose-100 p-3 text-sm text-rose-800">{error}</p>}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard label="Supervisors" value={supervisors.length} />
        <SummaryCard label="Employees in reports" value={new Set(reports.map((report) => report.employee_id)).size} />
        <SummaryCard label="Appraisal reports" value={reports.length} />
        <SummaryCard label="Average trust score" value={averageScore === '—' ? averageScore : `${averageScore}%`} />
      </section>
      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-bold text-blue-900">Supervisors in your region</h3>
          {supervisors.length === 0 ? <p className="text-sm text-slate-500">No supervisor profiles are assigned to this region.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead><tr className="border-b text-slate-500"><th className="p-2">Supervisor</th><th className="p-2">Department</th><th className="p-2">Branch</th></tr></thead>
                <tbody>{supervisors.map((item) => <tr key={item.supervisor_id} className="border-b last:border-0">
                  <td className="p-2 font-medium text-slate-800">{item.full_name || `Supervisor #${item.supervisor_id}`}</td>
                  <td className="p-2 text-slate-600">{item.department_code || '—'}</td>
                  <td className="p-2 text-slate-600">{item.branch_code || '—'}</td>
                </tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-bold text-blue-900">Recent appraisal reports</h3>
          {reports.length === 0 ? <p className="text-sm text-slate-500">No appraisal reports are available yet.</p> : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-white"><tr className="border-b text-slate-500"><th className="p-2">Employee</th><th className="p-2">Trust score</th><th className="p-2">Status</th></tr></thead>
                <tbody>{[...reports].sort((a, b) => new Date(b.generation_date) - new Date(a.generation_date)).slice(0, 12).map((report) => <tr key={report.report_id} className="border-b last:border-0">
                  <td className="p-2 text-slate-700">#{report.employee_id}</td>
                  <td className="p-2 font-semibold text-slate-800">{Number(report.unified_trust_score).toFixed(1)}%</td>
                  <td className="p-2 text-slate-600">{report.compliance_override_status ? 'Override applied' : report.report_status}</td>
                </tr>)}</tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-slate-500">Compliance overrides applied: {overrideCount}</p>
        </div>
      </section>
      <ExecutiveCoachingChat executiveId={executiveId} />
    </div>
  );
}

function SummaryCard({ label, value }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-3xl font-bold text-blue-900">{value}</p></div>;
}

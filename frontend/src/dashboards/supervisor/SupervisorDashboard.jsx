import React, { useState, useEffect } from 'react';
import axios from 'axios';
import StaffDirectory from './StaffDirectory';
import NarrativeReviewModal from './NarrativeReviewModal';

export default function SupervisorDashboard() {
  const [teamMembers, setTeamMembers] = useState([]);
  const [supervisor, setSupervisor] = useState(null);
  const [teamReports, setTeamReports] = useState([]);
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
        const [profile, team, reports] = await Promise.all([
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team`, { headers }),
          axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team-reports`, { headers }),
        ]);
        if (!cancelled) {
          setSupervisor(profile.data);
          setTeamMembers(team.data);
          setTeamReports(reports.data);
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
  }, [supervisorId, token]);

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
    {selectedEmployee && <NarrativeReviewModal employee={selectedEmployee} supervisorId={supervisorId} onClose={() => setSelectedEmployee(null)} onSuccess={() => setSelectedEmployee(null)} />}
  </div>;
}

function SummaryCard({ label, value }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-3xl font-bold text-blue-900">{value}</p></div>;
}

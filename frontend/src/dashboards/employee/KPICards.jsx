import React from 'react';

export default function KpiCards({ employeeData, latestReport }) {
  const trustScore = latestReport?.unified_trust_score ?? 'N/A';
  const scoreColor = trustScore >= 75 ? 'text-emerald-400' : trustScore >= 60 ? 'text-amber-400' : 'text-rose-400';

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      {/* Unified TrustScore Card */}
      <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-md">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Unified TrustScore</p>
        <div className={`text-3xl font-extrabold mt-2 ${scoreColor}`}>
          {trustScore} <span className="text-sm text-slate-400">/ 100</span>
        </div>
        <p className="text-xs text-slate-400 mt-1">Random Forest + Sentiment Model</p>
      </div>

      {/* Profile Summary */}
      <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-md">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Branch Location</p>
        <p className="text-xl font-bold text-slate-100 mt-2">{employeeData?.branch_location || 'Main Branch'}</p>
        <p className="text-xs text-teal-400 mt-1">Role: {employeeData?.role || 'Employee'}</p>
      </div>

      {/* Supervisor Tracking */}
      <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-md">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Assigned Supervisor ID</p>
        <p className="text-xl font-bold text-slate-100 mt-2">#{employeeData?.supervisor_id || '1'}</p>
        <p className="text-xs text-slate-400 mt-1">Direct Reporting</p>
      </div>

      {/* Compliance Status */}
      <div className="bg-slate-800 p-5 rounded-xl border border-slate-700 shadow-md">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Compliance Status</p>
        <p className="text-xl font-bold text-emerald-400 mt-2">
          {latestReport?.compliance_override_status ? 'Executive Override' : 'Standard Compliance'}
        </p>
        <p className="text-xs text-slate-400 mt-1">Audit Logged</p>
      </div>
    </div>
  );
}
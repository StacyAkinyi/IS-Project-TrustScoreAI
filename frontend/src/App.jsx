import React from 'react';
import EmployeeDashboard from './dashboards/employee/EmployeeDashboard';

export default function App() {
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6">
      <header className="mb-6 flex justify-between items-center border-b border-slate-700 pb-4">
        <h1 className="text-2xl font-bold text-teal-400">TrustScoreAI Portal</h1>
        <span className="bg-slate-800 border border-slate-700 px-3 py-1 rounded text-xs uppercase tracking-wider text-teal-300 font-semibold">
          Employee Portal
        </span>
      </header>

      <main>
        <EmployeeDashboard />
      </main>
    </div>
  );
}
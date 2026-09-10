import React, { useState, useEffect } from 'react';
import EmployeeDashboard from './dashboards/employee/EmployeeDashboard';
import SupervisorDashboard from './dashboards/supervisor/SupervisorDashboard';

export default function App() {
  const [userRole, setUserRole] = useState(localStorage.getItem('user_role') || 'supervisor');

  const handleRoleChange = (role) => {
    setUserRole(role);
    localStorage.setItem('user_role', role);
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6">
      <header className="mb-6 flex justify-between items-center border-b border-slate-700 pb-4">
        <h1 className="text-2xl font-bold text-teal-400">TrustScoreAI Portal</h1>
        
        {/* Active Role Switcher */}
        <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700">
          <button
            onClick={() => handleRoleChange('employee')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
              userRole === 'employee' ? 'bg-teal-500 text-slate-950' : 'text-slate-400 hover:text-white'
            }`}
          >
            Employee View
          </button>
          <button
            onClick={() => handleRoleChange('supervisor')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
              userRole === 'supervisor' ? 'bg-teal-500 text-slate-950' : 'text-slate-400 hover:text-white'
            }`}
          >
            Supervisor View
          </button>
        </div>
      </header>

      <main>
        {userRole === 'employee' && <EmployeeDashboard />}
        {userRole === 'supervisor' && <SupervisorDashboard />}
      </main>
    </div>
  );
}
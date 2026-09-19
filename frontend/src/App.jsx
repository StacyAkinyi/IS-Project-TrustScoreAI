import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import EmployeeDashboard from './dashboards/employee/EmployeeDashboard'; 
import SupervisorDashboard from './dashboards/supervisor/SupervisorDashboard';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const role = localStorage.getItem('user_role');
    const id = localStorage.getItem('user_id');
    
    if (token && role) {
      setIsAuthenticated(true);
      setUserRole(role);
      setUserId(id);
    }
  }, []);

  const handleLogin = (role) => {
    setIsAuthenticated(true);
    setUserRole(localStorage.getItem('user_role'));
    setUserId(localStorage.getItem('user_id'));
  };

  const handleLogout = () => {
    localStorage.clear();
    setIsAuthenticated(false);
    setUserRole(null);
    setUserId(null);
  };

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      <header className="bg-white shadow px-6 py-4 flex justify-between items-center">
        <h1 className="text-xl font-extrabold text-blue-900">
          TrustScoreAI Portal <span className="text-sm font-normal text-slate-500 uppercase">({userRole} View - ID: #{userId})</span>
        </h1>
        <button 
          onClick={handleLogout}
          className="bg-red-600 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-red-700 transition"
        >
          Sign Out
        </button>
      </header>

      <main className="flex-1 p-6 max-w-7xl w-full mx-auto">
        {/* Render the real Employee Dashboard component here */}
        {userRole === 'employee' && <EmployeeDashboard userId={userId} />}
        {userRole === 'supervisor' && <SupervisorDashboard supervisorId={userId} />}
        {userRole === 'executive' && (
          <div className="bg-white p-6 rounded shadow border border-slate-200">
            <h2 className="text-lg font-bold text-blue-900">Executive Macro-Analytics Portal</h2>
            <p className="text-slate-600 mt-2">Executive dashboard view is active for ID: {userId}.</p>
          </div>
        )}
      </main>
    </div>
  );
}
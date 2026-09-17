import React, { useState, useEffect } from 'react';
import Login from './components/Login';
import EmployeeDashboard from './dashboards/employee/EmployeeDashboard';
import SupervisorDashboard from './dashboards/supervisor/SupervisorDashboard';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);

  // Check if session already exists on page load
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const role = localStorage.getItem('user_role');
    if (token && role) {
      setIsAuthenticated(true);
      setUserRole(role);
    }
  }, []);

  // This is the function Login.jsx is trying to call!
  const handleLogin = (role) => {
    setIsAuthenticated(true);
    setUserRole(role);
  };

  const handleLogout = () => {
    localStorage.clear();
    setIsAuthenticated(false);
    setUserRole(null);
  };

  // If not logged in, render the Login screen and pass handleLogin as `onLogin`
  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  // Once authenticated, render the correct role-based dashboard view
  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="max-w-6xl mx-auto flex justify-between items-center mb-6 bg-white p-4 rounded shadow">
        <h1 className="text-xl font-bold text-blue-900">TrustScoreAI Portal ({userRole?.toUpperCase()} VIEW)</h1>
        <button 
          onClick={handleLogout}
          className="bg-red-600 text-white px-4 py-2 rounded text-sm font-semibold hover:bg-red-700 transition"
        >
          Sign Out
        </button>
      </div>

      <div className="max-w-6xl mx-auto bg-white p-6 rounded shadow">
        {userRole === 'employee' && <p>Welcome to your Employee Performance & AI Coaching Dashboard.</p>}
        {userRole === 'supervisor' && <p>Welcome to your Supervisor Team Directory & Review Portal.</p>}
        {userRole === 'executive' && <p>Welcome to your Executive Macro-Analytics & Compliance Portal.</p>}
      </div>
    </div>
  );
}

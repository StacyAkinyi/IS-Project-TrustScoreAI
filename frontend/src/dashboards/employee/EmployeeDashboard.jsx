import React, { useState, useEffect } from 'react';
import PerformanceCharts from './PerformanceCharts';
import AppraisalForm from './AppraisalForm';
import CoachingChatbot from './CoachingChatbot';
import AIQuestionGenerator from './AIQuestionGenerator';



export default function EmployeeDashboard({ userId }) {
  const [employeeData, setEmployeeData] = useState(null);
  const [performanceRecords, setPerformanceRecords] = useState([]);
  const [reports, setReports] = useState([]);
  const [activeView, setActiveView] = useState('home'); 
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const token = localStorage.getItem('access_token');

  useEffect(() => {
    const fetchEmployeeData = async () => {
      try {
        setLoading(true);
        const headers = {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        };

        // 1. Fetch Profile Data
        const empRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${userId}`, { headers });
        if (!empRes.ok) throw new Error('Failed to fetch employee profile');
        const empJson = await empRes.json();
        setEmployeeData(empJson);

        // 2. Fetch Performance Records
        const perfRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${userId}/performance`, { headers });
        if (perfRes.ok) {
          const perfJson = await perfRes.json();
          // Extract array even if backend wraps it in { data: [...] }
          const recordsArray = Array.isArray(perfJson) ? perfJson : perfJson.data || [];
          setPerformanceRecords(recordsArray);
        } else {
          console.warn(`Performance API returned status: ${perfRes.status}`);
        }

        // 3. Fetch Reports
        const repRes = await fetch(`http://127.0.0.1:8000/api/v1/employees/${userId}/reports`, { headers });
        if (repRes.ok) {
          const repJson = await repRes.json();
          setReports(Array.isArray(repJson) ? repJson : repJson.data || []);
        }

      } catch (err) {
        console.error("Dashboard fetch error:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (userId) fetchEmployeeData();
  }, [userId, token]);

  if (loading) return <div className="p-8 text-center text-slate-600 font-semibold">Loading secure profile...</div>;
  if (error) return <div className="p-8 text-center text-red-600 font-semibold">Error: {error}</div>;

  const latestReport = reports.length > 0 ? reports[reports.length - 1] : null;
  const latestScore = latestReport ? latestReport.unified_trust_score : 'N/A';

  return (
    <div className="space-y-6">
      {/* Back button */}
      {activeView !== 'home' && (
        <button 
          onClick={() => setActiveView('home')}
          className="text-sm font-bold text-blue-700 hover:underline flex items-center gap-1 mb-2"
        >
          &larr; Back to Dashboard Home
        </button>
      )}

      {/* 1. Landing Home View */}
      {activeView === 'home' && (
        <div className="space-y-6">
          <div className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 text-center space-y-3">
            <h2 className="text-3xl font-extrabold text-blue-900">Welcome, {employeeData?.full_name}</h2>
            <p className="text-slate-600 text-sm">
              Role: <span className="font-semibold text-slate-800">{employeeData?.role}</span> | Branch: <span className="font-semibold text-slate-800">{employeeData?.branch_location}</span>
            </p>
            <div className="inline-block mt-2 bg-blue-50 border border-blue-200 px-6 py-2 rounded-full">
              <span className="text-xs font-bold text-blue-600 uppercase tracking-wider">Latest Trust Score: </span>
              <span className="text-lg font-extrabold text-blue-900">{latestScore} {latestScore !== 'N/A' && '%'}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div 
              onClick={() => setActiveView('kpis')}
              className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2"
            >
              <h3 className="text-lg font-bold text-blue-900">Performance Overview & KPIs</h3>
              <p className="text-slate-500 text-sm">View monthly trends, regression predictions, and appraisal history.</p>
            </div>

            <div 
              onClick={() => setActiveView('appraisals')}
              className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2"
            >
              <h3 className="text-lg font-bold text-blue-900">AI-Driven Appraisals</h3>
              <p className="text-slate-500 text-sm">Submit self-appraisals and reflections for automated machine learning evaluation.</p>
            </div>

            <div 
              onClick={() => setActiveView('chatbot')}
              className="bg-white p-8 rounded-lg shadow-sm border border-slate-200 hover:border-blue-500 cursor-pointer transition text-center space-y-2"
            >
              <h3 className="text-lg font-bold text-blue-900">AI Coaching Chatbot</h3>
              <p className="text-slate-500 text-sm">Chat 24/7 with the assistant for personalized behavioral guidance.</p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Sub-Page: Performance Overview & KPIs */}
      {activeView === 'kpis' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
            <h3 className="text-xl font-bold text-blue-900 mb-4">Monthly Performance & Regression Forecasts</h3>
            <PerformanceCharts performanceRecords={performanceRecords} />
          </div>

          <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
            <h3 className="text-lg font-bold text-blue-900 mb-4">Historical Appraisal Reports Log</h3>
            </>{reports.length === 0 ? (
              <p className="text-slate-500 text-sm">No appraisal history recorded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-slate-100 text-slate-700">
                      <th className="p-3 border-b">Report ID</th>
                      <th className="p-3 border-b">Unified Trust Score</th>
                      <th className="p-3 border-b">Compliance Status</th>
                      <th className="p-3 border-b">Generation Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((rep) => (
                      <tr key={rep.report_id} className="hover:bg-slate-50">
                        <td className="p-3 border-b">#{rep.report_id}</td>
                        <td className="p-3 border-b font-bold text-blue-700">{rep.unified_trust_score}%</td>
                        <td className="p-3 border-b">
                          {rep.compliance_override_status ? (
                            <span className="bg-amber-100 text-amber-800 px-2 py-1 rounded text-xs font-semibold">Overridden</span>
                          ) : (
                            <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-semibold">Verified</span>
                          )}
                        </td>
                        <td className="p-3 border-b text-slate-500">{new Date(rep.generation_date).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 3. Sub-Page: AI Appraisals */}
      {activeView === 'appraisals' && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <h3 className="text-xl font-bold text-blue-900 mb-2">Submit & Complete Self-Appraisals</h3>
          <p className="text-slate-600 text-sm mb-6">Input your operational metrics and reflection text below to trigger the backend machine learning and NLP scoring pipeline.</p>
          {activeView === 'appraisals' && (
            <AppraisalForm 
              employee={employeeData}  
              onBack={() => setActiveView('home')} 
            />
          )}
        </div>
      )}

      {/* 4. Sub-Page: AI Chatbot */}
      {activeView === 'chatbot' && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-slate-200">
          <h3 className="text-xl font-bold text-blue-900 mb-2">24/7 AI Coaching Assistant</h3>
          <p className="text-slate-600 text-sm mb-4">Query your metrics or ask for behavioral guidance based on your recent score fluctuations.</p>
          <CoachingChatbot userId={userId} />
        </div>
      )}
    </div>
  );
}
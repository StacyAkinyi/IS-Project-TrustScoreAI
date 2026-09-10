import React, { useState, useEffect } from 'react';
import axios from 'axios';
import KpiCards from './KpiCards';
import AppraisalForm from './AppraisalForm';
import CoachingChatbot from './CoachingChatbot';

// Ensure 'export default' is present here
export default function EmployeeDashboard() {
  const [employeeData, setEmployeeData] = useState(null);
  const [latestReport, setLatestReport] = useState(null);
  const [loading, setLoading] = useState(true);

  const userId = localStorage.getItem('user_id') || 1;
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    const fetchEmployeeProfile = async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/api/v1/employees/${userId}`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setEmployeeData(res.data);
      } catch (err) {
        console.error('Failed to load profile', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEmployeeProfile();
  }, [userId, token]);

  const handleAppraisalSuccess = (responseData) => {
    setLatestReport({
      unified_trust_score: responseData.unified_trust_score,
      compliance_override_status: false
    });
  };

  if (loading) return <div className="text-teal-400 p-8">Loading Employee Portal...</div>;

  return (
    <div className="space-y-6">
      <KpiCards employeeData={employeeData} latestReport={latestReport} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <AppraisalForm
          employeeId={employeeData?.employee_id || 1}
          supervisorId={employeeData?.supervisor_id || 1}
          onSubmissionSuccess={handleAppraisalSuccess}
        />
        <CoachingChatbot latestScore={latestReport?.unified_trust_score} />
      </div>
    </div>
  );
}
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import StaffDirectory from './StaffDirectory';
import NarrativeReviewModal from './NarrativeReviewModal';

export default function SupervisorDashboard() {
  const [teamMembers, setTeamMembers] = useState([]);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [loading, setLoading] = useState(true);

  const supervisorId = localStorage.getItem('user_id') || 1;
  const token = localStorage.getItem('access_token');

  useEffect(() => {
    const fetchTeam = async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8000/api/v1/supervisors/${supervisorId}/team`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setTeamMembers(res.data);
      } catch (err) {
        // Fallback mock team data for testing
        setTeamMembers([
          { employee_id: 1, full_name: 'John Doe', role: 'Loan Officer', branch_code: 'BR-001' },
          { employee_id: 2, full_name: 'Jane Smith', role: 'Compliance Analyst', branch_code: 'BR-001' }
        ]);
      } finally {
        setLoading(false);
      }
    };

    fetchTeam();
  }, [supervisorId, token]);

  if (loading) return <div className="text-teal-400 p-8">Loading Supervisor Portal...</div>;

  return (
    <div className="space-y-6">
      <StaffDirectory
        teamMembers={teamMembers}
        onSelectEmployee={(employee) => setSelectedEmployee(employee)}
      />

      {selectedEmployee && (
        <NarrativeReviewModal
          employee={selectedEmployee}
          supervisorId={supervisorId}
          onClose={() => setSelectedEmployee(null)}
          onSuccess={() => setSelectedEmployee(null)}
        />
      )}
    </div>
  );
}
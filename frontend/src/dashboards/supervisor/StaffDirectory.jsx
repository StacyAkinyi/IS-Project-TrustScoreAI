import React from 'react';

export default function StaffDirectory({ teamMembers, onSelectEmployee }) {
  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-md">
      <h3 className="text-lg font-bold text-teal-400 mb-4">Branch Staff Directory</h3>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-900 text-xs uppercase text-slate-400 border-b border-slate-700">
            <tr>
              <th className="p-3">Employee ID</th>
              <th className="p-3">Full Name</th>
              <th className="p-3">Role</th>
              <th className="p-3">Branch Code</th>
              <th className="p-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {teamMembers.map((member) => (
              <tr key={member.employee_id} className="hover:bg-slate-700/50 transition">
                <td className="p-3 font-mono text-teal-300">#{member.employee_id}</td>
                <td className="p-3 font-semibold text-slate-100">{member.full_name}</td>
                <td className="p-3">{member.role}</td>
                <td className="p-3 font-mono">{member.branch_code || 'BR-001'}</td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => onSelectEmployee(member)}
                    className="bg-teal-500 hover:bg-teal-600 text-slate-950 font-bold px-3 py-1.5 rounded text-xs transition"
                  >
                    Input Narrative Review
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
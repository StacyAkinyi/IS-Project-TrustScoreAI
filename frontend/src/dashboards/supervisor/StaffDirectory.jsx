import React from 'react';
import TableControls from '../../components/TableControls';

export default function StaffDirectory({ teamMembers, onSelectEmployee, onScheduleMeeting, branchCode }) {
  return (
    <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-md">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-bold text-teal-400">Branch Staff Directory</h3>
          <p className="text-xs text-slate-400">Direct reports and qualitative assessment triggers</p>
        </div>
        <span className="bg-slate-900 border border-slate-700 px-3 py-1 rounded text-xs text-teal-300 font-mono">
          Branch: {branchCode || 'Not assigned'}
        </span>
      </div>

      <TableControls rows={teamMembers} label="staff" searchText={(member) => `${member.employee_id} ${member.full_name} ${member.role} ${member.branch_location}`}>
      {(pageRows) => <div className="overflow-x-auto">
        <table className="w-full text-left text-sm text-slate-300">
          <thead className="bg-slate-900 text-xs uppercase text-slate-400 border-b border-slate-700">
            <tr>
              <th className="p-3">Employee ID</th>
              <th className="p-3">Full Name</th>
              <th className="p-3">Role</th>
              <th className="p-3">Branch Location</th>
              <th className="p-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {pageRows.map((member) => (
              <tr key={member.employee_id} className="hover:bg-slate-700/50 transition">
                <td className="p-3 font-mono text-teal-300">#{member.employee_id}</td>
                <td className="p-3 font-semibold text-slate-100">{member.full_name}</td>
                <td className="p-3">{member.role}</td>
                <td className="p-3">{member.branch_location || 'Main Branch'}</td>
                <td className="p-3 text-right space-x-2">
                  <button
                    type="button"
                    onClick={() => onScheduleMeeting?.(member)}
                    className="bg-slate-700 hover:bg-slate-600 text-slate-200 font-semibold px-3 py-1.5 rounded text-xs transition"
                  >
                    Schedule Meeting
                  </button>
                  <button
                    onClick={() => onSelectEmployee(member)}
                    className="bg-teal-500 hover:bg-teal-600 text-slate-950 font-bold px-3 py-1.5 rounded text-xs transition"
                  >
                    Start Semiannual Appraisal
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
      </TableControls>
    </div>
  );
}

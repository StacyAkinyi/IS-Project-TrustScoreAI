import { useCallback, useEffect, useMemo, useState } from 'react';
import './AdminDashboard.css';
import DashboardSidebar from '../../components/DashboardSidebar';
import TableControls from '../../components/TableControls';

const ADMIN_NAV = [
  { id: 'overview', label: 'Overview', icon: 'home' },
  { id: 'people', label: 'People', icon: 'team' },
  { id: 'telemetry', label: 'Telemetry', icon: 'performance' },
  { id: 'regions', label: 'Regions', icon: 'regions' },
  { id: 'directory', label: 'Accounts', icon: 'accounts' },
  { id: 'organization-insights', label: 'Org insights', icon: 'trust' },
];

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

const KPI_CARDS = [
  { key: 'loan_volumes', label: 'Loan volumes', unit: ' / period' },
  { key: 'transaction_accuracy', label: 'Transaction accuracy', unit: '%' },
  { key: 'workplan_completion', label: 'Workplan completion', unit: '%' },
  { key: 'tasks_on_time', label: 'Tasks on time', unit: '%' },
  { key: 'accounts_opened', label: 'Accounts opened', unit: ' / period' },
  { key: 'complaint_resolution', label: 'Complaint resolution', unit: '%' },
  { key: 'customer_satisfaction', label: 'Customer satisfaction', unit: ' / 5' },
  { key: 'processing_errors', label: 'Processing errors', unit: ' / record' },
  { key: 'loan_processing_hours', label: 'Loan processing time', unit: ' hrs' },
  { key: 'non_performing_credit', label: 'Non-performing credit', unit: '%' },
  { key: 'cash_reconciliation_errors', label: 'Cash reconciliation errors', unit: ' / record' },
  { key: 'compliance_incidents', label: 'Compliance incidents', unit: ' / record' },
  { key: 'digital_channel_adoption', label: 'Digital channel adoption', unit: '%' },
];

const EMPTY_FORM = {
  full_name: '',
  email: '',
  password: '',
  department: '',
  role: '',
  user_type: 'employee',
  start_date: '',
  supervisor_id: '',
  executive_id: '',
  branch_code: '',
  oversight_region: '',
  is_active: true,
};

async function apiRequest(path, options = {}) {
  const token = localStorage.getItem('access_token');
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = result.detail;
    throw new Error(typeof detail === 'string' ? detail : 'The request could not be completed.');
  }
  return result;
}

function formatValue(value, unit) {
  if (value === null || value === undefined) return '—';
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}`;
}

function roleLabel(userType) {
  return userType ? userType.replaceAll('_', ' ') : 'Unassigned';
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [regions, setRegions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeNav, setActiveNav] = useState('overview');
  const [error, setError] = useState('');
  const [regionError, setRegionError] = useState('');
  const [notice, setNotice] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');
    try {
      const [summaryResult, directoryResult, regionResult] = await Promise.allSettled([
        apiRequest('/api/v1/admin/overview'),
        apiRequest('/api/v1/admin/employees'),
        apiRequest('/api/v1/admin/regions'),
      ]);
      const errors = [];
      if (summaryResult.status === 'fulfilled') setOverview(summaryResult.value);
      else errors.push(`Organization summary: ${summaryResult.reason?.message || 'Could not load.'}`);
      if (directoryResult.status === 'fulfilled') setEmployees(directoryResult.value);
      else errors.push(`Account list: ${directoryResult.reason?.message || 'Could not load.'}`);
      if (regionResult.status === 'fulfilled') {
        setRegions(regionResult.value);
        setRegionError('');
      } else {
        setRegions([]);
        setRegionError(regionResult.reason?.message || 'Could not load oversight regions.');
      }
      setError(errors.join(' '));
    } catch (requestError) {
      setError(requestError.message || 'Could not load organization data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const visibleEmployees = useMemo(() => {
    return employees
      .filter((employee) => employee.user_type !== 'admin')
      .filter((employee) => roleFilter === 'all' || employee.user_type === roleFilter);
  }, [employees, roleFilter]);

  const supervisors = employees.filter((employee) => employee.user_type === 'supervisor' && employee.is_active);
  const executives = employees.filter((employee) => employee.user_type === 'executive' && employee.is_active);

  const openCreate = () => {
    setEditingEmployee(null);
    setForm({ ...EMPTY_FORM });
    setError('');
    setNotice('');
    setModalOpen(true);
  };

  const openEdit = (employee) => {
    setEditingEmployee(employee);
    setForm({
      ...EMPTY_FORM,
      full_name: employee.full_name || '',
      email: employee.email || '',
      department: employee.department || '',
      role: employee.role || '',
      user_type: employee.user_type,
      start_date: employee.start_date || '',
      supervisor_id: employee.supervisor_id ? String(employee.supervisor_id) : '',
      executive_id: employee.executive_id ? String(employee.executive_id) : '',
      branch_code: employee.branch_code || '',
      oversight_region: employee.oversight_region || '',
      is_active: employee.is_active,
    });
    setError('');
    setNotice('');
    setModalOpen(true);
  };

  const updateField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const handleTypeChange = (value) => setForm((current) => ({
    ...current,
    user_type: value,
    supervisor_id: '',
    executive_id: '',
    branch_code: '',
    oversight_region: '',
  }));

  const handleSave = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setNotice('');

    const payload = {
      full_name: form.full_name.trim(),
      email: form.email.trim().toLowerCase(),
      department: form.department.trim(),
      role: form.role.trim(),
    };
    if (editingEmployee) {
      payload.is_active = form.is_active;
      if (form.password) payload.password = form.password;
      if (form.user_type === 'employee') {
        payload.supervisor_id = form.supervisor_id ? Number(form.supervisor_id) : null;
        if (form.start_date) payload.start_date = form.start_date;
      } else if (form.user_type === 'supervisor') {
        payload.executive_id = Number(form.executive_id);
        payload.branch_code = form.branch_code.trim();
      } else if (form.user_type === 'executive') {
        payload.oversight_region = form.oversight_region.trim();
      }
    } else {
      payload.password = form.password;
      payload.user_type = form.user_type;
      if (form.user_type === 'employee') payload.start_date = form.start_date;
      if (form.user_type === 'employee' && form.supervisor_id) {
        payload.supervisor_id = Number(form.supervisor_id);
      } else if (form.user_type === 'supervisor') {
        payload.executive_id = Number(form.executive_id);
        payload.branch_code = form.branch_code.trim();
      } else if (form.user_type === 'executive') {
        payload.oversight_region = form.oversight_region.trim();
      }
    }

    try {
      if (editingEmployee) {
        await apiRequest(`/api/v1/admin/employees/${editingEmployee.employee_id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        setNotice('Account and hierarchy details updated.');
      } else {
        await apiRequest('/api/v1/admin/employees', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        setNotice('Account created. The password was stored as a hash.');
      }
      setModalOpen(false);
      await loadData(true);
    } catch (requestError) {
      setError(requestError.message || 'Could not save this account.');
    } finally {
      setSaving(false);
    }
  };

  const accounts = overview?.accounts || {};
  const telemetry = overview?.telemetry || {};
  const reports = overview?.reports || {};
  const trustPipeline = overview?.trust_pipeline || {};

  return (
    <div className="ts-dashboard-shell">
      <DashboardSidebar items={ADMIN_NAV} activeId={activeNav} onSelect={(item) => { setActiveNav(item.id); document.getElementById(`admin-${item.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }} />
      <div className="ts-dashboard-content">
      <section className="admin-dashboard">
      <div id="admin-overview" className="admin-page-heading scroll-mt-4">
        <div>
          <p className="admin-eyebrow">TrustScoreAI · Administration</p>
          <h2>Organization overview</h2>
          <p className="admin-subtitle">Monitor organization-wide telemetry and maintain employee reporting lines.</p>
        </div>
        <button className="admin-button admin-button-primary" onClick={openCreate}>
          <span aria-hidden="true">＋</span> Add account
        </button>
      </div>

      {error && !modalOpen && <div className="admin-alert admin-alert-error" role="alert">{error}</div>}
      {notice && !modalOpen && <div className="admin-alert admin-alert-success" role="status">{notice}</div>}

      <div id="admin-people" className="admin-section-head scroll-mt-4">
        <div>
          <h3>People and access</h3>
          <p>Account counts across the organization</p>
        </div>
        <button className="admin-button admin-button-light" onClick={() => loadData(true)} disabled={refreshing}>
          {refreshing ? 'Refreshing…' : 'Refresh data'}
        </button>
      </div>
      <div className="admin-stat-grid">
        <StatCard label="Employees" value={accounts.employees} detail="Base employee accounts" />
        <StatCard label="Supervisors" value={accounts.supervisors} detail="Immediate supervisor accounts" />
        <StatCard label="Executives" value={accounts.executives} detail="Executive manager accounts" />
        <StatCard label="Active accounts" value={accounts.active_accounts} detail={`${accounts.total_accounts ?? 0} total, including admins`} />
      </div>

      <div id="admin-telemetry" className="admin-section-head admin-section-spaced scroll-mt-4">
        <div>
          <h3>Organization-wide telemetry</h3>
          <p>Average across {telemetry.records_count ?? 0} stored performance records</p>
        </div>
        <div className="admin-report-summary">
          <span>{reports.count ?? 0} total reports</span>
          <strong>{reports.average_trust_score == null ? '—' : `${reports.average_trust_score}%`}</strong>
          <small>Historical: {reports.historical_score_count ?? 0} · Performance: {reports.performance_report_count ?? 0} · Average TrustScore</small>
        </div>
      </div>
      {loading ? (
        <div className="admin-loading">Loading organization metrics…</div>
      ) : (
        <div className="admin-kpi-grid">
          {KPI_CARDS.map((metric) => (
            <article className="admin-kpi-card" key={metric.key}>
              <span>{metric.label}</span>
              <strong>{formatValue(telemetry.averages?.[metric.key], metric.unit)}</strong>
              <small>Organization average</small>
            </article>
          ))}
        </div>
      )}

      <section id="admin-regions" className="admin-region-section scroll-mt-4">
        <div className="admin-section-head">
          <div>
            <h3>Oversight regions</h3>
            <p>Expand a region to follow its executive, supervisors, employees, saved records, and eight Trust Score groups.</p>
          </div>
        </div>
        {loading ? (
          <div className="admin-loading">Loading oversight regions…</div>
        ) : regionError ? (
          <div className="admin-alert admin-alert-error" role="alert">Could not load region details: {regionError}</div>
        ) : regions.length === 0 ? (
          <div className="admin-loading">No executive oversight regions have been set up yet.</div>
        ) : regions.map((region) => (
          <details className="admin-region-card" key={region.executive_id}>
            <summary className="admin-region-summary">
              <div>
                <strong>{region.oversight_region || 'Unassigned region'}</strong>
                <span>Executive: {region.executive?.full_name || 'Unassigned'}</span>
              </div>
              <div className="admin-region-counts">
                <span>{region.summary.employee_count} employees</span>
                <span>{region.summary.supervisor_count} supervisors</span>
                <span>{region.summary.telemetry_records} telemetry records</span>
              </div>
            </summary>
            <div className="admin-region-body">
              <div className="admin-region-metrics">
                <span>{region.summary.saved_appraisals} saved appraisals</span>
                <span>{region.summary.historical_reports} historical score reports</span>
                <span>{region.summary.saved_reports} saved performance reports</span>
              </div>
              <h4>Latest team KPI telemetry</h4>
              <div className="admin-kpi-grid admin-region-kpis">
                {KPI_CARDS.map((metric) => (
                  <article className="admin-kpi-card" key={metric.key}>
                    <span>{metric.label}</span>
                    <strong>{formatValue(region.summary.latest_kpi_averages?.[metric.key], metric.unit)}</strong>
                    <small>Average of employees’ latest readings</small>
                  </article>
                ))}
              </div>
              <GroupBars groups={region.summary.group_scores} title="Latest classified group scores · region average" />
              <div className="admin-hierarchy-root">
                <div className="admin-hierarchy-person admin-hierarchy-executive">
                  <span>EXECUTIVE</span>
                  <strong>{region.executive?.full_name || 'Executive'}</strong>
                </div>
                {region.supervisors.map((team) => (
                  <details className="admin-supervisor-branch" key={team.supervisor_id}>
                    <summary>
                      <span className="admin-hierarchy-person admin-hierarchy-supervisor">
                        <span>SUPERVISOR · {team.branch_code || 'Branch not set'}</span>
                        <strong>{team.supervisor?.full_name || 'Supervisor'}</strong>
                      </span>
                      <span className="admin-hierarchy-count">{team.employees.length} employees</span>
                    </summary>
                    <div className="admin-hierarchy-employees">
                      {team.employees.map((person) => (
                        <details className="admin-person-card" key={person.employee_id}>
                          <summary>
                            <span><strong>{person.full_name}</strong><small>{person.role || person.department || 'Employee'} · #{person.employee_id}</small></span>
                            <span className="admin-person-counts">
                              <small>{person.saved_appraisals} appraisals</small>
                              <small>{person.historical_reports + person.saved_reports} reports</small>
                              <small>{person.telemetry_record_count} KPI records</small>
                            </span>
                          </summary>
                          <div className="admin-person-detail">
                            <p className="admin-detail-date">Latest telemetry: {person.latest_telemetry_at ? new Date(person.latest_telemetry_at).toLocaleDateString() : 'No telemetry saved'}</p>
                            <div className="admin-kpi-grid admin-person-kpis">
                              {KPI_CARDS.map((metric) => (
                                <article className="admin-kpi-card" key={metric.key}>
                                  <span>{metric.label}</span>
                                  <strong>{formatValue(person.latest_telemetry?.[metric.key], metric.unit)}</strong>
                                  <small>Latest reading</small>
                                </article>
                              ))}
                            </div>
                            <div className="admin-region-metrics">
                              <span>{person.saved_appraisals} saved appraisals</span>
                              <span>{person.historical_reports} historical score reports</span>
                              <span>{person.saved_reports} saved performance reports</span>
                            </div>
                            <GroupBars groups={person.group_scores} title="Latest eight-group classification" />
                          </div>
                        </details>
                      ))}
                      {team.employees.length === 0 && <p className="admin-hierarchy-empty">No employees are assigned to this supervisor.</p>}
                    </div>
                  </details>
                ))}
                {region.supervisors.length === 0 && <p className="admin-hierarchy-empty">No supervisors are assigned to this oversight region.</p>}
              </div>
            </div>
          </details>
        ))}
      </section>

      <div className="admin-section-head admin-section-spaced">
        <div>
          <h3>Accounts and hierarchy</h3>
          <p>Assign employees to supervisors and supervisors to executives.</p>
        </div>
        <span className="admin-feedback-count">{overview?.feedback_count ?? 0} feedback entries</span>
      </div>
      <div id="admin-directory" className="admin-directory-controls scroll-mt-4">
        <select aria-label="Filter by account type" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
          <option value="all">All account types</option>
          <option value="employee">Employees</option>
          <option value="supervisor">Supervisors</option>
          <option value="executive">Executives</option>
        </select>
      </div>
      <TableControls rows={visibleEmployees} label="accounts" searchText={(employee) => `${employee.full_name} ${employee.email} ${employee.department} ${employee.role} ${employee.supervisor_name} ${employee.executive_name} ${employee.branch_code}`}>
      {(pageRows) => <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Account</th>
              <th>Department and title</th>
              <th>Type</th>
              <th>Reports to</th>
              <th>Status</th>
              <th><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="6" className="admin-empty">Loading accounts…</td></tr>
            ) : pageRows.length === 0 ? (
              <tr><td colSpan="6" className="admin-empty">No accounts match this search.</td></tr>
            ) : pageRows.map((employee) => (
              <tr key={employee.employee_id}>
                <td>
                  <strong>{employee.full_name}</strong>
                  <span>{employee.email} · #{employee.employee_id}</span>
                </td>
                <td>
                  <strong>{employee.department}</strong>
                  <span>{employee.role}</span>
                </td>
                <td><span className={`admin-role-chip admin-role-${employee.user_type}`}>{roleLabel(employee.user_type)}</span></td>
                <td>
                  {employee.user_type === 'employee' ? (
                    <><strong>{employee.supervisor_name || 'Not assigned'}</strong><span>{employee.branch_code || 'Employee reporting line'}</span></>
                  ) : employee.user_type === 'supervisor' ? (
                    <><strong>{employee.executive_name || 'Executive not assigned'}</strong><span>{employee.branch_code || 'Branch not set'}</span></>
                  ) : (
                    <><strong>Organization</strong><span>{employee.oversight_region || 'Region not set'}</span></>
                  )}
                </td>
                <td><span className={`admin-status ${employee.is_active ? 'is-active' : 'is-inactive'}`}>{employee.is_active ? 'Active' : 'Inactive'}</span></td>
                <td><button className="admin-edit-button" onClick={() => openEdit(employee)}>Edit</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>}
      </TableControls>

      <section id="admin-organization-insights" className="admin-ai-panel admin-organization-insights scroll-mt-4">
        <div style={{ width: '100%' }}>
          <p className="admin-eyebrow">Organization overview</p>
          <h3>Organization insights</h3>
          <p>Summary of saved Trust Score runs and supervisor-answer classifications. Group values are averages across employees with saved scores.</p>
          <div className="admin-stat-grid" style={{ marginTop: '14px' }}>
            <StatCard label="Average Trust Score" value={trustPipeline.average_trust_score == null ? '—' : trustPipeline.average_trust_score + '%'} detail={(trustPipeline.scores_ready_count ?? 0) + ' complete runs'} />
            <StatCard label="Classified answers" value={(trustPipeline.feedback_categories || []).reduce((total, item) => total + (item.classified_answer_count || 0), 0)} detail="Supervisor appraisal answers" />
            <StatCard label="Incomplete scores" value={trustPipeline.incomplete_count ?? 0} detail={(trustPipeline.runs_count ?? 0) + ' total period runs'} />
            <StatCard label="Cash error alerts" value={trustPipeline.cash_zero_tolerance_alerts ?? 0} detail="Saved zero-tolerance alerts" />
          </div>
          <GroupBars
            title="Eight-group averages across saved Trust Scores"
            groups={[
              ...(trustPipeline.kpi_groups || []),
              ...(trustPipeline.feedback_categories || []),
            ].map((item) => ({
              category: item.category,
              label: item.label,
              score: item.average_score_0_100,
            }))}
          />
          {!trustPipeline.available && <div className="admin-ai-status">No saved Trust Score classifications are available yet.</div>}
        </div>
      </section>

      {modalOpen && (
        <div className="admin-modal-backdrop" role="presentation" onMouseDown={(event) => {
          if (event.target === event.currentTarget && !saving) setModalOpen(false);
        }}>
          <section className="admin-modal" role="dialog" aria-modal="true" aria-labelledby="admin-modal-title">
            <div className="admin-modal-heading">
              <div>
                <p className="admin-eyebrow">Account administration</p>
                <h3 id="admin-modal-title">{editingEmployee ? 'Edit account' : 'Create account'}</h3>
              </div>
              <button type="button" className="admin-close-button" onClick={() => setModalOpen(false)} disabled={saving} aria-label="Close">×</button>
            </div>
            {error && <div className="admin-alert admin-alert-error" role="alert">{error}</div>}
            <form onSubmit={handleSave} className="admin-form">
              <div className="admin-form-grid">
                <label>Full name<input required minLength="2" value={form.full_name} onChange={(event) => updateField('full_name', event.target.value)} /></label>
                <label>Email<input type="email" required value={form.email} onChange={(event) => updateField('email', event.target.value)} /></label>
                <label>Department<input required value={form.department} onChange={(event) => updateField('department', event.target.value)} /></label>
                <label>Job title<input required value={form.role} onChange={(event) => updateField('role', event.target.value)} /></label>
                <label>Account type
                  <select value={form.user_type} disabled={Boolean(editingEmployee)} onChange={(event) => handleTypeChange(event.target.value)}>
                    <option value="employee">Employee</option>
                    <option value="supervisor">Supervisor</option>
                    <option value="executive">Executive</option>
                  </select>
                </label>
                <label>{editingEmployee ? 'Set a new password (optional)' : 'Initial password'}
                  <input type="password" minLength="12" maxLength="72" required={!editingEmployee} value={form.password} onChange={(event) => updateField('password', event.target.value)} autoComplete="new-password" placeholder={editingEmployee ? 'Leave blank to keep current password' : 'At least 12 characters'} />
                </label>
                {form.user_type === 'employee' && (
                  <>
                    <label>Employment start date
                      <input type="date" required={!editingEmployee} value={form.start_date} onChange={(event) => updateField('start_date', event.target.value)} />
                    </label>
                    <label>Supervisor
                      <select value={form.supervisor_id} onChange={(event) => updateField('supervisor_id', event.target.value)}>
                        <option value="">Not assigned yet</option>
                        {supervisors.map((supervisor) => <option key={supervisor.employee_id} value={supervisor.supervisor_profile_id}>{supervisor.full_name} · {supervisor.branch_code || 'No branch'}</option>)}
                      </select>
                    </label>
                    {editingEmployee && !form.start_date && <p className="admin-form-hint admin-form-wide">Add the employee’s actual start date to enable the correct first appraisal form for late-year joiners.</p>}
                  </>
                )}
                {form.user_type === 'supervisor' && (
                  <>
                    <label>Executive manager
                      <select required value={form.executive_id} onChange={(event) => updateField('executive_id', event.target.value)}>
                        <option value="">Select an executive</option>
                        {executives.map((executive) => <option key={executive.employee_id} value={executive.executive_id || executive.employee_id}>{executive.full_name} · {executive.oversight_region || 'No region'}</option>)}
                      </select>
                    </label>
                    <label>Branch code<input required value={form.branch_code} onChange={(event) => updateField('branch_code', event.target.value)} /></label>
                  </>
                )}
                {form.user_type === 'executive' && (
                  <label className="admin-form-wide">Oversight region<input required value={form.oversight_region} onChange={(event) => updateField('oversight_region', event.target.value)} /></label>
                )}
                {editingEmployee && (
                  <label className="admin-checkbox-label admin-form-wide">
                    <input type="checkbox" checked={form.is_active} onChange={(event) => updateField('is_active', event.target.checked)} />
                    Account is active
                  </label>
                )}
              </div>
              {form.user_type === 'supervisor' && executives.length === 0 && (
                <p className="admin-form-hint">Create an executive account first so this supervisor can be linked into the reporting hierarchy.</p>
              )}
              <p className="admin-form-hint">Passwords must be 12–72 bytes and include uppercase, lowercase, a number, and a symbol. They are hashed before storage.</p>
              <div className="admin-modal-actions">
                <button type="button" className="admin-button admin-button-light" onClick={() => setModalOpen(false)} disabled={saving}>Cancel</button>
                <button type="submit" className="admin-button admin-button-primary" disabled={saving || (form.user_type === 'supervisor' && executives.length === 0)}>{saving ? 'Saving…' : editingEmployee ? 'Save changes' : 'Create account'}</button>
              </div>
            </form>
          </section>
        </div>
      )}
      </section>
      </div>
    </div>
  );
}

function StatCard({ label, value, detail }) {
  return (
    <article className="admin-stat-card">
      <span>{label}</span>
      <strong>{value === undefined || value === null ? '—' : Number(value).toLocaleString()}</strong>
      <small>{detail}</small>
    </article>
  );
}

function GroupBars({ groups = [], title }) {
  const available = groups.some((group) => group.score !== null && group.score !== undefined);
  return (
    <div className="admin-group-chart">
      <h4>{title}</h4>
      {!available ? (
        <p>No saved eight-group classification is available for this view.</p>
      ) : groups.map((group) => (
        <div className="admin-group-bar-row" key={group.category}>
          <span>{group.label}</span>
          <div className="admin-group-track" aria-label={`${group.label}: ${group.score}%`}>
            <div className="admin-group-fill" style={{ width: `${Math.max(0, Math.min(100, Number(group.score) || 0))}%` }} />
          </div>
          <strong>{group.score == null ? '—' : `${group.score}%`}</strong>
        </div>
      ))}
    </div>
  );
}

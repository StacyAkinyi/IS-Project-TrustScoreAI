import { useCallback, useEffect, useMemo, useState } from 'react';
import './AdminDashboard.css';

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
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
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
      const [summary, directory] = await Promise.all([
        apiRequest('/api/v1/admin/overview'),
        apiRequest('/api/v1/admin/employees'),
      ]);
      setOverview(summary);
      setEmployees(directory);
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
    const normalizedSearch = search.trim().toLowerCase();
    return employees
      .filter((employee) => employee.user_type !== 'admin')
      .filter((employee) => roleFilter === 'all' || employee.user_type === roleFilter)
      .filter((employee) => {
        if (!normalizedSearch) return true;
        return [
          employee.full_name,
          employee.email,
          employee.department,
          employee.role,
          employee.supervisor_name,
          employee.executive_name,
          employee.branch_code,
        ].some((value) => String(value || '').toLowerCase().includes(normalizedSearch));
      });
  }, [employees, roleFilter, search]);

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
      } else if (form.user_type === 'supervisor') {
        payload.executive_id = Number(form.executive_id);
        payload.branch_code = form.branch_code.trim();
      } else if (form.user_type === 'executive') {
        payload.oversight_region = form.oversight_region.trim();
      }
    } else {
      payload.password = form.password;
      payload.user_type = form.user_type;
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
    <section className="admin-dashboard">
      <div className="admin-page-heading">
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

      <div className="admin-section-head">
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

      <div className="admin-section-head admin-section-spaced">
        <div>
          <h3>Organization-wide telemetry</h3>
          <p>Average across {telemetry.records_count ?? 0} stored performance records</p>
        </div>
        <div className="admin-report-summary">
          <span>{reports.count ?? 0} reports</span>
          <strong>{reports.average_trust_score == null ? '—' : `${reports.average_trust_score}%`}</strong>
          <small>Average TrustScore</small>
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

      <section className="admin-ai-panel">
        <div>
          <p className="admin-eyebrow">AI insight summary</p>
          <h3>Appraisal competency categories</h3>
          <p>{overview?.ai_categories?.message || 'Category summaries will appear here when classification results are stored.'}</p>
        </div>
        {overview?.ai_categories?.available && overview.ai_categories.items?.length > 0 ? (
          <div className="admin-ai-grid">
            {overview.ai_categories.items.map((item) => (
              <article className="admin-ai-card" key={item.category}>
                <span>{item.label}</span>
                <strong>{item.average_score == null ? '—' : `${item.average_score} / 5`}</strong>
                <small>{item.ratings_count} ratings · {item.human_reviewed_count} human reviewed</small>
              </article>
            ))}
          </div>
        ) : (
          <div className="admin-ai-status">No saved competency ratings yet.</div>
        )}
      </section>

      <section className="admin-ai-panel">
        <div style={{ width: '100%' }}>
          <p className="admin-eyebrow">Model pipeline</p>
          <h3>Unified Trust Score pipeline</h3>
          <p>{trustPipeline.message || 'Run classification from a supervisor dashboard to populate organization-wide results.'}</p>
          <div className="admin-stat-grid" style={{ marginTop: '14px' }}>
            <StatCard label="Average Trust Score" value={trustPipeline.average_trust_score == null ? '—' : trustPipeline.average_trust_score + '%'} detail={(trustPipeline.scores_ready_count ?? 0) + ' complete runs'} />
            <StatCard label="Auto-classified answers" value={(trustPipeline.feedback_categories || []).reduce((total, item) => total + (item.classified_answer_count || 0), 0)} detail="Supervisor appraisal answers" />
            <StatCard label="Incomplete runs" value={trustPipeline.incomplete_count ?? 0} detail={(trustPipeline.runs_count ?? 0) + ' total period runs'} />
            <StatCard label="Cash error alerts" value={trustPipeline.cash_zero_tolerance_alerts ?? 0} detail="Zero-tolerance control breaches" />
          </div>
          <div className="admin-ai-grid" style={{ marginTop: '12px', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))' }}>
            {(trustPipeline.kpi_groups || []).map((item) => (
              <article className="admin-ai-card" key={item.category}>
                <span>KPI · {item.label}</span>
                <strong>{item.average_score_0_100 == null ? '—' : item.average_score_0_100 + '%'}</strong>
                <small>{item.sample_count} period groups</small>
              </article>
            ))}
            {(trustPipeline.feedback_categories || []).map((item) => {
              const directions = item.predicted_directions || {};
              return (
                <article className="admin-ai-card" key={item.category}>
                  <span>Feedback · {item.label}</span>
                  <strong>{item.average_score_0_100 == null ? '—' : item.average_score_0_100 + '%'}</strong>
                  <small>{item.classified_answer_count} classified answers · {item.scored_run_count} scored runs</small>
                  <small>Suggestions: +{directions.positive || 0} / −{directions.negative || 0} / mixed {directions.mixed || 0} / neutral {directions.neutral || 0}</small>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <div className="admin-section-head admin-section-spaced">
        <div>
          <h3>Accounts and hierarchy</h3>
          <p>Assign employees to supervisors and supervisors to executives.</p>
        </div>
        <span className="admin-feedback-count">{overview?.feedback_count ?? 0} feedback entries</span>
      </div>
      <div className="admin-directory-controls">
        <input
          aria-label="Search accounts"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search name, email, department, or manager"
        />
        <select aria-label="Filter by account type" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
          <option value="all">All account types</option>
          <option value="employee">Employees</option>
          <option value="supervisor">Supervisors</option>
          <option value="executive">Executives</option>
        </select>
      </div>
      <div className="admin-table-wrap">
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
            ) : visibleEmployees.length === 0 ? (
              <tr><td colSpan="6" className="admin-empty">No accounts match this search.</td></tr>
            ) : visibleEmployees.map((employee) => (
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
      </div>

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
                  <label className="admin-form-wide">Supervisor
                    <select value={form.supervisor_id} onChange={(event) => updateField('supervisor_id', event.target.value)}>
                      <option value="">Not assigned yet</option>
                      {supervisors.map((supervisor) => <option key={supervisor.employee_id} value={supervisor.supervisor_profile_id}>{supervisor.full_name} · {supervisor.branch_code || 'No branch'}</option>)}
                    </select>
                  </label>
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

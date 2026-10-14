import React from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const riskMetrics = [
  { key: 'transaction_accuracy', label: 'Transaction accuracy', unit: '%', direction: 'high', max: 100, decimals: 1 },
  { key: 'workplan_completion', label: 'Workplan completion', unit: '%', direction: 'high', max: 120, decimals: 1 },
  { key: 'task_deadline_fulfillment_pct', label: 'Tasks completed on time', unit: '%', direction: 'high', max: 100, decimals: 1 },
  { key: 'complaint_resolution_rate_pct', label: 'Complaint resolution', unit: '%', direction: 'high', max: 100, decimals: 1 },
  { key: 'customer_satisfaction', label: 'Customer satisfaction', unit: '/ 5', direction: 'high', max: 5, decimals: 2 },
  { key: 'error_frequencies', label: 'Processing errors', unit: '', direction: 'low', max: 15, decimals: 0 },
  { key: 'loan_processing_turnaround_hours', label: 'Loan processing time', unit: ' hrs', direction: 'low', max: 96, decimals: 1 },
  { key: 'non_performing_credit_pct', label: 'Non-performing credit', unit: '%', direction: 'low', max: 18, decimals: 1 },
  { key: 'cash_reconciliation_errors', label: 'Cash reconciliation errors', unit: '', direction: 'low', max: 10, decimals: 0 },
  { key: 'compliance_incidents', label: 'Compliance incidents', unit: '', direction: 'low', max: 4, decimals: 0 },
];

const contextMetrics = [
  { key: 'loan_volumes', label: 'Loans processed', unit: ' loans', decimals: 0 },
  { key: 'accounts_opened', label: 'Accounts opened', unit: ' accounts', decimals: 0 },
  { key: 'digital_channel_adoption_pct', label: 'Digital channel adoption', unit: '%', decimals: 1 },
];

const bandLimits = (metric) => ({
  firstThird: metric.max / 3,
  secondThird: (metric.max * 2) / 3,
});

const statusFor = (metric, value) => {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return 'No data';
  const normalizedValue = Number(value) / metric.max;
  if (metric.direction === 'high') {
    return normalizedValue < 1 / 3 ? 'Danger' : normalizedValue < 2 / 3 ? 'Warning' : 'Safe';
  }
  return normalizedValue <= 1 / 3 ? 'Safe' : normalizedValue <= 2 / 3 ? 'Warning' : 'Danger';
};

const statusClasses = {
  Safe: 'border-green-200 bg-green-50 text-green-800',
  Warning: 'border-orange-200 bg-orange-50 text-orange-800',
  Danger: 'border-red-200 bg-red-50 text-red-800',
  'No data': 'border-slate-200 bg-slate-50 text-slate-600',
};

const forecastNextMonth = (records, metric) => {
  const latestRecord = records[records.length - 1];
  const latestValue = Number(latestRecord?.[metric.key]);
  if (!Number.isFinite(latestValue)) return null;

  const points = records.slice(-6).map((record, index) => {
    const date = new Date(record.recorded_at);
    const x = Number.isNaN(date.getTime())
      ? index
      : date.getFullYear() * 12 + date.getMonth();
    return { x, y: Number(record[metric.key]) };
  }).filter((point) => Number.isFinite(point.y));

  if (points.length < 2) return latestValue;
  const meanX = points.reduce((sum, point) => sum + point.x, 0) / points.length;
  const meanY = points.reduce((sum, point) => sum + point.y, 0) / points.length;
  const denominator = points.reduce((sum, point) => sum + ((point.x - meanX) ** 2), 0);
  const slope = denominator === 0
    ? 0
    : points.reduce((sum, point) => sum + ((point.x - meanX) * (point.y - meanY)), 0) / denominator;
  const latestDate = new Date(latestRecord.recorded_at);
  const nextX = Number.isNaN(latestDate.getTime())
    ? points[points.length - 1].x + 1
    : latestDate.getFullYear() * 12 + latestDate.getMonth() + 1;
  const prediction = meanY + slope * (nextX - meanX);
  return Math.max(0, metric.max === undefined ? prediction : Math.min(metric.max, prediction));
};

const formatValue = (value, metric) => Number(value).toFixed(metric.decimals) + metric.unit;
const monthLabel = (value) => new Date(value).toLocaleDateString('en-KE', { month: 'short', year: '2-digit' });

function MetricChart({ metric, records, banded = false }) {
  const latest = records[records.length - 1];
  const value = Number(latest[metric.key]);
  const forecastValue = forecastNextMonth(records, metric);
  const { firstThird, secondThird } = bandLimits(metric);
  const status = banded ? statusFor(metric, value) : null;
  const forecastStatus = banded ? statusFor(metric, forecastValue) : null;
  const lineColor = status === 'Danger' ? '#dc2626' : status === 'Warning' ? '#ea580c' : status === 'Safe' ? '#16a34a' : '#2563eb';
  const forecastLineColor = forecastStatus === 'Danger' ? '#dc2626' : forecastStatus === 'Warning' ? '#ea580c' : forecastStatus === 'Safe' ? '#16a34a' : '#64748b';
  const chartData = records.map((record, index) => ({
    month: monthLabel(record.recorded_at),
    value: Number(record[metric.key]),
    forecast: index === records.length - 1 ? Number(record[metric.key]) : null,
  }));
  const latestDate = new Date(latest.recorded_at);
  const nextMonth = Number.isNaN(latestDate.getTime())
    ? new Date()
    : new Date(latestDate.getFullYear(), latestDate.getMonth() + 1, 1);
  chartData.push({ month: monthLabel(nextMonth), value: null, forecast: forecastValue });

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h4 className="font-bold text-slate-800">{metric.label}</h4>
          <p className="text-xs text-slate-500">{banded ? 'Demo review bands · monthly history' : 'Monthly context · no pass/fail band'}</p>
        </div>
        {banded ? (
          <span className={'whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-bold ' + statusClasses[status]}>
            {status}
          </span>
        ) : <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">Context</span>}
      </div>
      <div className="mb-2 grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-slate-500">Latest</p>
          <p className="text-lg font-bold text-slate-900">{formatValue(value, metric)}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">Next month estimate</p>
          <p className="text-lg font-bold text-slate-800">{forecastValue === null ? 'No estimate' : formatValue(forecastValue, metric)}</p>
          {banded && forecastStatus && (
            <span className={'inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ' + statusClasses[forecastStatus]}>
              Forecast: {forecastStatus}
            </span>
          )}
        </div>
      </div>
      <div className="mb-1 flex gap-4 text-xs text-slate-500">
        <span><span className="mr-1 inline-block w-4 border-t-2 border-blue-600 align-middle" />History</span>
        <span><span className="mr-1 inline-block w-4 border-t-2 border-dashed border-slate-500 align-middle" />Next month estimate</span>
      </div>
      <div className="h-44 w-full" style={{ height: 176, minHeight: 176, width: "100%" }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 10, left: -18, bottom: 0 }}>
            {banded && metric.direction === 'high' && (
              <>
                <ReferenceArea y1={0} y2={firstThird} fill="#fee2e2" fillOpacity={0.72} />
                <ReferenceArea y1={firstThird} y2={secondThird} fill="#ffedd5" fillOpacity={0.8} />
                <ReferenceArea y1={secondThird} y2={metric.max} fill="#dcfce7" fillOpacity={0.78} />
              </>
            )}
            {banded && metric.direction === 'low' && (
              <>
                <ReferenceArea y1={0} y2={firstThird} fill="#dcfce7" fillOpacity={0.78} />
                <ReferenceArea y1={firstThird} y2={secondThird} fill="#ffedd5" fillOpacity={0.8} />
                <ReferenceArea y1={secondThird} y2={metric.max} fill="#fee2e2" fillOpacity={0.72} />
              </>
            )}
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#cbd5e1" />
            <XAxis dataKey="month" tick={{ fontSize: 10 }} tickLine={false} axisLine={false} minTickGap={20} />
            <YAxis domain={banded ? [0, metric.max] : ['auto', 'auto']} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} width={42} />
            <Tooltip
              formatter={(item) => [formatValue(item, metric), metric.label]}
              labelStyle={{ color: '#0f172a' }}
            />
            <Line type="monotone" dataKey="value" name="History" stroke={lineColor} strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
            <Line type="monotone" dataKey="forecast" name="Next month estimate" stroke={forecastLineColor} strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 4 }} activeDot={{ r: 5 }} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
}

export default function PerformanceCharts({ performanceRecords }) {
  if (!performanceRecords || performanceRecords.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="font-semibold text-slate-700">No performance telemetry is loaded yet.</p>
        <p className="mt-1 text-sm text-slate-500">Generate and load the synthetic demo history to view this section.</p>
      </div>
    );
  }

  const records = [...performanceRecords].sort((a, b) => new Date(a.recorded_at) - new Date(b.recorded_at));
  const latest = records[records.length - 1];
  const counts = riskMetrics.reduce((total, metric) => {
    total[statusFor(metric, Number(latest[metric.key]))] += 1;
    return total;
  }, { Safe: 0, Warning: 0, Danger: 0, 'No data': 0 });

  const summaryCards = [
    { label: 'Safe', count: counts.Safe, style: 'border-green-200 bg-green-50 text-green-800' },
    { label: 'Warning', count: counts.Warning, style: 'border-orange-200 bg-orange-50 text-orange-800' },
    { label: 'Danger', count: counts.Danger, style: 'border-red-200 bg-red-50 text-red-800' },
  ];

  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
        <h4 className="font-bold text-blue-900">Monthly performance telemetry</h4>
        <p className="mt-1 text-sm text-blue-900">
          Each KPI scale is split into thirds. Higher-is-better measures use red, orange, then green; lower-is-better measures reverse the order. Dashed lines estimate next month from a linear trend in up to six recent readings; with one reading, the latest value is carried forward. Estimates are exploratory and are not bank policy or an automated employment decision.
        </p>
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Latest KPI status summary">
          {summaryCards.map((card) => (
            <span key={card.label} className={'rounded-full border px-3 py-1 text-sm font-bold ' + card.style}>
              {card.label}: {card.count}
            </span>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-lg font-bold text-slate-800">Quality and risk indicators</h3>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {riskMetrics.map((metric) => <MetricChart key={metric.key} metric={metric} records={records} banded />)}
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-lg font-bold text-slate-800">Workload and adoption context</h3>
        <p className="mb-3 text-sm text-slate-600">These measures are shown as trends without red/green judgments because volumes vary by role and branch.</p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {contextMetrics.map((metric) => <MetricChart key={metric.key} metric={metric} records={records} />)}
        </div>
      </div>
    </section>
  );
}


import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

export default function PerformanceCharts({ performanceRecords }) {
  if (!performanceRecords || performanceRecords.length === 0) {
    return <p className="text-slate-500 text-sm">No historical performance records available for regression analysis.</p>;
  }

  const sortedRecords = [...performanceRecords].sort((a, b) => {
    const dateA = a.recorded_at ? new Date(a.recorded_at) : 0;
    const dateB = b.recorded_at ? new Date(b.recorded_at) : 0;
    return dateA - dateB;
  });

  const calculateRegressionForecast = (dataPoints) => {
    const n = dataPoints.length;
    if (n < 2) return { nextPrediction: dataPoints[0]?.y || 0, trend: 'Stable' };

    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    dataPoints.forEach((pt, index) => {
      sumX += index;
      sumY += pt.y;
      sumXY += index * pt.y;
      sumXX += index * index;
    });

    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    const nextPrediction = slope * n + intercept;
    const trend = slope > 0 ? 'Upward Trend 📈' : slope < 0 ? 'Downward Trend 📉' : 'Stable ➔';

    return { nextPrediction: Math.round(nextPrediction * 100) / 100, trend };
  };

  const formatMonthLabel = (dateStr, index) => {
    if (!dateStr) return `M${index + 1}`;
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return `M${index + 1}`;
    return d.toLocaleDateString('en-US', { month: 'short' });
  };

  const metrics = [
    { key: 'loan_volumes', label: 'Loan Volumes', unit: ' units' },
    { key: 'transaction_accuracy', label: 'Transaction Accuracy', unit: '%' },
    { key: 'workplan_completion', label: 'Workplan Completion', unit: '%' },
    { key: 'error_frequencies', label: 'Error Frequencies (KRI)', unit: ' errors' }
  ];

  return (
    <div style={{ width: '100%', padding: '10px' }}>
      <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', padding: '16px', borderRadius: '8px', marginBottom: '24px' }}>
        <h4 style={{ fontWeight: 'bold', color: '#1e3a8a', margin: 0 }}>Predictive Analytics & Regression Engine</h4>
        <p style={{ color: '#475569', fontSize: '12px', marginTop: '4px' }}>
          Historical monthly telemetry analyzed via linear regression to forecast next-month performance trajectories.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
        {metrics.map((metric) => {
          const dataPoints = sortedRecords.map(r => ({ y: Number(r[metric.key]) || 0 }));
          const { nextPrediction, trend } = calculateRegressionForecast(dataPoints);
          const currentVal = dataPoints[dataPoints.length - 1]?.y || 0;

          const chartData = sortedRecords.map((rec, idx) => ({
            month: formatMonthLabel(rec.recorded_at, idx),
            value: Number(rec[metric.key]) || 0,
          }));

          chartData.push({
            month: 'Pred',
            value: nextPrediction,
          });

          return (
            <div key={metric.key} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', backgroundColor: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h5 style={{ margin: 0, fontWeight: 'bold', color: '#1e293b' }}>{metric.label}</h5>
                  <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>Monthly progression & forecast</p>
                </div>
                <span style={{ fontSize: '12px', fontWeight: 'bold', backgroundColor: '#f1f5f9', padding: '4px 8px', borderRadius: '4px' }}>
                  {trend}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', backgroundColor: '#f8fafc', padding: '10px', borderRadius: '6px', border: '1px solid #f1f5f9', marginBottom: '16px' }}>
                <div>
                  <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>Latest Recorded</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#0f172a' }}>{currentVal}{metric.unit}</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ margin: 0, fontSize: '11px', color: '#2563eb', fontWeight: 'bold' }}>Next Month Prediction (ML)</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#1e3a8a' }}>{nextPrediction}{metric.unit}</p>
                </div>
              </div>

              {/* Fixed 200px Height Container for Recharts */}
              <div style={{ width: '100%', height: '200px', minHeight: '200px' }}>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} domain={['auto', 'auto']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0f172a', borderRadius: '6px', color: '#fff', fontSize: '12px', border: 'none' }}
                      formatter={(val) => [`${val}${metric.unit}`, metric.label]}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#2563eb"
                      strokeWidth={2.5}
                      dot={{ r: 4, fill: '#2563eb' }}
                      activeDot={{ r: 6 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
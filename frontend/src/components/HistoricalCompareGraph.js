import React, { useState, useEffect, useCallback, useMemo } from 'react';
import locationService from '../services/locationService';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts';

const YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026, 'all'];
const MODES = [
  { key: 'monthly', label: 'Monthly' },
  { key: 'weekly', label: 'Weekly' },
  { key: 'daily', label: 'Daily' },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const actual = payload.find(p => p.dataKey === 'gee_actual');
  const pred = payload.find(p => p.dataKey === 'ml_prediction');
  
  const actualVal = actual?.value;
  const predVal = pred?.value;
  
  const diff = (actualVal != null && predVal != null)
    ? (actualVal - predVal).toFixed(4)
    : null;
    
  const pctErr = (actualVal && predVal)
    ? (Math.abs(actualVal - predVal) / actualVal * 100).toFixed(1)
    : null;
    
  return (
    <div className="compare-tooltip">
      <p className="compare-tooltip-label">{label}</p>
      {actualVal != null && <p style={{color:'#3b82f6'}}>Satellite Actual: {Number(actualVal).toFixed(4)}</p>}
      {predVal != null && <p style={{color:'#10b981'}}>ML Prediction: {Number(predVal).toFixed(4)}</p>}
      {diff !== null && <p style={{color:'#f59e0b'}}>Difference: {diff}</p>}
      {pctErr !== null && <p style={{color:'#ef4444'}}>% Error: {pctErr}%</p>}
    </div>
  );
};

const getStatCards = (stats, unit) => [
  { label: 'Avg Satellite Actual', value: stats.avg_actual?.toFixed(4), unit },
  { label: 'Avg ML Prediction', value: stats.avg_prediction?.toFixed(4), unit },
  { label: 'Avg Difference', value: stats.avg_difference?.toFixed(4), unit },
  { label: '% Difference', value: stats.pct_difference?.toFixed(1), unit: '%' },
  { label: 'MAE', value: stats.mae?.toFixed(4), unit },
  { label: 'RMSE', value: stats.rmse?.toFixed(4), unit },
  { label: 'Correlation (r)', value: stats.correlation?.toFixed(4), unit: '' },
  { label: 'R²', value: stats.r_squared?.toFixed(4), unit: '' },
];

const HistoricalCompareGraph = ({ lat, lon, pollutant, whoLimit, pollutantName, unit }) => {
  const [selectedYear, setSelectedYear] = useState(2024);
  const [mode, setMode] = useState('monthly');
  const [page, setPage] = useState(1);
  const [selectedMonth, setSelectedMonth] = useState(1);
  const [compData, setCompData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!lat || !lon) return;
    setLoading(true);
    setError(null);
    try {
      const data = await locationService.getComparison({
        lat, lon, pollutant, year: selectedYear, mode, page, month: selectedMonth
      });
      console.log("Comparison API Response:", data);
      setCompData(data);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load comparison data.');
    } finally {
      setLoading(false);
    }
  }, [lat, lon, pollutant, selectedYear, mode, page, selectedMonth]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    setPage(1);
  }, [selectedYear, mode, selectedMonth]);

  return (
    <div className="historical-compare-container">
      <div className="compare-controls">
        <div className="compare-year-selector">
          <span className="compare-control-label">Year</span>
          <div className="compare-btn-group">
            {YEARS.map(yr => (
              <button
                key={yr}
                className={`compare-btn ${selectedYear === yr ? 'active' : ''}`}
                onClick={() => setSelectedYear(yr)}
              >
                {yr === 'all' ? 'All' : yr}
              </button>
            ))}
          </div>
        </div>

        {selectedYear !== 'all' && (
          <div className="compare-mode-selector">
            <span className="compare-control-label">View</span>
            <div className="compare-btn-group">
              {MODES.map(m => (
                <button
                  key={m.key}
                  className={`compare-btn ${mode === m.key ? 'active' : ''}`}
                  onClick={() => setMode(m.key)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {selectedYear !== 'all' && mode === 'daily' && (
          <div className="compare-month-selector">
            <span className="compare-control-label">Month</span>
            <select
              className="compare-select"
              value={selectedMonth}
              onChange={e => { setSelectedMonth(Number(e.target.value)); setPage(1); }}
            >
              {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((m, i) => (
                <option key={i+1} value={i+1}>{m}</option>
              ))}
            </select>
          </div>
        )}

        {selectedYear !== 'all' && (mode === 'weekly' || mode === 'daily') && compData?.pagination && (
          <div className="compare-pagination">
            <button
              className="compare-btn"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={!compData.pagination.has_prev}
            >
              ← Prev
            </button>
            <span className="compare-page-info">
              Page {compData.pagination.current_page} of {compData.pagination.total_pages}
            </span>
            <button
              className="compare-btn"
              onClick={() => setPage(p => p + 1)}
              disabled={!compData.pagination.has_next}
            >
              Next →
            </button>
          </div>
        )}
      </div>

      {loading && <div className="compare-skeleton" />}

      {error && !loading && (
        <div className="compare-error-banner">⚠ {error}</div>
      )}

      {compData?.message && !loading && !error && (
        <div className="compare-info-banner">
          ℹ {compData.message}
        </div>
      )}

      {/* Satellite partial-failure notice: shown when some months failed but not all */}
      {compData && !loading && !error && !compData.is_current_year && (() => {
        const chartData = Array.isArray(compData?.data) ? compData.data : [];
        const failedLabels = chartData
          .filter(d => d.has_gee === false && d.gee_actual === null)
          .map(d => d.label);
        const totalExpected = chartData.length;
        if (failedLabels.length === 0 || failedLabels.length === totalExpected) return null;
        return (
          <div className="compare-warn-banner">
            ⚠ Satellite data unavailable for {failedLabels.length} period{failedLabels.length > 1 ? 's' : ''}:
            {' '}<strong>{failedLabels.join(', ')}</strong>.
            {' '}These appear as gaps in the Satellite Actual line.
          </div>
        );
      })()}

      {/* Satellite total-failure notice: all months failed */}
      {compData && !loading && !error && !compData.is_current_year && (() => {
        const chartData = Array.isArray(compData?.data) ? compData.data : [];
        const allFailed =
            chartData.length > 0 &&
            chartData.every(d => d.gee_actual === null);
        if (!allFailed) return null;
        return (
          <div className="compare-error-banner">
            ⚠ Satellite observation source returned no data for any period in {compData.year}.
            {' '}Only the ML Prediction line is shown below.
          </div>
        );
      })()}

      {compData && !loading && !error && (
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={Array.isArray(compData?.data) ? compData.data : []} margin={{ top: 10, right: 30, left: 20, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            <ReferenceLine y={whoLimit} stroke="#ef4444" strokeDasharray="5 5"
              label={{ value: 'Safe Limit', position: 'right', fontSize: 11, fill: '#ef4444' }} />
            <Line
              type="monotone" dataKey="gee_actual" stroke="#3b82f6"
              strokeWidth={2}
              dot={(props) => {
                const { cx, cy, payload } = props;
                if (payload.gee_actual == null) return <g key={`gee-null-${payload.date}`} />;
                return <circle key={`gee-${payload.date}`} cx={cx} cy={cy} r={4} fill="#3b82f6" stroke="#fff" strokeWidth={1.5} />;
              }}
              name="Satellite Actual"
              connectNulls={false}
            />
            <Line
              type="monotone" dataKey="ml_prediction" stroke="#10b981"
              strokeWidth={2}
              dot={(props) => {
                const { cx, cy, payload } = props;
                if (payload.ml_prediction == null) return <g key={`ml-null-${payload.date}`} />;
                return <circle key={`ml-${payload.date}`} cx={cx} cy={cy} r={4} fill="#10b981" stroke="#fff" strokeWidth={1.5} />;
              }}
              name="ML Prediction"
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {compData?.stats && !compData.is_current_year && !loading && (
        <div className="compare-stats-panel">
          <h4 className="compare-stats-title">📊 Model Accuracy Statistics</h4>
          <div className="compare-stats-grid">
            {getStatCards(compData.stats, unit).map((card, i) => (
              <div key={i} className="compare-stat-card">
                <span className="compare-stat-label">{card.label}</span>
                <span className="compare-stat-value">
                  {card.value ?? '--'}
                  {card.unit && <small> {card.unit}</small>}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default HistoricalCompareGraph;

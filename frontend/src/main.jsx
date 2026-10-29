import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Activity, AlertCircle, ArrowDownRight, ArrowUpRight, CalendarDays, CheckCircle2, ChevronDown, Clock3, Download, ExternalLink, Gauge, RefreshCw, Wind, Zap } from 'lucide-react';
import './styles.css';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const fmt = (v, digits = 0) => v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toLocaleString('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: digits });
const compactTime = (iso) => iso ? new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short' }) : '—';

function MetricCard({ title, value, unit, icon: Icon, hint, tone = 'blue' }) {
  return <article className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={18}/></div><div className="metric-label">{title}</div><div className="metric-value">{value}<span>{unit}</span></div><div className="metric-hint">{hint}</div></article>;
}

function App() {
  const [year, setYear] = useState('2026');
  const [month, setMonth] = useState('1');
  const [view, setView] = useState('day-ahead');
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAll, setShowAll] = useState(false);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const response = await fetch(`${API_BASE}/api/analysis?year=${year}&month=${month}&view=${view}`);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `API request failed (${response.status})`);
      }
      setPayload(await response.json());
    } catch (e) {
      setError(`${e.message}. Start the Python backend and check its API connectivity.`);
      setPayload(null);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const chartData = useMemo(() => (payload?.records || []).map(r => ({ ...r, label: r.startTime ? new Date(r.startTime).toLocaleString('en-GB', { day: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) : '', forecast: r.forecast == null ? null : Number(r.forecast), actual: r.actual == null ? null : Number(r.actual), error: r.error == null ? null : Number(r.error) })), [payload]);
  const tableData = showAll ? chartData : chartData.slice(0, 12);
  const m = payload?.metrics || {};
  const downloadCsv = () => {
    const rows = payload?.records || [];
    if (!rows.length) return;
    const cols = ['startTime', 'publishTime', 'forecast', 'actual', 'error'];
    const csv = [cols.join(','), ...rows.map(r => cols.map(c => JSON.stringify(r[c] ?? '')).join(','))].join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    const a = document.createElement('a'); a.href = url; a.download = `windsight-${payload.period}-${view}.csv`; a.click(); URL.revokeObjectURL(url);
  };

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Wind size={23}/></div><div><div className="brand-name">WindSight</div><div className="brand-sub">FORECAST INTELLIGENCE</div></div></div>
      <div className="nav-caption">WORKSPACE</div>
      <div className="nav-item active"><Activity size={18}/> Forecast overview</div>
      <div className="nav-item"><Gauge size={18}/> Accuracy analysis <span className="nav-dot"/></div>
      <div className="nav-item"><CalendarDays size={18}/> Delivery periods</div>
      <div className="sidebar-bottom"><div className="status-card"><div className="status-head"><span className="status-pulse"/> Data connection</div><p>Elexon Insights API</p><span className="status-small">Public source · No API key</span></div><div className="profile"><div className="avatar">WS</div><div><strong>Energy Analytics</strong><small>Analyst workspace</small></div><ChevronDown size={15}/></div></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>Forecast overview</strong></div><div className="top-actions"><span className="live-tag"><span/> ELEXON DATA</span><button className="icon-btn" title="Refresh data" onClick={load} disabled={loading}><RefreshCw size={17} className={loading ? 'spin' : ''}/></button></div></header>
      <section className="page-heading"><div><div className="eyebrow">UK POWER MARKET · WIND GENERATION</div><h1>Forecast overview</h1><p>Understand renewable output, compare forecast vintages and quantify forecast error before procurement decisions.</p></div><div className="heading-badge"><div className="badge-icon"><Zap size={19}/></div><div><strong>Day-ahead view</strong><small>Prior-day information only</small></div></div></section>

      <section className="filter-bar"><div className="filter-title"><CalendarDays size={17}/><span>Analysis period</span></div><label>Month<select value={month} onChange={e => setMonth(e.target.value)}>{Array.from({length:12},(_,i)=><option key={i+1} value={i+1}>{new Date(2026,i,1).toLocaleString('en-GB',{month:'long'})}</option>)}</select></label><label>Year<select value={year} onChange={e => setYear(e.target.value)}><option>2026</option><option>2025</option><option>2024</option></select></label><label className="view-select">Forecast view<select value={view} onChange={e => setView(e.target.value)}><option value="day-ahead">Day-ahead decision vintage</option><option value="latest">Latest available vintage</option></select></label><button className="primary-btn" onClick={load} disabled={loading}>{loading ? <RefreshCw size={16} className="spin"/> : <Activity size={16}/>} Analyse period</button></section>

      {error && <div className="alert error"><AlertCircle size={18}/><div><strong>Could not load live data</strong><p>{error}</p></div></div>}
      {payload?.dataStatus === 'unavailable' && <div className="alert error"><AlertCircle size={18}/><div><strong>No usable records returned</strong><p>{payload.message}</p></div></div>}
      {payload?.message && payload.dataStatus !== 'unavailable' && <div className="alert info"><AlertCircle size={18}/><div><strong>Partial data coverage</strong><p>{payload.message}</p></div></div>}

      <section className="metrics-grid">
        <MetricCard title="Mean absolute error" value={fmt(m.maeMw, 1)} unit=" MW" icon={Activity} hint="Lower is better" tone="blue"/>
        <MetricCard title="Root mean square error" value={fmt(m.rmseMw, 1)} unit=" MW" icon={Gauge} hint="Penalises larger misses" tone="purple"/>
        <MetricCard title="Forecast bias" value={m.biasMw == null ? '—' : `${m.biasMw > 0 ? '+' : ''}${fmt(m.biasMw, 1)}`} unit=" MW" icon={m.biasMw > 0 ? ArrowUpRight : ArrowDownRight} hint="Positive = over-forecast" tone={m.biasMw > 0 ? 'orange' : 'green'}/>
        <MetricCard title="Matched intervals" value={fmt(m.matchedIntervals)} unit=" / 30 min" icon={CheckCircle2} hint="Actual + forecast available" tone="green"/>
      </section>

      <section className="chart-grid"><article className="panel chart-panel"><div className="panel-head"><div><h2>Forecast vs actual generation</h2><p>National wind generation · MW · UTC</p></div><span className="chart-legend"><i className="legend-forecast"/> Forecast <i className="legend-actual"/> Actual</span></div><div className="chart-area">{chartData.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{top:12,right:12,left:0,bottom:0}}><CartesianGrid strokeDasharray="3 3" stroke="#e9edf4"/><XAxis dataKey="label" tick={{fontSize:10,fill:'#778197'}} minTickGap={35}/><YAxis tick={{fontSize:10,fill:'#778197'}} width={52}/><Tooltip labelFormatter={(label,items)=>items?.[0]?.payload?.startTime ? compactTime(items[0].payload.startTime) : label} formatter={(v,name)=>[v == null ? 'No data' : `${fmt(v,1)} MW`, name === 'forecast' ? 'Forecast' : 'Actual']}/><Legend/><Line type="monotone" dataKey="forecast" name="Forecast" stroke="#5478f5" strokeWidth={2.3} dot={false} connectNulls={false}/><Line type="monotone" dataKey="actual" name="Actual" stroke="#18a889" strokeWidth={2.3} dot={false} connectNulls={false}/></LineChart></ResponsiveContainer> : <div className="empty-state"><Activity size={30}/><strong>No chart data yet</strong><span>Choose a period and select Analyse period.</span></div>}</div><div className="chart-foot"><span><Clock3 size={14}/> Half-hourly settlement intervals</span><span>{chartData.length.toLocaleString()} records</span></div></article>
      <article className="panel error-panel"><div className="panel-head"><div><h2>Forecast error distribution</h2><p>Forecast minus actual · MW</p></div></div><div className="chart-area error-chart">{chartData.some(r=>r.error != null) ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData.filter(r=>r.error != null)} margin={{top:12,right:8,left:0,bottom:0}}><CartesianGrid strokeDasharray="3 3" stroke="#e9edf4"/><XAxis dataKey="label" tick={{fontSize:10,fill:'#778197'}} minTickGap={35}/><YAxis tick={{fontSize:10,fill:'#778197'}} width={45}/><Tooltip formatter={v=>[`${fmt(v,1)} MW`,'Error']}/><Area type="monotone" dataKey="error" stroke="#8a70e8" fill="#e8e1ff" strokeWidth={2} connectNulls={false}/></AreaChart></ResponsiveContainer> : <div className="empty-state"><Gauge size={30}/><strong>Awaiting matched data</strong><span>Error appears when actuals and forecasts overlap.</span></div>}</div><div className="error-summary"><div><span>Over-forecast</span><strong>{fmt(m.overForecastIntervals)}</strong></div><div><span>Under-forecast</span><strong>{fmt(m.underForecastIntervals)}</strong></div></div></article></section>

      <section className="panel table-panel"><div className="panel-head table-head"><div><h2>Settlement interval detail</h2><p>Forecast publication time is shown for auditability.</p></div><button className="secondary-btn" onClick={downloadCsv} disabled={!chartData.length}><Download size={15}/> Export CSV</button></div><div className="table-wrap"><table><thead><tr><th>Delivery interval (UTC)</th><th>Published (UTC)</th><th>Forecast (MW)</th><th>Actual (MW)</th><th>Error (MW)</th><th>Status</th></tr></thead><tbody>{tableData.map((r,i)=><tr key={`${r.startTime}-${i}`}><td className="time-cell">{compactTime(r.startTime)}</td><td>{compactTime(r.publishTime)}</td><td>{fmt(r.forecast,1)}</td><td>{fmt(r.actual,1)}</td><td className={r.error > 0 ? 'positive' : r.error < 0 ? 'negative' : ''}>{fmt(r.error,1)}</td><td>{r.actual == null ? <span className="pill pending">Forecast only</span> : <span className="pill matched">Matched</span>}</td></tr>)}</tbody></table>{!tableData.length && <div className="table-empty">No records to display. Load data from the Elexon API to populate this table.</div>}</div>{chartData.length > 12 && <button className="show-more" onClick={()=>setShowAll(v=>!v)}>{showAll ? 'Show fewer rows' : `Show all ${chartData.length.toLocaleString()} records`}</button>}</section>

      <section className="bottom-grid"><article className="insight-card"><div className="insight-icon"><Zap size={19}/></div><div><h3>Decision support, not a trading instruction</h3><p>Use the day-ahead forecast and historical error together. A positive bias means the selected forecast vintage tended to exceed actual wind generation; it does not by itself determine how much power to procure.</p></div></article><article className="source-card"><div><h3>Data provenance</h3><p>FUELHH · Actual generation by fuel type (WIND)<br/>WINDFOR · Wind generation forecast vintages</p><a href="https://bmrs.elexon.co.uk/api-documentation/endpoint" target="_blank" rel="noreferrer">Official Elexon API docs <ExternalLink size={13}/></a></div><div className="source-mark"><Wind size={22}/></div></article></section>
      <footer className="footer"><span>WindSight · Pilot analytics experience</span><span>All timestamps shown in UTC · MW = megawatts</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App/></React.StrictMode>);

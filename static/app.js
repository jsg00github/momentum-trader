const { useState, useEffect, useMemo, useRef, Fragment } = React;
// Use global API_BASE from config.js, or fallback to relative (for safety)
const API_BASE = window.API_BASE || "http://localhost:8000/api";

// Helper function for authenticated fetch calls
const authFetch = (url, options = {}) => {
    const token = localStorage.getItem('token');
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
};

// Configure axios to include auth token in all requests
axios.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers = config.headers || {};
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// --- Trading Calendar Utilities ---
// US Market Holidays (NYSE/NASDAQ) - Updated annually
// Format: 'YYYY-MM-DD'
const US_MARKET_HOLIDAYS = new Set([
    // 2025
    '2025-01-01', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26',
    '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27', '2025-12-25',
    // 2026
    '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
    '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
]);

/**
 * Calculate trading days between two dates (excludes weekends and US holidays)
 * @param {Date|string} startDate - Start date
 * @param {Date|string} endDate - End date (defaults to today)
 * @returns {number} Number of trading days
 */
function getTradingDaysBetween(startDate, endDate = new Date()) {
    const parseLocal = (d) => {
        if (typeof d === 'string' && d.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const [y, m, day] = d.split('-').map(Number);
            return new Date(y, m - 1, day);
        }
        return new Date(d);
    };

    const start = parseLocal(startDate);
    const end = parseLocal(endDate);

    if (isNaN(start.getTime()) || start > end) return 0; // Fixed condition start > end because same day is valid

    let tradingDays = 0;
    const current = new Date(start);
    current.setHours(0, 0, 0, 0);
    end.setHours(0, 0, 0, 0);

    // If same date, it's Day 1
    if (current.getTime() === end.getTime()) return 1;

    while (current <= end) {
        const dayOfWeek = current.getDay();
        const dateStr = current.getFullYear() + '-' + String(current.getMonth() + 1).padStart(2, '0') + '-' + String(current.getDate()).padStart(2, '0');

        // Skip weekends (0 = Sunday, 6 = Saturday)
        // Skip US market holidays
        if (dayOfWeek !== 0 && dayOfWeek !== 6 && !US_MARKET_HOLIDAYS.has(dateStr)) {
            tradingDays++;
        }

        current.setDate(current.getDate() + 1);
    }

    // Safety check: if today is start date, ensure at least 1 (though logic above covers it)
    return tradingDays > 0 ? tradingDays : 1;
}

// --- Components ---

function EquityChart({ data }) {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);

    useEffect(() => {
        if (!chartContainerRef.current || !data || data.length === 0) return;

        const chart = LightweightCharts.createChart(chartContainerRef.current, {
            layout: {
                background: { color: '#1e293b' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: '#334155' },
                horzLines: { color: '#334155' },
            },
            rightPriceScale: {
                borderColor: '#475569',
            },
            timeScale: {
                borderColor: '#475569',
                timeVisible: true,
            },
            height: 300,
        });

        const areaSeries = chart.addAreaSeries({
            topColor: 'rgba(34, 197, 94, 0.56)',
            bottomColor: 'rgba(34, 197, 94, 0.04)',
            lineColor: 'rgba(34, 197, 94, 1)',
            lineWidth: 2,
        });

        // Zip dates and equity values
        const chartData = data.dates.map((date, i) => ({
            time: date,
            value: data.equity[i]
        }));

        areaSeries.setData(chartData);
        chart.timeScale().fitContent();

        chartRef.current = chart;

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                });
            }
        };

        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        }
    }, [data]);

    return <div ref={chartContainerRef} className="w-full h-72" />;
}

// 1. Sector Allocation Chart (Horizontal Bars)
function SectorAllocationChart({ data }) {
    if (!data || data.length === 0) return null;
    const maxVal = Math.max(...data.map(d => d.value));

    return (
        <div className="bg-slate-800/50 p-6 rounded-xl border border-slate-700 h-full">
            <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-6 flex items-center gap-2">
                <span>📊</span> Sector Allocation
            </h3>
            <div className="space-y-4">
                {data.map((item, i) => (
                    <div key={i} className="group">
                        <div className="flex justify-between text-xs mb-1.5">
                            <span className="text-slate-300 font-medium group-hover:text-white transition">{item.sector}</span>
                            <span className="text-slate-500 font-mono">${item.value.toLocaleString()}</span>
                        </div>
                        <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden border border-slate-700/50">
                            <div
                                className="h-full bg-gradient-to-r from-blue-600 to-indigo-500 shadow-[0_0_10px_rgba(37,99,235,0.3)] transition-all duration-1000 ease-out"
                                style={{ width: `${(item.value / maxVal) * 100}%` }}
                            ></div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// 2. Portfolio Benchmark Chart (Line vs Monthly Comparison)
function PortfolioBenchmarkChart({ performanceData }) {
    const [viewMode, setViewMode] = useState('line'); // 'line' or 'bar'
    const [valueMode, setValueMode] = useState('percent'); // 'percent' or 'dollar'
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Cell, PieChart, Pie } = Recharts;

    useEffect(() => {
        if (viewMode === 'bar' || !chartContainerRef.current || !performanceData || !performanceData.line_data) return;
        if (!performanceData.line_data.dates || !performanceData.line_data.portfolio) return;

        const chart = LightweightCharts.createChart(chartContainerRef.current, {
            layout: { background: { color: 'transparent' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
            rightPriceScale: { borderColor: '#475569', scaleMargins: { top: 0.1, bottom: 0.1 } },
            timeScale: { borderColor: '#475569', timeVisible: true },
            height: 350,
        });

        const portfolioSeries = chart.addLineSeries({
            color: '#3b82f6',
            lineWidth: 3,
            title: 'PORTFOLIO'
        });

        const spySeries = chart.addLineSeries({
            color: '#d946ef',
            lineWidth: 2,
            lineStyle: 2,
            title: 'S&P 500'
        });

        const lineData = performanceData.line_data;

        // Calculate data based on valueMode
        let pValues = lineData.portfolio || [];
        let sValues = lineData.spy || [];

        if (valueMode === 'dollar' && lineData.portfolio_dollar) {
            pValues = lineData.portfolio_dollar;
        }
        if (valueMode === 'dollar' && lineData.spy_dollar) {
            sValues = lineData.spy_dollar;
        }

        const pData = lineData.dates.map((date, i) => ({
            time: date,
            value: pValues[i] || 0
        }));
        const sData = lineData.dates.map((date, i) => ({
            time: date,
            value: sValues[i] || 0
        }));

        portfolioSeries.setData(pData);
        spySeries.setData(sData);

        // Add Floating Labels at the end of the lines
        if (pData.length > 0) {
            const lastP = pData[pData.length - 1];
            if (lastP && lastP.value !== undefined && lastP.value !== null) {
                const labelText = valueMode === 'percent'
                    ? `${lastP.value >= 0 ? '+' : ''}${(lastP.value || 0).toFixed(2)}%`
                    : `$${(lastP.value || 0).toLocaleString()}`;
                portfolioSeries.createPriceLine({
                    price: lastP.value,
                    color: '#3b82f6',
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: labelText,
                });
            }
        }
        if (sData.length > 0) {
            const lastS = sData[sData.length - 1];
            if (lastS && lastS.value !== undefined && lastS.value !== null) {
                const labelText = valueMode === 'percent'
                    ? `${lastS.value >= 0 ? '+' : ''}${(lastS.value || 0).toFixed(2)}%`
                    : `$${(lastS.value || 0).toLocaleString()}`;
                spySeries.createPriceLine({
                    price: lastS.value,
                    color: '#d946ef',
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: labelText,
                });
            }
        }

        chart.timeScale().fitContent();
        chartRef.current = chart;

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);
        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        }
    }, [viewMode, valueMode, performanceData]);

    return (
        <div className="bg-slate-800/40 p-6 rounded-2xl border border-slate-700 shadow-2xl backdrop-blur-sm">
            <div className="flex flex-col gap-3 mb-6">
                <div className="flex justify-between items-center">
                    <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                        <span className="text-lg">📈</span> Performance vs Benchmark
                    </h3>
                    <div className="flex items-center gap-2">
                        {/* Dollar/Percent Toggle */}
                        <div className="flex items-center gap-1 bg-slate-900/50 p-1 rounded-lg border border-slate-700">
                            <button
                                onClick={() => setValueMode('percent')}
                                className={`px-2 py-1 rounded-md text-[10px] font-bold transition ${valueMode === 'percent' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                📈 %
                            </button>
                            <button
                                onClick={() => setValueMode('dollar')}
                                className={`px-2 py-1 rounded-md text-[10px] font-bold transition ${valueMode === 'dollar' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                💵 $
                            </button>
                        </div>
                        {/* Line/Bar Toggle */}
                        <div className="flex items-center gap-1 bg-slate-900/50 p-1 rounded-lg border border-slate-700">
                            <button
                                onClick={() => setViewMode('line')}
                                className={`px-2 py-1 rounded-md text-[10px] font-bold transition flex items-center gap-1 ${viewMode === 'line' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                📉 LINE
                            </button>
                            <button
                                onClick={() => setViewMode('bar')}
                                className={`px-2 py-1 rounded-md text-[10px] font-bold transition flex items-center gap-1 ${viewMode === 'bar' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                📊 BARS
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {viewMode === 'line' ? (
                <div ref={chartContainerRef} className="w-full" />
            ) : (
                <div className="w-full">
                    {performanceData?.monthly_data && performanceData.monthly_data.length > 0 ? (
                        <>
                            <div className="h-[350px]">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={performanceData.monthly_data}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} opacity={0.3} />
                                        <XAxis dataKey="month" stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} />
                                        <YAxis stroke="#64748b" fontSize={10} axisLine={false} tickLine={false} tickFormatter={(val) => `${val}%`} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#000', borderColor: '#334155', borderRadius: '12px', padding: '10px' }}
                                            itemStyle={{ fontSize: '11px', fontWeight: 'bold' }}
                                            cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                        />
                                        <Legend verticalAlign="top" align="right" wrapperStyle={{ fontSize: '10px', paddingBottom: '20px' }} />
                                        <Bar dataKey="portfolio" name="My Portfolio" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="spy" name="S&P 500" fill="#d946ef" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Detailed Data Table (Matched to TipRanks reference) */}
                            <div className="mt-6 overflow-x-auto border border-slate-700/50 rounded-xl bg-black/20 p-4">
                                <table className="w-full text-[10px] border-collapse min-w-[600px]">
                                    <thead>
                                        <tr>
                                            <th className="p-2 text-left border-b border-slate-700 text-slate-500 uppercase tracking-tighter">Metric</th>
                                            {performanceData.monthly_data.map((m, idx) => (
                                                <th key={idx} className="p-2 text-center border-b border-slate-700 text-slate-400 font-medium">{m.month}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {/* S&P 500 Row */}
                                        <tr>
                                            <td className="p-3 flex items-center gap-2 border-b border-white/5 whitespace-nowrap">
                                                <div className="w-2.5 h-2.5 rounded-sm bg-[#d946ef]"></div>
                                                <span className="font-bold text-slate-300">S&P 500</span>
                                            </td>
                                            {performanceData.monthly_data.map((m, idx) => (
                                                <td key={idx} className={`p-3 text-center font-mono border-b border-white/5 ${(m.spy || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                                    <span className="mr-1">{(m.spy || 0) >= 0 ? '▲' : '▼'}</span>
                                                    {Math.abs(m.spy || 0).toFixed(2)}%
                                                </td>
                                            ))}
                                        </tr>
                                        {/* Portfolio Row */}
                                        <tr>
                                            <td className="p-3 flex items-center gap-2 border-b border-white/5 whitespace-nowrap">
                                                <div className="w-2.5 h-2.5 rounded-sm bg-[#3b82f6]"></div>
                                                <span className="font-bold text-slate-300">My Portfolio</span>
                                            </td>
                                            {performanceData.monthly_data.map((m, idx) => (
                                                <td key={idx} className={`p-3 text-center font-mono border-b border-white/5 ${(m.portfolio || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                                    <span className="mr-1">{(m.portfolio || 0) >= 0 ? '▲' : '▼'}</span>
                                                    {Math.abs(m.portfolio || 0).toFixed(2)}%
                                                </td>
                                            ))}
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </>
                    ) : (
                        <div className="h-[350px] flex items-center justify-center text-slate-500 italic">
                            No monthly data available. Close some trades to see performance.
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// 3. Risk-o-meter Gauge
function RiskGauge({ riskAmount, totalCapital }) {
    const riskPct = totalCapital > 0 ? (riskAmount / totalCapital) * 100 : 0;
    const isSafe = riskPct <= 1.0;
    const isHigh = riskPct > 2.0;

    return (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 shadow-lg flex flex-col items-center justify-center relative overflow-hidden">
            <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 font-bold">Risk Exposure</div>
            <div className={`text-2xl font-black ${isSafe ? 'text-green-400' : (isHigh ? 'text-red-400' : 'text-yellow-400')}`}>
                {riskPct.toFixed(1)}%
            </div>
            <div className="text-[9px] text-slate-500 mt-1">Total At Risk: ${riskAmount.toLocaleString()}</div>

            <div className="w-full h-1.5 bg-slate-900 rounded-full mt-3 overflow-hidden">
                <div
                    className={`h-full transition-all duration-1000 ${isSafe ? 'bg-green-500' : (isHigh ? 'bg-red-500' : 'bg-yellow-500')}`}
                    style={{ width: `${Math.min(riskPct * 20, 100)}%` }}
                ></div>
            </div>
        </div>
    );
}

// 4. Historical Portfolio Analytics (Snapshots)
function PortfolioHistoryChart({ data }) {
    const [plViewMode, setPlViewMode] = useState('dollar'); // 'dollar' or 'percent'
    const [timeframe, setTimeframe] = useState('1M'); // '1D', '1W', '1M', 'YTD', '1Y', 'Max'

    if (!data || data.length < 2) {
        return (
            <div className="bg-slate-800 rounded-xl border border-slate-700 p-8 flex flex-col items-center justify-center text-center opacity-60 h-full">
                <span className="text-3xl mb-2">📊</span>
                <div className="text-sm font-bold text-slate-400">Historical Data Pending</div>
                <div className="text-[10px] text-slate-500 max-w-[200px]">Recording usually begins after your first daily snapshot. Check back tomorrow!</div>
            </div>
        );
    }

    const {
        ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip,
        CartesianGrid, BarChart, Bar, Cell, ReferenceLine
    } = Recharts;

    // Filter data by timeframe
    const filterByTimeframe = (inputData) => {
        const now = new Date();
        let cutoffDate = new Date(0); // Default to include all

        switch (timeframe) {
            case '1D':
                cutoffDate = new Date(now);
                cutoffDate.setDate(cutoffDate.getDate() - 1);
                break;
            case '1W':
                cutoffDate = new Date(now);
                cutoffDate.setDate(cutoffDate.getDate() - 7);
                break;
            case '1M':
                cutoffDate = new Date(now);
                cutoffDate.setMonth(cutoffDate.getMonth() - 1);
                break;
            case 'YTD':
                cutoffDate = new Date(now.getFullYear(), 0, 1);
                break;
            case '1Y':
                cutoffDate = new Date(now);
                cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
                break;
            case 'Max':
            default:
                cutoffDate = new Date(0);
        }

        return inputData.filter(d => {
            const itemDate = new Date(d.date);
            return itemDate >= cutoffDate;
        });
    };

    const filteredData = filterByTimeframe(data);

    const processed = filteredData.map((d, i) => {
        const prev = i > 0 ? filteredData[i - 1] : d;
        const equity = d.total_equity || d.total_value_usd || 0;
        const prevEquity = prev.total_equity || prev.total_value_usd || 0;
        const dailyChange = equity - prevEquity;
        const dailyChangePct = prevEquity > 0 ? (dailyChange / prevEquity) * 100 : 0;

        // Use 'date' field from backend (not snapshot_date)
        const dateStr = d.date || '';
        let displayDate = 'N/A';
        try {
            const dateObj = new Date(dateStr);
            if (!isNaN(dateObj.getTime())) {
                displayDate = dateObj.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
            }
        } catch (e) { }

        return {
            ...d,
            total_equity: equity,
            dailyChange,
            dailyChangePct,
            displayDate
        };
    });

    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            const entry = processed.find(p => p.displayDate === label);
            return (
                <div className="bg-slate-900 border border-slate-700 p-3 rounded-lg shadow-2xl backdrop-blur-md">
                    <p className="text-slate-400 text-[10px] uppercase font-bold mb-1">{label}</p>
                    <p className="text-white font-bold text-sm">
                        ${entry?.total_equity?.toLocaleString() || 0} <span className="text-slate-500 text-[10px]">Total</span>
                    </p>
                    <p className={`text-xs mt-1 ${entry?.dailyChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {entry?.dailyChange >= 0 ? '▲' : '▼'} ${Math.abs(entry?.dailyChange || 0).toFixed(2)}
                        <span className="ml-1">({entry?.dailyChangePct?.toFixed(2) || 0}%)</span>
                    </p>
                </div>
            );
        }
        return null;
    };

    // Current dataKey and formatter based on mode
    const dataKey = plViewMode === 'dollar' ? 'dailyChange' : 'dailyChangePct';
    const yAxisFormatter = plViewMode === 'dollar'
        ? (val) => `$${val.toLocaleString()}`
        : (val) => `${val.toFixed(1)}%`;

    return (
        <div className="space-y-6">
            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 shadow-xl">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-slate-300 font-bold text-xs uppercase tracking-wider flex items-center gap-2">
                        <span>📈 Equity Growth</span>
                        <span className="text-[9px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">HISTORY</span>
                    </h3>
                </div>
                <div className="h-[180px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={processed}>
                            <defs>
                                <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} opacity={0.3} />
                            <XAxis dataKey="displayDate" stroke="#64748b" fontSize={9} tickLine={false} axisLine={false} minTickGap={30} />
                            <YAxis hide domain={['dataMin - 1000', 'dataMax + 1000']} />
                            <Tooltip content={<CustomTooltip />} />
                            <Area type="monotone" dataKey="total_equity" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorEquity)" animationDuration={1000} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-5 shadow-xl">
                <div className="flex flex-col gap-3 mb-4">
                    <div className="flex justify-between items-center">
                        <h3 className="text-slate-300 font-bold text-xs uppercase tracking-wider flex items-center gap-2">
                            <span>📊 P&L</span>
                        </h3>
                        {/* Dollar/Percent Toggle */}
                        <div className="flex items-center gap-1 bg-slate-900/50 p-1 rounded-lg border border-slate-700">
                            <button
                                onClick={() => setPlViewMode('dollar')}
                                className={`px-2.5 py-1 rounded-md text-[10px] font-bold transition ${plViewMode === 'dollar' ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                💵 $
                            </button>
                            <button
                                onClick={() => setPlViewMode('percent')}
                                className={`px-2.5 py-1 rounded-md text-[10px] font-bold transition ${plViewMode === 'percent' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                            >
                                📈 %
                            </button>
                        </div>
                    </div>
                    {/* Timeframe Toggle */}
                    <div className="flex justify-center gap-1">
                        {['1D', '1W', '1M', 'YTD', '1Y', 'Max'].map(tf => (
                            <button
                                key={tf}
                                onClick={() => setTimeframe(tf)}
                                className={`px-2 py-1 rounded-md text-[9px] font-bold transition ${timeframe === tf ? 'bg-blue-600 text-white' : 'bg-[#1a1a1a] text-slate-400 hover:text-white border border-[#2a2a2a]'}`}
                            >
                                {tf}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="h-[130px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={processed} margin={{ top: 20, right: 10, left: 10, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} opacity={0.3} />
                            <XAxis dataKey="displayDate" stroke="#64748b" fontSize={8} tickLine={false} axisLine={false} minTickGap={20} />
                            <YAxis stroke="#64748b" fontSize={8} tickLine={false} axisLine={false} tickFormatter={yAxisFormatter} />
                            <Tooltip content={<CustomTooltip />} />
                            <ReferenceLine y={0} stroke="#475569" strokeWidth={2} />
                            <Bar dataKey={dataKey} radius={[3, 3, 0, 0]}>
                                {processed.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.dailyChange >= 0 ? '#10b981' : '#ef4444'} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
                {/* Summary Stats */}
                <div className="flex gap-4 mt-3 pt-3 border-t border-slate-700/50">
                    {(() => {
                        const lastDay = processed[processed.length - 1];
                        const totalChange = processed.reduce((sum, d) => sum + d.dailyChange, 0);
                        const totalPctChange = processed.reduce((sum, d) => sum + d.dailyChangePct, 0);
                        const initialEquity = processed[0]?.total_equity || 1;
                        const finalEquity = lastDay?.total_equity || 1;
                        const overallPctChange = ((finalEquity - initialEquity) / initialEquity) * 100;

                        return (
                            <>
                                <div className="flex-1 text-center">
                                    <div className="text-[9px] text-slate-500 uppercase font-bold">Last Day</div>
                                    <div className={`font-bold font-mono text-sm ${lastDay?.dailyChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {plViewMode === 'dollar' ? (
                                            <>{lastDay?.dailyChange >= 0 ? '+' : ''}${lastDay?.dailyChange?.toFixed(2) || '0'}</>
                                        ) : (
                                            <>{lastDay?.dailyChangePct >= 0 ? '+' : ''}{lastDay?.dailyChangePct?.toFixed(2) || '0'}%</>
                                        )}
                                    </div>
                                </div>
                                <div className="flex-1 text-center border-l border-slate-700/50">
                                    <div className="text-[9px] text-slate-500 uppercase font-bold">Period Total</div>
                                    <div className={`font-bold font-mono text-sm ${totalChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {plViewMode === 'dollar' ? (
                                            <>{totalChange >= 0 ? '+' : ''}${totalChange.toFixed(2)}</>
                                        ) : (
                                            <>{overallPctChange >= 0 ? '+' : ''}{overallPctChange.toFixed(2)}%</>
                                        )}
                                    </div>
                                </div>
                            </>
                        );
                    })()}
                </div>
            </div>
        </div>
    );
}


// --- Analytics Component ---
function JournalAnalytics({ equityData, calendarData }) {
    if (!calendarData) return <div className="text-slate-500 italic text-center p-8">Loading Analytics...</div>;

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Equity Curve Reuse */}
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg">
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-4">Equity Growth</h3>
                {equityData && equityData.dates.length > 0 ? (
                    <EquityChart data={equityData} />
                ) : (
                    <div className="text-slate-500 italic text-center py-12">No closed trades to plot.</div>
                )}
            </div>

            {/* Calendar Heatmap */}
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 shadow-lg">
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-4">Trading Calendar</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-7 gap-3">
                    {calendarData.length === 0 ? (
                        <div className="col-span-full text-center text-slate-500 italic py-8">No trading history available.</div>
                    ) : calendarData.map((day) => (
                        <div key={day.date} className="bg-slate-900/50 border border-slate-700/50 p-3 rounded-lg flex flex-col items-center hover:bg-slate-800 transition">
                            <span className="text-[10px] text-slate-500 mb-1 font-mono">{day.date}</span>
                            <span className={`text-base font-bold font-mono ${day.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {day.pnl >= 0 ? '+' : ''}{day.pnl}
                            </span>
                            <div className="mt-1 flex gap-1 items-center">
                                <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 rounded">{day.count} trds</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

// Form to Log New Trades
// Form to Log New Trades
function TradeForm({ onSave, onCancel }) {
    const [formData, setFormData] = useState({
        ticker: '',
        direction: 'BUY', // Using 'direction' as the field name to match backend input model, but UI will show "Action"
        entry_date: new Date().toISOString().split('T')[0],
        entry_price: '',
        shares: '',
        stop_loss: '',
        target: '',
        target2: '',
        target3: '',
        strategy: '', // NEW: Strategy field
        status: 'OPEN',
        exit_date: '',
        exit_price: '',
        notes: ''
    });

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        const payload = {
            ...formData,
            entry_price: parseFloat(formData.entry_price),
            shares: parseInt(formData.shares),
            stop_loss: formData.stop_loss ? parseFloat(formData.stop_loss) : null,
            target: formData.target ? parseFloat(formData.target) : null,
            target2: formData.target2 ? parseFloat(formData.target2) : null,
            target3: formData.target3 ? parseFloat(formData.target3) : null,
            strategy: formData.strategy || null, // NEW: Strategy field
            exit_price: formData.exit_price ? parseFloat(formData.exit_price) : null,
        };

        try {
            await axios.post(`${API_BASE}/trades/add`, payload);
            if (onSave) onSave();
        } catch (err) {
            console.error(err);
            alert("Error saving trade: " + (err.response?.data?.detail || err.message));
        }
    };

    const isSell = formData.direction === 'SELL';

    return (
        <div className="bg-slate-800 p-6 rounded-lg border border-slate-700 mb-6">
            <h3 className="text-xl font-bold mb-4 text-white">Log Transaction</h3>
            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label className="block text-xs text-slate-400 mb-1">Ticker</label>
                    <input required name="ticker" value={formData.ticker} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white uppercase" />
                </div>
                <div>
                    <label className="block text-xs text-slate-400 mb-1">Action</label>
                    <select name="direction" value={formData.direction} onChange={handleChange} className={`w-full border border-slate-700 rounded p-2 text-white font-bold ${isSell ? 'bg-red-900/50' : 'bg-green-900/50'}`}>
                        <option value="BUY">BUY</option>
                        <option value="SELL">SELL</option>
                    </select>
                </div>
                <div>
                    <label className="block text-xs text-slate-400 mb-1">Date</label>
                    <input required type="date" name="entry_date" value={formData.entry_date} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                </div>
                <div>
                    <label className="block text-xs text-slate-400 mb-1">Shares</label>
                    <input required type="number" name="shares" value={formData.shares} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                </div>
                <div>
                    <label className="block text-xs text-slate-400 mb-1">{isSell ? 'Sale Price ($)' : 'Entry Price ($)'}</label>
                    <input required type="number" step="0.01" name="entry_price" value={formData.entry_price} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                </div>

                {/* Optional fields only for BUY */}
                {!isSell && (
                    <>
                        <div>
                            <label className="block text-xs text-slate-400 mb-1">Stop Loss ($)</label>
                            <input type="number" step="0.01" name="stop_loss" value={formData.stop_loss} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                        </div>
                        <div>
                            <label className="block text-xs text-slate-400 mb-1">Target 1 ($)</label>
                            <input type="number" step="0.01" name="target" value={formData.target} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                        </div>
                        <div>
                            <label className="block text-xs text-slate-400 mb-1">Target 2 ($)</label>
                            <input type="number" step="0.01" name="target2" value={formData.target2} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                        </div>
                        <div>
                            <label className="block text-xs text-slate-400 mb-1">Target 3 ($)</label>
                            <input type="number" step="0.01" name="target3" value={formData.target3} onChange={handleChange} className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                        </div>
                        <div>
                            <label className="block text-xs text-slate-400 mb-1">Strategy</label>
                            <input type="text" name="strategy" value={formData.strategy} onChange={handleChange} placeholder="e.g. Color Bull Flag" className="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white" />
                        </div>
                    </>
                )}

                <div className="col-span-full flex justify-end gap-3 mt-4">
                    <button type="button" onClick={onCancel} className="px-4 py-2 rounded text-slate-300 hover:text-white transition">Cancel</button>
                    <button type="submit" className={`px-6 py-2 text-white rounded font-medium transition ${isSell ? 'bg-red-600 hover:bg-red-500' : 'bg-blue-600 hover:bg-blue-500'}`}>
                        {isSell ? 'Confirm Sell' : 'Log Buy'}
                    </button>
                </div>
            </form>
        </div>
    )
}
// Main Trade Journal Component
// --- Specialized Analytics Components (TipRanks Style) ---

function AnalyticsCard({ title, children, icon }) {
    return (
        <div className="bg-slate-800/40 rounded-2xl border border-slate-700/50 shadow-2xl backdrop-blur-sm p-5 flex flex-col h-full hover:border-slate-600/50 transition-colors">
            <div className="flex justify-between items-center mb-4 border-b border-slate-700/30 pb-3">
                <h3 className="text-slate-300 text-[11px] font-black uppercase tracking-widest flex items-center gap-2">
                    <span className="text-lg opacity-80">{icon}</span> {title}
                </h3>
                <div className="flex items-center gap-2">
                    <span className="text-slate-500 text-[10px] cursor-help hover:text-slate-300 transition-colors">ⓘ</span>
                </div>
            </div>
            <div className="flex-grow">{children}</div>
        </div>
    );
}

function DonutSummary({ data, dataKey, nameKey, colors, centerText, subCenterText }) {
    const { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } = Recharts;

    if (!data || data.length === 0) return (
        <div className="flex items-center justify-center h-[180px] text-slate-600 text-[10px] italic">
            Insufficient data for analysis
        </div>
    );

    const total = data.reduce((a, b) => a + (b[dataKey] || 0), 0);

    return (
        <div className="flex items-center gap-6 h-[180px]">
            <div className="w-1/2 h-full relative">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={data}
                            innerRadius={55}
                            outerRadius={75}
                            paddingAngle={5}
                            dataKey={dataKey}
                            stroke="none"
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', fontSize: '10px', color: '#fff' }}
                            itemStyle={{ color: '#fff' }}
                        />
                    </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-white text-lg font-black">{centerText}</span>
                    <span className="text-slate-500 text-[9px] uppercase font-bold tracking-tighter">{subCenterText}</span>
                </div>
            </div>
            <div className="w-1/2 flex flex-col gap-2 overflow-y-auto max-h-[160px] pr-2 custom-scrollbar">
                {data.map((item, idx) => {
                    const pct = item.pct ? item.pct : (total > 0 ? ((item[dataKey] / total) * 100).toFixed(1) : 0);
                    return (
                        <div key={idx} className="flex items-center justify-between text-[10px]">
                            <div className="flex items-center gap-2 truncate">
                                <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: colors[idx % colors.length] }}></div>
                                <span className="text-slate-400 font-medium truncate">{item[nameKey]}</span>
                            </div>
                            <span className="text-slate-200 font-bold shrink-0">{pct}%</span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

// --- Portfolio News Widget (fetches and displays news for holdings) ---
function PortfolioNewsWidget({ tickers }) {
    const [newsItems, setNewsItems] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!tickers || tickers.length === 0) return;

        setLoading(true);
        axios.get(`${API_BASE}/news/portfolio?tickers=${tickers.join(',')}`)
            .then(res => {
                setNewsItems(res.data || []);
                setLoading(false);
            })
            .catch(err => {
                console.error('Error fetching portfolio news:', err);
                setLoading(false);
            });
    }, [tickers.join(',')]);

    const formatTimeAgo = (timestamp) => {
        if (!timestamp) return '';
        const diff = (Date.now() / 1000) - timestamp;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return `${Math.floor(diff / 86400)}d ago`;
    };

    return (
        <div className="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden shadow-2xl backdrop-blur-sm">
            <div className="p-4 border-b border-slate-700 bg-slate-900/50 flex items-center gap-3">
                <span className="text-xl">📰</span>
                <h3 className="text-slate-300 font-bold text-sm uppercase tracking-widest">Portfolio News</h3>
            </div>
            <div className="p-3 max-h-[300px] overflow-y-auto">
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-slate-500">
                        <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full mr-2"></div>
                        Loading news...
                    </div>
                ) : newsItems.length > 0 ? (
                    <div className="space-y-3">
                        {newsItems.map((item, i) => (
                            <a
                                key={i}
                                href={item.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="block p-3 rounded-xl hover:bg-slate-700/50 transition border border-transparent hover:border-slate-600/50"
                            >
                                <div className="flex items-start gap-2 mb-1.5">
                                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase shrink-0 ${item.sentiment === 'bullish' ? 'bg-green-500/20 text-green-400' :
                                        (item.sentiment === 'bearish' ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-400')
                                        }`}>
                                        {item.ticker}
                                    </span>
                                    <span className="text-[10px] text-slate-500">{formatTimeAgo(item.datetime)}</span>
                                </div>
                                <div className="text-xs text-slate-300 leading-tight line-clamp-2">{item.headline}</div>
                                <div className="text-[10px] text-slate-500 mt-1 truncate">{item.source}</div>
                            </a>
                        ))}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center py-8 opacity-40">
                        <span className="text-3xl mb-2">📭</span>
                        <div className="text-xs text-slate-500">No recent news for your holdings</div>
                    </div>
                )}
            </div>
        </div>
    );
}

// --- Open Positions Analytics Component / Portfolio Dashboard ---
function PerformanceDashboard({ data, performanceData, snapshotData }) {
    if (!data) return <div className="p-8 text-center text-slate-500 italic font-mono">📡 SIGNAL SEARCHING...</div>;

    const { exposure, asset_allocation, sector_allocation, holdings, upcoming_dividends, suggestions } = data;
    const latestEquity = snapshotData && snapshotData.length > 0 ? snapshotData[snapshotData.length - 1].total_equity : 0;

    const ALLOCATION_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#6366f1', '#ec4899', '#8b5cf6'];
    const SECTOR_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#3b82f6', '#ec4899', '#94a3b8'];

    return (
        <div className="space-y-8 animate-fade-in mb-8">
            {/* Row 1: Allocation & Distribution */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {/* 1. Asset Allocation */}
                <AnalyticsCard title="Asset Allocation" icon="🥧">
                    <DonutSummary
                        data={asset_allocation || []}
                        dataKey="value"
                        nameKey="type"
                        colors={ALLOCATION_COLORS}
                        centerText="My Assets"
                        subCenterText="Value"
                    />
                </AnalyticsCard>

                {/* 2. Holdings Distribution */}
                <AnalyticsCard title="Holdings Distribution" icon="🌐">
                    <div className="flex flex-col lg:flex-row gap-6">
                        <div className="w-full lg:w-1/2">
                            <DonutSummary
                                data={sector_allocation?.slice(0, 6) || []}
                                dataKey="value"
                                nameKey="sector"
                                colors={SECTOR_COLORS}
                                centerText={exposure?.active_count || 0}
                                subCenterText="Holdings"
                            />
                        </div>
                        <div className="w-full lg:w-1/2">
                            <div className="text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-tighter">Major Holdings</div>
                            <div className="space-y-2 max-h-[140px] overflow-y-auto pr-1">
                                {holdings && holdings.length > 0 ? holdings.slice(0, 5).map((h, i) => (
                                    <div key={i} className="flex justify-between items-center border-b border-slate-700/20 pb-1.5 last:border-0 hover:bg-white/5 transition-colors p-1 rounded">
                                        <div className="flex flex-col max-w-[120px]">
                                            <span className="text-[10px] text-white font-bold truncate">{h.name} <span className="text-blue-400 font-mono text-[9px]">({h.ticker})</span></span>
                                        </div>
                                        <span className="text-[10px] text-slate-300 font-mono font-bold">{h.pct}%</span>
                                    </div>
                                )) : <div className="text-slate-600 text-[10px] italic py-4">No open positions</div>}
                            </div>
                        </div>
                    </div>
                </AnalyticsCard>
            </div>

            {/* Row 2: Volatility & P/E */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 3. Portfolio Volatility (Beta) */}
                <AnalyticsCard title="Portfolio Volatility" icon="⚡">
                    <div className="flex flex-col gap-6">
                        <div className="flex items-baseline gap-3">
                            <span className="text-5xl font-black text-white">{exposure?.portfolio_beta || '0.00'}</span>
                            <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">My Risk (Beta)</span>
                        </div>
                        <div className="relative pt-4 pb-4 px-2">
                            <div className="flex justify-between text-[9px] text-slate-500 uppercase font-black mb-2">
                                <span>Low Risk</span>
                                <span>High Risk</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-700/30 rounded-full overflow-hidden flex">
                                {Array.from({ length: 10 }).map((_, i) => (
                                    <div key={i} className={`h-full flex-grow border-r border-slate-900/50 ${i < 3 ? 'bg-blue-500' : (i < 7 ? 'bg-indigo-500' : 'bg-pink-500')}`} style={{ opacity: 0.3 + (i * 0.07) }}></div>
                                ))}
                            </div>
                            <div className="absolute top-[34px] transition-all duration-1000" style={{ left: `${Math.max(2, Math.min((exposure?.portfolio_beta || 0) * 33, 95))}%` }}>
                                <div className="w-4 h-4 bg-white rounded-full border-[3px] border-slate-900 shadow-xl -translate-x-1/2 relative z-10">
                                    <div className="absolute top-5 left-1/2 -translate-x-1/2 text-[8px] font-black text-white whitespace-nowrap bg-indigo-600 px-2 py-0.5 rounded-full uppercase shadow-lg border border-white/20">My Portfolio</div>
                                </div>
                            </div>
                        </div>
                        <div className="mt-4 bg-black/10 rounded-xl p-3">
                            <div className="flex justify-between text-[9px] text-slate-500 border-b border-slate-700/30 pb-1.5 mb-2 uppercase font-black">
                                <span>My Highest Risk Stocks</span>
                                <span className="font-mono">Beta</span>
                            </div>
                            <div className="space-y-2">
                                {holdings?.filter(h => h.beta).sort((a, b) => b.beta - a.beta).slice(0, 3).map((h, i) => (
                                    <div key={i} className="flex justify-between items-center text-[10px]">
                                        <span className="text-slate-200 font-bold truncate max-w-[150px]">{h.name} <span className="text-blue-400 font-mono text-[9px]">({h.ticker})</span></span>
                                        <span className="text-pink-400 font-mono font-bold bg-pink-400/10 px-1.5 py-0.5 rounded">{h.beta.toFixed(2)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </AnalyticsCard>

                {/* 4. Portfolio P/E */}
                <AnalyticsCard title="Portfolio P/E" icon="💹">
                    <div className="flex flex-col gap-6">
                        <div className="flex items-baseline gap-3">
                            <span className="text-5xl font-black text-white">{exposure?.portfolio_pe || '0.0'}</span>
                            <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">My Portfolio P/E Ratio</span>
                        </div>
                        <div className="relative pt-4 pb-4 px-2">
                            <div className="flex justify-between text-[9px] text-slate-500 uppercase font-black mb-2">
                                <span>0</span>
                                <span>100+</span>
                            </div>
                            <div className="h-1.5 w-full bg-slate-700/30 rounded-full overflow-hidden flex">
                                {Array.from({ length: 10 }).map((_, i) => (
                                    <div key={i} className="h-full flex-grow border-r border-slate-900/50 bg-blue-500" style={{ opacity: 0.2 + (i * 0.08) }}></div>
                                ))}
                            </div>
                            <div className="absolute top-[34px] transition-all duration-1000" style={{ left: `${Math.max(2, Math.min((exposure?.portfolio_pe || 0), 98))}%` }}>
                                <div className="w-4 h-4 bg-white rounded-full border-[3px] border-slate-900 shadow-xl -translate-x-1/2 relative z-10">
                                    <div className="absolute top-5 left-1/2 -translate-x-1/2 text-[8px] font-black text-white whitespace-nowrap bg-blue-600 px-2 py-0.5 rounded-full uppercase shadow-lg border border-white/20">My Portfolio</div>
                                </div>
                            </div>
                        </div>
                        <div className="mt-4 bg-black/10 rounded-xl p-3">
                            <div className="flex justify-between text-[9px] text-slate-500 border-b border-slate-700/30 pb-1.5 mb-2 uppercase font-black">
                                <span>My Highest P/E Ratio Stocks</span>
                                <span className="font-mono">P/E Ratio</span>
                            </div>
                            <div className="space-y-2">
                                {holdings?.filter(h => h.pe).sort((a, b) => b.pe - a.pe).slice(0, 3).map((h, i) => (
                                    <div key={i} className="flex justify-between items-center text-[10px]">
                                        <span className="text-slate-200 font-bold truncate max-w-[150px]">{h.name} <span className="text-blue-400 font-mono text-[9px]">({h.ticker})</span></span>
                                        <span className="text-indigo-400 font-mono font-bold bg-indigo-400/10 px-1.5 py-0.5 rounded">{h.pe.toFixed(1)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </AnalyticsCard>
            </div>

            {/* Row 3: Dividends & Warnings */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 5. Portfolio Dividends */}
                <AnalyticsCard title="Portfolio Dividends" icon="💰">
                    <div className="flex gap-8 mb-6 bg-black/20 p-4 rounded-2xl border border-slate-700/30">
                        <div className="flex flex-col">
                            <span className="text-4xl font-black text-white">{exposure?.portfolio_div_yield || '0.00'}%</span>
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-tight">Est. Annual Dividend Yield</span>
                        </div>
                        <div className="w-[1px] bg-slate-700/50 my-1"></div>
                        <div className="flex flex-col">
                            <span className="text-4xl font-black text-white">${(exposure?.total_div_payment || 0).toLocaleString()}</span>
                            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-tight">Est. Annual Payment</span>
                        </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="bg-black/10 p-3 rounded-xl">
                            <div className="flex justify-between text-[9px] text-slate-500 border-b border-slate-700/30 pb-1 mb-2 uppercase font-black">
                                <span>Top Yield Holdings</span>
                                <span>Yield</span>
                            </div>
                            <div className="space-y-2">
                                {holdings?.filter(h => h.yield > 0).sort((a, b) => b.yield - a.yield).slice(0, 4).map((h, i) => (
                                    <div key={i} className="flex justify-between items-center text-[10px]">
                                        <span className="text-slate-300 font-bold truncate max-w-[100px]">{h.name}</span>
                                        <span className="text-green-400 font-mono font-bold">{h.yield}%</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="bg-black/10 p-3 rounded-xl">
                            <div className="flex justify-between text-[9px] text-slate-500 border-b border-slate-700/30 pb-1 mb-2 uppercase font-black">
                                <span>Upcoming Ex-Dates</span>
                                <span>Ex-Date</span>
                            </div>
                            <div className="space-y-2">
                                {upcoming_dividends?.length > 0 ? upcoming_dividends.map((d, i) => (
                                    <div key={i} className="flex justify-between items-center text-[10px]">
                                        <span className="text-slate-300 font-bold truncate max-w-[100px]">{d.name}</span>
                                        <span className="text-orange-400 font-mono text-[9px] bg-orange-400/10 px-1.5 py-0.5 rounded">{d.ex_date}</span>
                                    </div>
                                )) : <div className="text-slate-600 text-[10px] italic pt-4 text-center">No upcoming events</div>}
                            </div>
                        </div>
                    </div>
                </AnalyticsCard>

                {/* 6. Portfolio News (replacing Stock Warnings) */}
                <PortfolioNewsWidget tickers={holdings?.map(h => h.ticker) || []} />
            </div>

            {/* 3. Performance & History charts */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-8 space-y-6">
                    <PortfolioBenchmarkChart
                        performanceData={performanceData}
                    />
                    <PortfolioHistoryChart data={snapshotData} />
                </div>

                {/* Strategy Insights */}
                <div className="lg:col-span-4 space-y-6">
                    {suggestions?.length > 0 ? (
                        <div className="bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden shadow-2xl backdrop-blur-sm">
                            <div className="p-5 border-b border-slate-700 bg-slate-900/50 flex items-center gap-3">
                                <span className="text-xl">🧠</span>
                                <h3 className="text-slate-300 font-bold text-sm uppercase tracking-widest">Strategy Engine</h3>
                            </div>
                            <div className="p-3 space-y-1">
                                {suggestions.map((s, i) => (
                                    <div key={i} className="p-4 rounded-xl hover:bg-slate-900/60 transition group border border-transparent hover:border-slate-700/50">
                                        <div className="flex justify-between items-center mb-1.5">
                                            <span className="font-bold font-mono text-white text-lg">{s.ticker}</span>
                                            <span className={`px-2.5 py-1 rounded-lg font-black uppercase text-[10px] tracking-wider ${s.action === 'ADD' ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-100'}`}>
                                                {s.action}
                                            </span>
                                        </div>
                                        <div className="text-xs text-slate-500 italic group-hover:text-slate-400">{s.reason}</div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="bg-slate-800 rounded-2xl border border-slate-700 border-dashed flex flex-col items-center justify-center p-10 text-center opacity-40">
                            <span className="text-5xl mb-4">🔭</span>
                            <div className="text-sm font-bold text-slate-300 mb-1">Scanning Markets</div>
                            <div className="text-[10px] text-slate-500 max-w-[180px]">AI advisor is currently analyzing your open positions for risks or add-on opportunities...</div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function TradeJournal() {
    const [trades, setTrades] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [equityData, setEquityData] = useState(null);
    const [liveData, setLiveData] = useState({});
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [expandedGroups, setExpandedGroups] = useState({});
    const [activeTab, setActiveTab] = useState('active');
    const [activeSubTab, setActiveSubTab] = useState('log'); // 'log' or 'analytics'
    const [rsiColorFilter, setRsiColorFilter] = useState('all'); // 'all', 'green', 'blue', 'yellow', 'orange', 'pink', 'red'
    const [calendarData, setCalendarData] = useState([]);
    const [lastUpdated, setLastUpdated] = useState(null); // Timestamp for live data
    const [premarket, setPremarket] = useState({}); // Pre-market data per ticker
    const [openAnalytics, setOpenAnalytics] = useState(null);
    const [snapshotData, setSnapshotData] = useState([]);
    const [cachedSummary, setCachedSummary] = useState(null); // Instant load from last snapshot
    const [showSplitModal, setShowSplitModal] = useState(false);
    const [splitForm, setSplitForm] = useState({ ticker: '', splitType: 'reverse', ratio: '' });
    const [showAlertModal, setShowAlertModal] = useState(false);
    const [alertSettings, setAlertSettings] = useState({
        telegram_chat_id: '',
        enabled: false,
        notify_sl: true,
        notify_tp: true,
        notify_rsi_sell: true,
        sl_warning_pct: 2.0
    });
    const [showBuyModal, setShowBuyModal] = useState(false);
    const [buyData, setBuyData] = useState({ ticker: '', currentPrice: 0, sharesToBuy: '', buyPrice: '' });
    const [performanceData, setPerformanceData] = useState(null);
    const [marketFilter, setMarketFilter] = useState('all'); // 'all', 'usa', 'argentina'
    const [argentinaTrades, setArgentinaTrades] = useState([]); // Argentina positions (for Portfolio Dashboard)
    const [displayCurrency, setDisplayCurrency] = useState('usd_ccl'); // 'usd_ccl', 'usd_mep', 'usd_oficial', 'ars_ccl'
    const [unifiedMetrics, setUnifiedMetrics] = useState(null); // Multi-currency totals

    // AI Portfolio Analysis
    const [aiInsight, setAiInsight] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);

    const handleAnalyzePortfolio = async () => {
        setAnalyzing(true);
        try {
            const res = await fetch(`${API_BASE}/ai/portfolio-insight`);
            const data = await res.json();
            setAiInsight(data.insight);
        } catch (err) {
            console.error('AI Analysis failed:', err);
            setAiInsight('Error analyzing portfolio. Please try again.');
        }
        setAnalyzing(false);
    };

    // Group trades by ticker (USA only - Argentina has its own journal)
    const groupedTrades = useMemo(() => {
        return trades.reduce((groups, trade) => {
            const ticker = trade.ticker;
            if (!groups[ticker]) groups[ticker] = [];
            groups[ticker].push(trade);
            return groups;
        }, {});
    }, [trades]);


    // Split into Active (holding shares) vs History (fully closed)
    const { activeGroups, historyGroups } = useMemo(() => {
        const active = {};
        const history = {};

        Object.entries(groupedTrades).forEach(([ticker, group]) => {
            // Check if ANY trade in the group is still OPEN
            const hasOpenPositions = group.some(t => t.status === 'OPEN');

            // If any shares remain (Status=OPEN), it's active partial position.
            // Only if ALL are CLOSED does it go to history.
            if (hasOpenPositions) {
                active[ticker] = group;
            } else {
                history[ticker] = group;
            }
        });

        return { activeGroups: active, historyGroups: history };
    }, [groupedTrades]);

    // State for Partial Sell Modal (USA)
    const [showSellModal, setShowSellModal] = useState(false);
    const [sellData, setSellData] = useState({
        ticker: '',
        currentShares: 0,
        currentPrice: 0
    });

    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

    const currentGroups = activeTab === 'active' ? activeGroups : historyGroups;

    const toggleGroup = (ticker) => {
        setExpandedGroups(prev => ({ ...prev, [ticker]: !prev[ticker] }));
    };

    // Calculate Row Stats for Sorting
    const rowStats = useMemo(() => {
        return Object.entries(currentGroups).map(([ticker, groupTrades]) => {
            const live = liveData[ticker] || {};

            let openShares = 0;
            let openCost = 0;
            let totalHistoryShares = 0;
            let totalHistoryCost = 0;
            let totalExitValue = 0;
            let minEntryDate = null;
            let maxExitDate = null;
            let totalPnl = 0;

            groupTrades.forEach(t => {
                const isLong = t.direction === 'LONG';
                totalHistoryShares += t.shares;
                totalHistoryCost += (t.entry_price || 0) * t.shares;

                if (!minEntryDate || new Date(t.entry_date) < new Date(minEntryDate)) {
                    minEntryDate = t.entry_date;
                }

                if (t.status === 'OPEN') {
                    openShares += t.shares;
                    openCost += (t.entry_price || 0) * t.shares;

                    const currentPrice = live.price || t.entry_price;
                    const upnl = (currentPrice - (t.entry_price || 0)) * t.shares * (isLong ? 1 : -1);
                    totalPnl += upnl;
                } else {
                    if (t.pnl) totalPnl += t.pnl;
                    if (t.exit_price) totalExitValue += (t.exit_price * t.shares);
                    if (t.exit_date) {
                        if (!maxExitDate || new Date(t.exit_date) > new Date(maxExitDate)) {
                            maxExitDate = t.exit_date;
                        }
                    }
                }
            });

            const isHistory = activeTab === 'history';
            const displayShares = isHistory ? totalHistoryShares : openShares;
            const displayCost = isHistory ? totalHistoryCost : openCost;

            const avgPpc = isHistory
                ? (totalHistoryShares > 0 ? totalHistoryCost / totalHistoryShares : 0)
                : (openShares > 0 ? openCost / openShares : 0);

            const avgExitPrice = (isHistory && totalHistoryShares > 0) ? totalExitValue / totalHistoryShares : 0;

            // Use trading days (excludes weekends and holidays)
            let daysHeld = 0;
            if (minEntryDate) {
                const endDate = isHistory && maxExitDate ? new Date(maxExitDate) : new Date();
                daysHeld = getTradingDaysBetween(minEntryDate, endDate);
            }

            const returnBasis = isHistory ? totalHistoryCost : openCost;
            const totalPnlPct = returnBasis > 0 ? (totalPnl / returnBasis) * 100 : 0;

            const currentPrice = live.price || avgPpc;
            const dayChange = live.change_pct || 0;
            const displayPrice = isHistory ? avgExitPrice : live.price;

            return {
                ticker,
                groupTrades,
                live,
                avgPpc,
                displayShares,
                displayCost,
                totalPnl,
                displayPrice,
                dayChange, // numeric for sort
                displayChange: isHistory && maxExitDate ? maxExitDate : (dayChange ? `${dayChange > 0 ? '+' : ''}${dayChange.toFixed(2)}%` : '-'),
                totalPnlPct,
                daysHeld,
                emas: {
                    ema_8: live.ema_8,
                    ema_21: live.ema_21,
                    ema_35: live.ema_35,
                    ema_200: live.ema_200
                },
                currentPrice,
                preMktChange: (!isHistory && live.extended_change_pct) ? live.extended_change_pct : 0,
                isPremarket: live.is_premarket || false,
                isPostmarket: live.is_postmarket || false
            };
        });
    }, [currentGroups, liveData, activeTab, premarket]);

    const sortedRows = useMemo(() => {
        let sortableItems = [...rowStats];

        // Apply W.RSI color filter
        if (rsiColorFilter !== 'all') {
            sortableItems = sortableItems.filter(row => {
                const rsiColor = row.live?.rsi_weekly?.color;
                return rsiColor === rsiColorFilter;
            });
        }

        // Apply sorting
        if (sortConfig.key !== null) {
            sortableItems.sort((a, b) => {
                let aValue = a[sortConfig.key];
                let bValue = b[sortConfig.key];

                // Handle strings generically
                if (typeof aValue === 'string') aValue = aValue.toLowerCase();
                if (typeof bValue === 'string') bValue = bValue.toLowerCase();

                if (aValue < bValue) {
                    return sortConfig.direction === 'asc' ? -1 : 1;
                }
                if (aValue > bValue) {
                    return sortConfig.direction === 'asc' ? 1 : -1;
                }
                return 0;
            });
        }
        return sortableItems;
    }, [rowStats, sortConfig, rsiColorFilter]);

    const requestSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        setSortConfig({ key, direction });
    };

    // Helper for header sort icon
    const getSortIcon = (key) => {
        if (sortConfig.key !== key) return '↕';
        return sortConfig.direction === 'asc' ? '↑' : '↓';
    };

    // STAGE 0: Instant load from cache (no external API calls)
    const fetchCachedData = async () => {
        try {
            const cachedRes = await axios.get(`${API_BASE}/trades/cached-summary`);
            const cached = cachedRes.data;
            // Set cached values immediately for instant UI
            if (cached) {
                setCachedSummary(cached);
            }
        } catch (err) {
            console.error("Cached summary not available:", err);
        }
    };

    // STAGE 1: Fast essential data (trades list + metrics from DB)
    const fetchEssentialData = async () => {
        setLoading(true);
        try {
            // Load trades first (Critical)
            try {
                const tradesRes = await axios.get(`${API_BASE}/trades/list`);
                setTrades(tradesRes.data.trades || []);
            } catch (err) {
                console.error("Failed to fetch trades list:", err);
            }

            // Load metrics independently (Non-critical)
            try {
                const metricsRes = await axios.get(`${API_BASE}/trades/metrics`);
                setMetrics(metricsRes.data);
            } catch (err) {
                console.error("Failed to fetch metrics:", err);
            }
        } catch (err) {
            console.error("Unexpected error in fetchEssentialData", err);
        } finally {
            setLoading(false);
        }
    };

    // STAGE 2: Heavy analytics data (deferred - loads after UI shows)
    const fetchHeavyData = async () => {
        const heavyEndpoints = [
            { url: `${API_BASE}/trades/equity-curve`, setter: setEquityData },
            { url: `${API_BASE}/trades/calendar`, setter: setCalendarData },
            { url: `${API_BASE}/trades/analytics/open`, setter: setOpenAnalytics },
            { url: `${API_BASE}/trades/snapshots`, setter: setSnapshotData },
            { url: `${API_BASE}/trades/analytics/performance`, setter: setPerformanceData },
            { url: `${API_BASE}/argentina/positions`, setter: setArgentinaTrades },
            { url: `${API_BASE}/trades/unified/metrics`, setter: setUnifiedMetrics }
        ];

        await Promise.all(heavyEndpoints.map(ep =>
            axios.get(ep.url)
                .then(res => ep.setter(res.data))
                .catch(err => console.error(`Failed to fetch ${ep.url}:`, err))
        ));
    };

    // Legacy fetchData for manual refresh (loads everything)
    const fetchData = async () => {
        await fetchEssentialData();
        await fetchHeavyData();
        fetchLivePrices();
    };

    const fetchLivePrices = async (forceRefresh = false) => {
        setRefreshing(true);
        try {
            // If force refresh, clear the backend cache first
            if (forceRefresh) {
                await authFetch(`${API_BASE}/prices/refresh`, { method: 'POST' }).catch(() => { });
            }
            const res = await axios.get(`${API_BASE}/trades/open-prices`);
            setLiveData(res.data);
            setLastUpdated(new Date());
        } catch (e) {
            console.error(e);
        } finally {
            setRefreshing(false);
        }
    };

    const loadAlertSettings = async () => {
        try {
            const res = await axios.get(`${API_BASE}/alerts/settings`);
            setAlertSettings(res.data);
        } catch (e) {
            console.error("Failed to load alert settings", e);
        }
    };

    const saveAlertSettings = async () => {
        try {
            await axios.post(`${API_BASE}/alerts/settings`, alertSettings);
            alert("Alert settings saved!");
            setShowAlertModal(false);
        } catch (e) {
            console.error("Failed to save alert settings", e);
            alert("Error saving settings");
        }
    };

    const testAlert = async () => {
        try {
            const res = await axios.post(`${API_BASE}/alerts/test`, null, {
                params: { chat_id: alertSettings.telegram_chat_id }
            });
            if (res.data.success) {
                alert("✅ Test alert sent! Check your Telegram");
            } else {
                alert("❌ Failed to send test alert. Check BOT_TOKEN and chat_id");
            }
        } catch (e) {
            console.error("Test alert failed", e);
            alert("Error sending test alert");
        }
    };


    useEffect(() => {
        // STAGE 0: Immediate load from cache (instant UI)
        fetchCachedData();

        // STAGE 1: Load essential data (trades table renders fast)
        fetchEssentialData();
        loadAlertSettings();

        // STAGE 2: Load heavy data after a small delay (UI renders first)
        const heavyTimer = setTimeout(() => {
            fetchHeavyData();
            fetchLivePrices();
        }, 100);

        // Auto-Refresh Live Prices every 60s
        const interval = setInterval(() => {
            fetchLivePrices();
        }, 60000);

        return () => {
            clearTimeout(heavyTimer);
            clearInterval(interval);
        };
    }, []);


    const fileInputRef = React.useRef(null);


    const handleDownloadTemplate = () => {
        window.location.href = `${API_BASE}/trades/template`;
    };

    const handleImportClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        setLoading(true);
        try {
            const res = await axios.post(`${API_BASE}/trades/upload_csv`, formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });

            if (res.data.errors && res.data.errors.length > 0) {
                alert(`Imported with some errors:
${res.data.errors.join("\n")}`);
            } else {
                alert(res.data.message || "Import successful!");
            }
            fetchData(); // Refresh list
        } catch (e) {
            console.error(e);
            alert("Import failed: " + (e.response?.data?.error || e.message));
        } finally {
            setLoading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = ""; // Reset input
            }
        }
    };


    const handleDelete = async (id) => {
        if (!confirm("Delete this trade?")) return;
        try {
            await axios.delete(`${API_BASE}/trades/${id}`);
            fetchData();
        } catch (e) {
            alert("Delete failed");
        }
    };

    const handleDeleteAll = async () => {
        if (!confirm("⚠️ WARNING: This will DELETE ALL TRADES from your journal.\n\nAre you sure you want to continue?")) return;
        if (!confirm("Double Check: This action cannot be undone. Confirm delete all?")) return;

        try {
            const res = await axios.delete(`${API_BASE}/trades/all`);
            alert(res.data.message);
            fetchData();
        } catch (e) {
            console.error(e);
            alert("Failed to delete all trades");
        }
    };

    const handleUpdateGroup = async (trades, field, value) => {
        try {
            await Promise.all(trades.map(t => axios.put(`${API_BASE}/trades/${t.id}`, { [field]: value })));

            fetchData();
        } catch (e) {
            console.error(e);
            alert("Failed to update group trades");
        }
    };

    const handleApplySplit = async () => {
        if (!splitForm.ticker || !splitForm.ratio) {
            alert("Please fill in all fields");
            return;
        }

        const ratio = splitForm.splitType === 'reverse'
            ? parseFloat(splitForm.ratio)
            : 1 / parseFloat(splitForm.ratio);

        if (confirm(`Apply ${splitForm.splitType} split ${splitForm.ratio}:1 to ${splitForm.ticker}?\n\nShares will be adjusted and prices will be recalculated.`)) {
            try {
                const res = await axios.post(`${API_BASE}/trades/apply-split`, {
                    ticker: splitForm.ticker,
                    split_ratio: ratio
                });
                alert(res.data.message);
                setShowSplitModal(false);
                setSplitForm({ ticker: '', splitType: 'reverse', ratio: '' });
                fetchData();
            } catch (e) {
                console.error(e);
                alert("Failed to apply split: " + (e.response?.data?.detail || e.message));
            }
        }
    };

    // Only show loading spinner if NO cached data AND no trades loaded yet
    if (loading && !cachedSummary && trades.length === 0) return <div className="p-12 text-center text-slate-500">Loading Journal...</div>;

    // Helper for coloring EMAs
    const getEmaColor = (price, ema) => {
        if (!ema) return "text-slate-600";
        return price > ema ? "text-green-400 font-medium" : "text-red-400 font-medium";
    };


    return (
        <div className="p-4 container mx-auto max-w-[1600px]">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        📊 Journal USA
                        {(loading || refreshing) && (
                            <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-1 rounded-full animate-pulse">
                                ⟳ Syncing...
                            </span>
                        )}
                        {!loading && !refreshing && cachedSummary?.snapshot_date && (
                            <span className="text-xs text-slate-500">
                                📸 {cachedSummary.snapshot_date}
                            </span>
                        )}
                        <button onClick={() => fetchLivePrices(true)} disabled={refreshing} className="text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2 py-1 rounded transition text-slate-400">
                            {refreshing ? '↻ Syncing...' : `↻ Refresh ${lastUpdated ? `(${lastUpdated.toLocaleTimeString()})` : ''}`}
                        </button>
                    </h2>
                </div>
                <div className="flex gap-2">
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        style={{ display: 'none' }}
                        accept=".csv"
                    />
                    <button onClick={handleDownloadTemplate} className="bg-slate-800 hover:bg-slate-700 text-slate-400 px-3 py-2 rounded-lg font-medium transition text-sm border border-slate-700" title="Download Template CSV">
                        ⬇️ CSV
                    </button>
                    <button onClick={handleImportClick} className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-slate-600">
                        Import CSV
                    </button>
                    <button onClick={handleDeleteAll} className="bg-red-900/50 hover:bg-red-800 text-red-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-red-800">
                        🗑️ Reset
                    </button>
                    <button onClick={() => setShowSplitModal(true)} className="bg-purple-900/50 hover:bg-purple-800 text-purple-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-purple-800">
                        🔀 Adjust Split
                    </button>
                    <button
                        onClick={() => {
                            setShowAlertModal(true);
                            loadAlertSettings();
                        }}
                        className={`px-4 py-2 rounded-lg font-medium transition text-sm border ${alertSettings.enabled
                            ? 'bg-green-900/50 hover:bg-green-800 text-green-200 border-green-800'
                            : 'bg-slate-800 hover:bg-slate-700 text-slate-400 border-slate-700'
                            }`}
                    >
                        🔔 Alerts {alertSettings.enabled && '✓'}
                    </button>
                    <button
                        onClick={handleAnalyzePortfolio}
                        disabled={analyzing}
                        className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm shadow-lg"
                    >
                        {analyzing ? '🔄 Analyzing...' : '🤖 AI Insights'}
                    </button>
                    <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm">
                        {showForm ? 'Cancel' : '+ Log Trade'}
                    </button>
                </div>
            </div>

            {showForm && <TradeForm onSave={() => { setShowForm(false); fetchData(); }} onCancel={() => setShowForm(false)} />}

            {/* AI Insight Display */}
            {aiInsight && (
                <div className="mb-6 bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-xl p-4">
                    <div className="flex justify-between items-start mb-3">
                        <h3 className="text-purple-400 font-bold flex items-center gap-2">
                            🤖 AI Portfolio Analysis
                        </h3>
                        <button onClick={() => setAiInsight(null)} className="text-slate-500 hover:text-white text-sm">✕ Close</button>
                    </div>
                    {(() => {
                        const text = aiInsight;
                        const sentimentMatch = text.match(/\*\*Sentiment:\*\*\s*(\d+)\/100\s*\(([^)]+)\)/);
                        const analysisMatch = text.match(/\*\*Analysis:\*\*\s*([\s\S]*?)(?=\*\*Actionable|$)/);
                        const actionMatch = text.match(/\*\*Actionable Insight:\*\*\s*([\s\S]*?)$/);

                        if (sentimentMatch) {
                            const score = parseInt(sentimentMatch[1]);
                            const mood = sentimentMatch[2];
                            const analysis = analysisMatch ? analysisMatch[1].trim() : '';
                            const action = actionMatch ? actionMatch[1].trim() : '';

                            const moodColor = score >= 60 ? 'text-green-400' : score >= 40 ? 'text-yellow-400' : 'text-red-400';
                            const barColor = score >= 60 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';

                            return (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-4">
                                        <div className="flex-1">
                                            <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                                                <div className={`${barColor} h-full rounded-full transition-all duration-500`} style={{ width: `${score}%` }}></div>
                                            </div>
                                        </div>
                                        <span className={`text-lg font-bold ${moodColor}`}>{score}/100 {mood}</span>
                                    </div>
                                    {analysis && <p className="text-slate-300 text-sm">{analysis}</p>}
                                    {action && (
                                        <div className="bg-blue-900/40 rounded-lg p-3 border border-blue-500/30">
                                            <span className="text-blue-400 font-bold text-xs">🎯 ACTION:</span>
                                            <p className="text-white text-sm mt-1">{action}</p>
                                        </div>
                                    )}
                                </div>
                            );
                        }
                        return <p className="text-slate-300 text-sm whitespace-pre-wrap">{text.replace(/\*\*/g, '')}</p>;
                    })()}
                </div>
            )}

            {/* Alert Configuration Modal */}
            {
                showAlertModal && (
                    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setShowAlertModal(false)}>
                        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-lg" onClick={(e) => e.stopPropagation()}>
                            <h3 className="text-xl font-bold text-white mb-4">🔔 Telegram Alert Settings</h3>

                            <div className="space-y-4">
                                {/* Enable Toggle */}
                                <div className="flex items-center justify-between bg-slate-800 border border-slate-700 rounded p-3">
                                    <span className="text-white font-medium">Enable Alerts</span>
                                    <button
                                        onClick={() => setAlertSettings({ ...alertSettings, enabled: !alertSettings.enabled })}
                                        className={`px-4 py-2 rounded-lg font-medium transition ${alertSettings.enabled
                                            ? 'bg-green-600 text-white'
                                            : 'bg-slate-700 text-slate-400'
                                            }`}
                                    >
                                        {alertSettings.enabled ? 'ON' : 'OFF'}
                                    </button>
                                </div>

                                {/* Chat ID Input */}
                                <div>
                                    <label className="block text-slate-400 text-sm mb-2">
                                        Telegram Chat ID
                                        <a href="#" className="text-blue-400 ml-2 text-xs hover:underline" onClick={(e) => {
                                            e.preventDefault();
                                            alert("1. Open Telegram → Search @BotFather\n2. Send /newbot\n3. Follow steps\n4. Set BOT_TOKEN in .env\n5. Message your bot with /start\n6. Bot will send you your chat_id");
                                        }}>How to get?</a>
                                    </label>
                                    <input
                                        type="text"
                                        value={alertSettings.telegram_chat_id}
                                        onChange={(e) => setAlertSettings({ ...alertSettings, telegram_chat_id: e.target.value })}
                                        className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white font-mono text-sm"
                                        placeholder="e.g. 123456789"
                                    />
                                </div>

                                {/* Alert Types */}
                                <div className="bg-slate-800 border border-slate-700 rounded p-4 space-y-3">
                                    <div className="text-white font-semibold mb-2">Alert Types:</div>

                                    <label className="flex items-center gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={alertSettings.notify_sl}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, notify_sl: e.target.checked })}
                                            className="w-4 h-4"
                                        />
                                        <span className="text-slate-300">🔴 Stop Loss Hit</span>
                                    </label>

                                    <label className="flex items-center gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={alertSettings.notify_tp}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, notify_tp: e.target.checked })}
                                            className="w-4 h-4"
                                        />
                                        <span className="text-slate-300">🟢 Target Hit</span>
                                    </label>

                                    <label className="flex items-center gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={alertSettings.notify_rsi_sell}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, notify_rsi_sell: e.target.checked })}
                                            className="w-4 h-4"
                                        />
                                        <span className="text-slate-300">📉 W.RSI Bearish Signal</span>
                                    </label>

                                    {/* SL Warning Percentage */}
                                    <div className="pt-2 border-t border-slate-700">
                                        <label className="block text-slate-400 text-sm mb-1">
                                            Warning when price within % of SL:
                                        </label>
                                        <input
                                            type="number"
                                            value={alertSettings.sl_warning_pct}
                                            onChange={(e) => setAlertSettings({ ...alertSettings, sl_warning_pct: parseFloat(e.target.value) })}
                                            className="w-20 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-sm"
                                            step="0.5"
                                            min="0"
                                            max="10"
                                        />
                                        <span className="text-slate-500 ml-2 text-sm">%</span>
                                    </div>
                                </div>

                                {/* Info Box */}
                                <div className="bg-blue-900/30 border border-blue-700/50 rounded p-3 text-sm text-blue-200">
                                    <div className="font-semibold mb-1">ℹ️ How it works:</div>
                                    <div className="text-xs text-blue-300 space-y-1">
                                        <div>• Server checks positions every 5 minutes</div>
                                        <div>• Sends Telegram message when conditions met</div>
                                        <div>• Won't spam (max 1 alert/24h per condition)</div>
                                    </div>
                                </div>
                            </div>

                            <div className="flex gap-2 mt-6">
                                <button onClick={() => setShowAlertModal(false)} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg transition">
                                    Cancel
                                </button>
                                <button onClick={testAlert} className="flex-1 bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-lg font-medium transition">
                                    Test Alert
                                </button>
                                <button onClick={saveAlertSettings} className="flex-1 bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg font-medium transition">
                                    Save
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Split Adjustment Modal */}
            {
                showSplitModal && (
                    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={() => setShowSplitModal(false)}>
                        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                            <h3 className="text-xl font-bold text-white mb-4">Stock Split Adjustment</h3>

                            <div className="space-y-4">
                                <div>
                                    <label className="block text-slate-400 text-sm mb-2">Ticker</label>
                                    <input
                                        type="text"
                                        value={splitForm.ticker}
                                        onChange={(e) => setSplitForm({ ...splitForm, ticker: e.target.value.toUpperCase() })}
                                        className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
                                        placeholder="e.g. MSTU"
                                    />
                                </div>

                                <div>
                                    <label className="block text-slate-400 text-sm mb-2">Split Type</label>
                                    <select
                                        value={splitForm.splitType}
                                        onChange={(e) => setSplitForm({ ...splitForm, splitType: e.target.value })}
                                        className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
                                    >
                                        <option value="reverse">Reverse Split (1:10 - price increases)</option>
                                        <option value="forward">Forward Split (10:1 - price decreases)</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="block text-slate-400 text-sm mb-2">
                                        Ratio (e.g., 10 for {splitForm.splitType === 'reverse' ? '1:10' : '10:1'})
                                    </label>
                                    <input
                                        type="number"
                                        value={splitForm.ratio}
                                        onChange={(e) => setSplitForm({ ...splitForm, ratio: e.target.value })}
                                        className="w-full bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white"
                                        placeholder="10"
                                        step="0.1"
                                    />
                                </div>

                                <div className="bg-slate-800 border border-slate-700 rounded p-3 text-sm text-slate-400">
                                    <div className="font-semibold text-white mb-1">Preview:</div>
                                    {splitForm.ticker && splitForm.ratio ? (
                                        splitForm.splitType === 'reverse' ? (
                                            <div>
                                                • Shares divided by {splitForm.ratio}<br />
                                                • Prices multiplied by {splitForm.ratio}<br />
                                                • Example: 100 shares @ $5 → {(100 / splitForm.ratio).toFixed(0)} shares @ ${(5 * splitForm.ratio).toFixed(2)}
                                            </div>
                                        ) : (
                                            <div>
                                                • Shares multiplied by {splitForm.ratio}<br />
                                                • Prices divided by {splitForm.ratio}<br />
                                                • Example: 10 shares @ $50 → {(10 * splitForm.ratio).toFixed(0)} shares @ ${(50 / splitForm.ratio).toFixed(2)}
                                            </div>
                                        )
                                    ) : (
                                        <div>Fill in the fields to see preview</div>
                                    )}
                                </div>
                            </div>

                            <div className="flex gap-2 mt-6">
                                <button onClick={() => setShowSplitModal(false)} className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded-lg transition">
                                    Cancel
                                </button>
                                <button onClick={handleApplySplit} className="flex-1 bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg font-medium transition">
                                    Apply Split
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }

            {/* Metrics Grid - USD Only */}
            {(() => {
                // Calculate USA-only metrics
                let totalInvested = 0;
                let openPnl = 0;
                let totalDays = 0;
                let openCount = 0;

                trades.forEach(t => {
                    if (t.status === 'OPEN') {
                        const cost = t.shares * t.entry_price;
                        totalInvested += cost;

                        const live = liveData[t.ticker] || {};
                        const currentPrice = live.price || t.entry_price;
                        const isLong = t.direction !== 'SHORT';
                        const pnl = (currentPrice - t.entry_price) * t.shares * (isLong ? 1 : -1);
                        openPnl += pnl;

                        const start = new Date(t.entry_date);
                        const end = new Date();
                        const diff = Math.abs(end - start);
                        totalDays += Math.ceil(diff / (1000 * 60 * 60 * 24));
                        openCount++;
                    }
                });

                const avgDays = openCount > 0 ? totalDays / openCount : 0;
                const roi = totalInvested > 0 ? (openPnl / totalInvested) * 100 : 0;

                return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <MetricCard
                            label="Total Invested"
                            value={`$${totalInvested.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
                            subtext={`${openCount} open trades`}
                            color="text-blue-400"
                        />
                        <MetricCard
                            label="Open P&L $"
                            value={`${openPnl >= 0 ? '+' : ''}$${openPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                            color={openPnl >= 0 ? "text-green-400" : "text-red-400"}
                        />
                        <MetricCard
                            label="Avg Days (Open)"
                            value={avgDays.toFixed(0)}
                            subtext="Average Holding"
                            color="text-yellow-400"
                        />
                        <MetricCard
                            label="Open R.O.I."
                            value={`${roi >= 0 ? '+' : ''}${roi.toFixed(2)}%`}
                            color={roi >= 0 ? "text-green-400" : "text-red-400"}
                        />
                    </div>
                );
            })()}


            {/* SUB TABS */}
            <div className="flex gap-4 border-b border-slate-800 mb-6">
                <button
                    onClick={() => setActiveSubTab('log')}
                    className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'log' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                >
                    📝 Active Positions
                </button>
                <button
                    onClick={() => setActiveSubTab('analytics')}
                    className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'analytics' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                >
                    ⚖️ Portfolio Analytics
                </button>
            </div>

            {/* W.RSI COLOR FILTER (Only show in log view) */}
            {activeSubTab === 'log' && (
                <div className="mb-4 flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-slate-500 font-medium">Filter by W.RSI Phase:</span>
                    {[
                        { value: 'all', label: 'All', bg: 'bg-slate-700', text: 'text-slate-300' },
                        { value: 'green', label: 'Strong', bg: 'bg-green-500', text: 'text-white' },
                        { value: 'blue', label: 'Accum', bg: 'bg-blue-500', text: 'text-white' },
                        { value: 'yellow', label: 'Pull↑', bg: 'bg-yellow-500', text: 'text-slate-900' },
                        { value: 'orange', label: 'Pull↓', bg: 'bg-orange-500', text: 'text-white' },
                        { value: 'pink', label: 'Corr', bg: 'bg-pink-400', text: 'text-white' },
                        { value: 'red', label: 'Bear', bg: 'bg-red-500', text: 'text-white' }
                    ].map(filter => (
                        <button
                            key={filter.value}
                            onClick={() => setRsiColorFilter(filter.value)}
                            className={`px-3 py-1 rounded-full text-xs font-bold transition ${rsiColorFilter === filter.value
                                ? `${filter.bg} ${filter.text} ring-2 ring-white/30`
                                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
                                }`}
                        >
                            {filter.label}
                        </button>
                    ))}
                </div>
            )}

            {/* Sell Modal (USA) */}
            {showSellModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            💸 Venta Parcial: {sellData.ticker}
                        </h3>

                        <div className="space-y-4">
                            <div>
                                <label className="text-slate-400 text-xs uppercase font-bold block mb-1">Cantidad a Vender (Max: {sellData.currentShares})</label>
                                <input
                                    type="number"
                                    value={sellData.sharesToSell || ''}
                                    onChange={(e) => setSellData({ ...sellData, sharesToSell: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white font-mono text-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                    placeholder="Todo"
                                />
                                <div className="flex justify-end mt-1">
                                    <button
                                        onClick={() => setSellData({ ...sellData, sharesToSell: sellData.currentShares })}
                                        className="text-xs text-blue-400 hover:text-blue-300"
                                    >
                                        Vender Todo ({sellData.currentShares})
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="text-slate-400 text-xs uppercase font-bold block mb-1">Precio de Salida</label>
                                <input
                                    type="number"
                                    value={sellData.exitPrice || ''}
                                    onChange={(e) => setSellData({ ...sellData, exitPrice: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white font-mono text-lg focus:ring-2 focus:ring-green-500 outline-none"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 mt-6">
                            <button
                                onClick={() => setShowSellModal(false)}
                                className="bg-slate-700 hover:bg-slate-600 text-white py-3 rounded-lg font-bold transition"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={async () => {
                                    if (!sellData.exitPrice) return alert("Ingresa precio de salida");
                                    const shares = sellData.sharesToSell ? parseInt(sellData.sharesToSell) : sellData.currentShares;

                                    try {
                                        await axios.post(`${API_BASE}/trades/add`, {
                                            ticker: sellData.ticker,
                                            entry_date: new Date().toISOString().split('T')[0],
                                            entry_price: parseFloat(sellData.exitPrice),
                                            shares: shares,
                                            direction: 'SELL',
                                            status: 'CLOSED'
                                        });
                                        setShowSellModal(false);
                                        fetchEssentialData(); // Refresh
                                    } catch (err) {
                                        alert("Error cerrando posición: " + (err.response?.data?.detail || err.message));
                                    }
                                }}
                                className="bg-red-600 hover:bg-red-500 text-white py-3 rounded-lg font-bold transition shadow-lg shadow-red-900/20"
                            >
                                📉 VENDER
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Buy More Modal (USA) */}
            {showBuyModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            📈 Comprar más: {buyData.ticker}
                        </h3>

                        <div className="space-y-4">
                            <div>
                                <label className="text-slate-400 text-xs uppercase font-bold block mb-1">Cantidad de Acciones</label>
                                <input
                                    type="number"
                                    value={buyData.sharesToBuy || ''}
                                    onChange={(e) => setBuyData({ ...buyData, sharesToBuy: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white font-mono text-lg focus:ring-2 focus:ring-green-500 outline-none"
                                    placeholder="Ej: 10"
                                />
                            </div>
                            <div>
                                <label className="text-slate-400 text-xs uppercase font-bold block mb-1">Precio de Compra</label>
                                <input
                                    type="number"
                                    step="0.01"
                                    value={buyData.buyPrice || ''}
                                    onChange={(e) => setBuyData({ ...buyData, buyPrice: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white font-mono text-lg focus:ring-2 focus:ring-green-500 outline-none"
                                    placeholder={`Actual: $${buyData.currentPrice?.toFixed(2)}`}
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-3 mt-6">
                                <button
                                    onClick={() => setShowBuyModal(false)}
                                    className="bg-slate-700 hover:bg-slate-600 text-white py-3 rounded-lg font-bold transition"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={async () => {
                                        if (!buyData.sharesToBuy || !buyData.buyPrice) return alert("Completa todos los campos");

                                        try {
                                            await axios.post(`${API_BASE}/trades/add`, {
                                                ticker: buyData.ticker,
                                                entry_date: new Date().toISOString().split('T')[0],
                                                entry_price: parseFloat(buyData.buyPrice),
                                                shares: parseInt(buyData.sharesToBuy),
                                                direction: 'BUY',
                                                status: 'OPEN'
                                            });
                                            setShowBuyModal(false);
                                            fetchEssentialData(); // Refresh
                                        } catch (err) {
                                            alert("Error agregando compra: " + (err.response?.data?.detail || err.message));
                                        }
                                    }}
                                    className="bg-green-600 hover:bg-green-500 text-white py-3 rounded-lg font-bold transition shadow-lg shadow-green-900/20"
                                >
                                    📈 COMPRAR
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* CONTENT AREA */}
            {
                activeSubTab === 'analytics' ? (
                    <PerformanceDashboard
                        data={openAnalytics}
                        performanceData={performanceData}
                        snapshotData={snapshotData}
                    />
                ) : (
                    <div className="space-y-6">
                        {/* SPREADSHEET TABLE */}
                        <div className="flex gap-6 border-b border-slate-800 mb-6">
                            <button
                                onClick={() => setActiveTab('active')}
                                className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'active' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                            >
                                🚀 Active Positions
                            </button>
                            <button
                                onClick={() => setActiveTab('history')}
                                className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'history' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                            >
                                TRADE HISTORY
                            </button>
                        </div>
                        {/* Color Legend for W.RSI and M.Path */}
                        <div className="mb-4 p-3 bg-slate-800/50 border border-slate-700 rounded-lg text-xs">
                            <div className="flex flex-wrap gap-x-6 gap-y-2">
                                <div className="flex items-center gap-2">
                                    <span className="font-bold text-slate-300">W.RSI:</span>
                                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-green-500"></span> Strong Bullish</span>
                                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500"></span> Accumulation</span>
                                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-yellow-500"></span> Pullback ↑50</span>
                                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500"></span> Pullback ↓50</span>
                                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-pink-400"></span> Correction</span>
                                    <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500"></span> Bearish</span>
                                </div>
                                <div className="flex items-center gap-2 border-l border-slate-600 pl-4">
                                    <span className="font-bold text-cyan-400">M.Path:</span>
                                    <span className="text-slate-400">Projected price (linear regression from last 20 closes)</span>
                                </div>
                                <div className="flex items-center gap-2 border-l border-slate-600 pl-4">
                                    <span className="font-bold text-amber-400">Vol:</span>
                                    <span className="text-green-400">▲</span><span className="text-slate-400">&gt;14d avg</span>
                                    <span className="text-red-400">▼</span><span className="text-slate-400">&lt;14d avg</span>
                                    <span className="text-slate-500">▬</span><span className="text-slate-400">≈avg</span>
                                </div>
                            </div>
                        </div>
                        <div className="bg-slate-900 border border-slate-700 overflow-x-auto overflow-y-auto max-h-[80vh] rounded-lg shadow-xl">
                            <table className="w-full text-left text-[11px] whitespace-nowrap">
                                <thead className="bg-[#0f172a] text-slate-400 uppercase font-bold border-b border-slate-600 select-none">
                                    <tr>
                                        <th onClick={() => requestSort('ticker')} className="p-2 border-r border-slate-800 sticky left-0 bg-[#0f172a] z-10 cursor-pointer hover:text-white transition">
                                            Ticker <span className="text-[9px] ml-1">{getSortIcon('ticker')}</span>
                                        </th>
                                        <th className="p-2 border-r border-slate-800">Fecha</th>
                                        <th onClick={() => requestSort('avgPpc')} className="p-2 text-right border-r border-slate-800 text-yellow-300 cursor-pointer hover:text-white transition">
                                            PPC <span className="text-[9px] ml-1">{getSortIcon('avgPpc')}</span>
                                        </th>
                                        <th onClick={() => requestSort('displayShares')} className="p-2 text-right border-r border-slate-800 cursor-pointer hover:text-white transition">
                                            Qty <span className="text-[9px] ml-1">{getSortIcon('displayShares')}</span>
                                        </th>
                                        <th onClick={() => requestSort('displayCost')} className="p-2 text-right border-r border-slate-800 cursor-pointer hover:text-white transition">
                                            Cost <span className="text-[9px] ml-1">{getSortIcon('displayCost')}</span>
                                        </th>
                                        <th onClick={() => requestSort('totalPnl')} className="p-2 text-right border-r border-slate-800 text-blue-300 font-bold cursor-pointer hover:text-white transition">
                                            P/L $ <span className="text-[9px] ml-1">{getSortIcon('totalPnl')}</span>
                                        </th>
                                        <th onClick={() => requestSort('displayPrice')} className="p-2 text-right border-r border-slate-800 text-blue-300 font-bold cursor-pointer hover:text-white transition">
                                            {activeTab === 'history' ? 'Avg Exit' : '$ Last'} <span className="text-[9px] ml-1">{getSortIcon('displayPrice')}</span>
                                        </th>
                                        <th onClick={() => requestSort('preMktChange')} className="p-2 text-center border-r border-slate-800 text-purple-300 cursor-pointer hover:text-white transition">
                                            PreMkt % <span className="text-[9px] ml-1">{getSortIcon('preMktChange')}</span>
                                        </th>
                                        <th onClick={() => requestSort('dayChange')} className="p-2 text-center border-r border-slate-800 cursor-pointer hover:text-white transition">
                                            {activeTab === 'history' ? 'Exit Date' : '% Day'} <span className="text-[9px] ml-1">{getSortIcon('dayChange')}</span>
                                        </th>
                                        <th onClick={() => requestSort('totalPnlPct')} className="p-2 border-r border-slate-800 text-right font-bold text-white cursor-pointer hover:text-blue-400 transition">
                                            % Trade <span className="text-[9px] ml-1">{getSortIcon('totalPnlPct')}</span>
                                        </th>
                                        <th className="p-2 border-r border-slate-800 text-center">SL</th>
                                        <th className="p-2 border-r border-slate-800 text-center">TP1</th>
                                        <th className="p-2 border-r border-slate-800 text-center">TP2</th>
                                        <th className="p-2 border-r border-slate-800 text-center">TP3</th>
                                        <th onClick={() => requestSort('daysHeld')} className="p-2 border-r border-slate-800 text-center cursor-pointer hover:text-white transition">
                                            Days <span className="text-[9px] ml-1">{getSortIcon('daysHeld')}</span>
                                        </th>
                                        <th className="p-2 border-r border-slate-800">Strategy</th>
                                        <th className="p-2 text-center border-r border-slate-800">W. RSI</th>
                                        <th className="p-2 text-center border-r border-slate-800">EMA 8</th>
                                        <th className="p-2 text-center border-r border-slate-800">EMA 21</th>
                                        <th className="p-2 text-center border-r border-slate-800">EMA 35</th>
                                        <th className="p-2 text-center">EMA 200</th>
                                        <th className="p-2 text-center text-cyan-400 border-l border-slate-700">M.Path</th>
                                        <th className="p-2 text-center text-amber-400 border-l border-slate-700" title="Volume vs 14-day avg">Vol</th>
                                        <th className="p-2 text-center text-purple-400 border-l border-slate-700" title="Weinstein Stage (1-4)">Stage</th>
                                        <th className="p-2 text-center text-slate-400 border-l border-slate-700" title="52-Week Range Position">52w</th>
                                        <th className="p-2 text-center text-blue-400 border-l border-slate-700" title="DI+ > DI- Alignment (D/W)">DI</th>
                                        <th className="p-2 text-center text-green-400 border-l border-slate-700" title="Momentum Score (0-100)">Score</th>
                                        <th className="p-2"></th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800">
                                    {sortedRows.map((row) => {
                                        const {
                                            ticker, groupTrades, avgPpc, displayShares, displayCost,
                                            totalPnl, displayPrice, dayChange, displayChange,
                                            totalPnlPct, daysHeld, emas, currentPrice
                                        } = row;

                                        const isHistory = activeTab === 'history';
                                        const isExpanded = expandedGroups[ticker];

                                        // Safe check for current price and direction (default LONG)
                                        const price = parseFloat(currentPrice) || 0;

                                        // SL/TP Hit Logic
                                        const slVal = parseFloat(groupTrades[0]?.stop_loss);
                                        const tp1Val = parseFloat(groupTrades[0]?.target);
                                        const tp2Val = parseFloat(groupTrades[0]?.target2);
                                        const tp3Val = parseFloat(groupTrades[0]?.target3);

                                        const slClass = (slVal > 0 && price > 0 && price < slVal) ? "bg-yellow-400 text-red-900 font-bold border border-red-900 rounded" : "text-slate-500";
                                        const tpClassBase = "bg-green-400 text-slate-900 font-bold border border-green-600 rounded";

                                        const tp1Class = (tp1Val > 0 && price > 0 && price > tp1Val) ? tpClassBase : "text-slate-500";
                                        const tp2Class = (tp2Val > 0 && price > 0 && price > tp2Val) ? tpClassBase : "text-slate-500";
                                        const tp3Class = (tp3Val > 0 && price > 0 && price > tp3Val) ? tpClassBase : "text-slate-500";

                                        return (
                                            <Fragment key={ticker}>
                                                {/* GROUP ROW */}
                                                <tr className="bg-slate-900 hover:bg-slate-800 transition border-b border-slate-800 cursor-pointer" onClick={() => toggleGroup(ticker)}>
                                                    <td className="p-2 border-r border-slate-800 font-bold text-blue-400 sticky left-0 bg-slate-900 z-10 flex items-center gap-2">
                                                        <span className="text-slate-500 text-[10px] w-4">{isExpanded ? '▼' : '▶'}</span>
                                                        {/* Ticker Link - Opens Chart in New Tab */}
                                                        <a
                                                            href={`/?ticker=${ticker}&view=charts&entry=${avgPpc}&stop=${groupTrades[0]?.stop_loss || ''}&target=${groupTrades[0]?.target || ''}`}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="font-bold hover:text-blue-300 transition-colors"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            {ticker}
                                                        </a>
                                                        <span className="text-slate-600 font-normal ml-1 text-[9px]">{groupTrades.length}</span>
                                                    </td>
                                                    <td className="p-2 border-r border-slate-800 text-slate-500 italic text-[10px]">{groupTrades[0].entry_date}</td>
                                                    <td className="p-2 text-right border-r border-slate-800 text-yellow-200 font-mono font-bold">${avgPpc.toFixed(2)}</td>
                                                    <td className="p-2 text-right border-r border-slate-800 text-slate-300 font-bold">{displayShares}</td>
                                                    <td className="p-2 text-right border-r border-slate-800 text-slate-500">${displayCost.toFixed(0)}</td>

                                                    {/* Aggregated P/L */}
                                                    <td className={`p-2 text-right border-r border-slate-800 font-bold font-mono ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        ${totalPnl.toFixed(0)}
                                                    </td>

                                                    {/* Live Data / Avg Exit */}
                                                    <td className="p-2 text-right border-r border-slate-800 text-blue-200 font-mono font-bold">
                                                        {displayPrice ? `$${displayPrice.toFixed(2)}` : '-'}
                                                    </td>
                                                    {/* Pre-Market % */}
                                                    <td className="p-2 text-center border-r border-slate-800">

                                                        {(() => {
                                                            if (isHistory) return <span className="text-slate-600">-</span>;
                                                            // Use properly mapped preMktChange from row stats
                                                            const pmChange = row.preMktChange;
                                                            if (!pmChange || pmChange === 0) return <span className="text-slate-600 text-[10px]">-</span>;
                                                            const pmColor = pmChange > 0 ? 'text-green-400' : pmChange < 0 ? 'text-red-400' : 'text-slate-400';
                                                            return <span className={`font-bold ${pmColor}`}>{pmChange > 0 ? '+' : ''}{pmChange}%</span>;
                                                        })()}
                                                    </td>
                                                    <td className={`p-2 text-center border-r border-slate-800 ${!isHistory && dayChange >= 0 ? 'text-green-400' : (!isHistory ? 'text-red-400' : 'text-slate-400')}`}>
                                                        {displayChange}
                                                    </td>
                                                    <td className={`p-2 text-right border-r border-slate-800 font-bold ${totalPnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {totalPnlPct.toFixed(2)}%
                                                    </td>

                                                    {/* SL/TP placeholders - NOW EDITABLE */}
                                                    <td className="p-2 border-r border-slate-800 text-center">
                                                        <EditableCell value={groupTrades[0]?.stop_loss} onSave={(val) => handleUpdateGroup(groupTrades, 'stop_loss', val)} width="w-12" className={slClass} prefix="$" />
                                                    </td>
                                                    <td className="p-2 border-r border-slate-800 text-center">
                                                        <EditableCell value={groupTrades[0]?.target} onSave={(val) => handleUpdateGroup(groupTrades, 'target', val)} width="w-12" className={tp1Class} prefix="$" />
                                                    </td>
                                                    <td className="p-2 border-r border-slate-800 text-center">
                                                        <EditableCell value={groupTrades[0]?.target2} onSave={(val) => handleUpdateGroup(groupTrades, 'target2', val)} width="w-12" className={tp2Class} prefix="$" />
                                                    </td>
                                                    <td className="p-2 border-r border-slate-800 text-center">
                                                        <EditableCell value={groupTrades[0]?.target3} onSave={(val) => handleUpdateGroup(groupTrades, 'target3', val)} width="w-12" className={tp3Class} prefix="$" />
                                                    </td>

                                                    {/* Days Held */}
                                                    <td className="p-2 border-r border-slate-800 text-center font-bold text-slate-300">{daysHeld}</td>

                                                    {/* Strategy */}
                                                    <td className="p-2 border-r border-slate-800 text-slate-500 italic text-[10px]">
                                                        <EditableCell value={groupTrades[0]?.strategy} onSave={(val) => handleUpdateGroup(groupTrades, 'strategy', val)} width="w-24" />
                                                    </td>

                                                    {/* Weekly RSI - 4-TIER COLOR SCHEME */}
                                                    <td className="p-2 text-center border-r border-slate-800 font-bold font-mono">
                                                        {(() => {
                                                            const rsi = row.live?.rsi_weekly;
                                                            if (!rsi) return <span className="text-slate-600">-</span>;

                                                            // 4-tier color logic from backend
                                                            const colorMap = {
                                                                green: { text: "text-green-400", bg: "bg-green-900/30", arrow: "▲" },
                                                                blue: { text: "text-blue-400", bg: "bg-blue-900/30", arrow: "▲" },
                                                                pink: { text: "text-pink-400", bg: "bg-pink-900/30", arrow: "▼" },
                                                                yellow: { text: "text-yellow-400", bg: "bg-yellow-900/30", arrow: "▼" },
                                                                orange: { text: "text-orange-400", bg: "bg-orange-900/30", arrow: "▼" },
                                                                red: { text: "text-red-400", bg: "bg-red-900/30", arrow: "▼" }
                                                            };
                                                            const color = rsi.color || (rsi.bullish ? 'green' : 'red');
                                                            const styles = colorMap[color] || colorMap.red;

                                                            return (
                                                                <div className={`flex flex-col items-center leading-none px-1 py-0.5 rounded ${styles.bg}`}>
                                                                    <span className={styles.text}>{rsi.val.toFixed(1)}</span>
                                                                    <span className={`text-[9px] ${styles.text}`}>{styles.arrow}</span>
                                                                </div>
                                                            );
                                                        })()}
                                                    </td>

                                                    {/* EMAS (Group level) with Violation Counters */}
                                                    <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_8)}`}>
                                                        {emas.ema_8 ? <span>${emas.ema_8.toFixed(2)}</span> : '-'}
                                                    </td>
                                                    <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_21)}`}>
                                                        {emas.ema_21 ? <span>${emas.ema_21.toFixed(2)}</span> : '-'}
                                                    </td>
                                                    <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_35)}`}>
                                                        {emas.ema_35 ? <span>${emas.ema_35.toFixed(2)}</span> : '-'}
                                                    </td>
                                                    <td className={`p-2 text-center ${getEmaColor(currentPrice || 0, emas.ema_200)}`}>
                                                        {emas.ema_200 ? <span>${emas.ema_200.toFixed(2)}</span> : '-'}
                                                    </td>
                                                    <td className="p-2 text-center border-l border-slate-700 font-bold">
                                                        {(() => {
                                                            const mPath = row.live?.momentum_path;
                                                            const price = currentPrice || 0;
                                                            if (!mPath) return <span className="text-slate-600">-</span>;

                                                            let colorClass = 'text-yellow-400';
                                                            if (mPath > price) colorClass = 'text-green-400';
                                                            else if (mPath < price) colorClass = 'text-red-400';

                                                            return <span className={colorClass}>${mPath.toFixed(2)}</span>;
                                                        })()}
                                                    </td>
                                                    {/* Volume Trend */}
                                                    <td className="p-2 text-center border-l border-slate-700 font-bold text-lg">
                                                        {(() => {
                                                            const volTrend = row.live?.volume_trend;
                                                            if (!volTrend) return <span className="text-slate-600">-</span>;
                                                            if (volTrend === 'up') return <span className="text-green-400" title="Vol > 14d avg">▲</span>;
                                                            if (volTrend === 'down') return <span className="text-red-400" title="Vol < 14d avg">▼</span>;
                                                            return <span className="text-slate-500" title="Vol ≈ 14d avg">▬</span>;
                                                        })()}
                                                    </td>
                                                    {/* Stage (Weinstein) */}
                                                    <td className="p-2 text-center border-l border-slate-700">
                                                        {(() => {
                                                            const stage = row.live?.stage;
                                                            if (!stage || stage.stage === 0) return <span className="text-slate-600">-</span>;
                                                            const colors = {
                                                                blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
                                                                green: 'bg-green-500/20 text-green-400 border-green-500/30',
                                                                yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
                                                                red: 'bg-red-500/20 text-red-400 border-red-500/30',
                                                                gray: 'bg-slate-500/20 text-slate-400 border-slate-500/30'
                                                            };
                                                            return (
                                                                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${colors[stage.color] || colors.gray}`} title={stage.label}>
                                                                    S{stage.stage}
                                                                </span>
                                                            );
                                                        })()}
                                                    </td>
                                                    {/* 52w Range */}
                                                    <td className="p-2 text-center border-l border-slate-700" style={{ minWidth: '60px' }}>
                                                        {(() => {
                                                            const range = row.live?.range_52w;
                                                            if (!range || range.high === 0) return <span className="text-slate-600">-</span>;
                                                            const pct = range.position_pct;
                                                            const color = pct > 70 ? 'bg-green-500' : pct > 30 ? 'bg-yellow-500' : 'bg-red-500';
                                                            return (
                                                                <div className="relative w-full h-2 bg-slate-700 rounded-full overflow-hidden" title={`$${range.low} - $${range.high} (${pct.toFixed(0)}%)`}>
                                                                    <div className="absolute left-0 h-full bg-slate-600" style={{ width: '100%' }}></div>
                                                                    <div className={`absolute h-3 w-1 ${color} rounded-full -top-0.5`} style={{ left: `${Math.min(95, Math.max(5, pct))}%` }}></div>
                                                                </div>
                                                            );
                                                        })()}
                                                    </td>
                                                    {/* DI Alignment (D/W) */}
                                                    <td className="p-2 text-center border-l border-slate-700">
                                                        {(() => {
                                                            const di = row.live?.di_alignment;
                                                            if (!di) return <span className="text-slate-600">-</span>;
                                                            return (
                                                                <div className="flex gap-0.5 justify-center">
                                                                    <span className={`px-1 py-0.5 rounded text-[8px] font-bold ${di.d1 === true ? 'bg-green-500/20 text-green-400' : di.d1 === false ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-500'}`}>D</span>
                                                                    <span className={`px-1 py-0.5 rounded text-[8px] font-bold ${di.w1 === true ? 'bg-green-500/20 text-green-400' : di.w1 === false ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-500'}`}>W</span>
                                                                </div>
                                                            );
                                                        })()}
                                                    </td>
                                                    {/* Momentum Score */}
                                                    <td className="p-2 text-center border-l border-slate-700">
                                                        {(() => {
                                                            const score = row.live?.momentum_score;
                                                            if (score === undefined || score === null) return <span className="text-slate-600">-</span>;
                                                            let colorClass = 'text-red-400';
                                                            if (score >= 70) colorClass = 'text-green-400';
                                                            else if (score >= 40) colorClass = 'text-yellow-400';
                                                            return <span className={`font-bold ${colorClass}`}>{score}</span>;
                                                        })()}
                                                    </td>
                                                    <td className="p-2 border-l border-slate-800 flex justify-center gap-1 bg-slate-900">
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                // Open Buy More Modal pre-filled for this ticker
                                                                setBuyData({
                                                                    ticker: ticker,
                                                                    currentPrice: currentPrice || avgPpc,
                                                                    sharesToBuy: '',
                                                                    buyPrice: currentPrice || avgPpc
                                                                });
                                                                setShowBuyModal(true);
                                                            }}
                                                            className="bg-green-600/20 hover:bg-green-600 text-green-400 hover:text-white px-2 py-0.5 rounded text-[10px] transition border border-green-600/30"
                                                            title="Comprar más"
                                                        >
                                                            +
                                                        </button>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                if (activeTab === 'active') {
                                                                    setSellData({
                                                                        ticker: ticker,
                                                                        currentShares: displayShares,
                                                                        currentPrice: currentPrice || avgPpc,
                                                                        exitPrice: currentPrice || avgPpc,
                                                                        sharesToSell: ''
                                                                    });
                                                                    setShowSellModal(true);
                                                                }
                                                            }}
                                                            className="bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white px-2 py-0.5 rounded text-[10px] transition border border-red-600/30"
                                                            title="Vender / Cerrar Posición"
                                                        >
                                                            x
                                                        </button>
                                                    </td>
                                                </tr>

                                                {/* DETAIL ROWS */}
                                                {
                                                    isExpanded && groupTrades.map(trade => {
                                                        // Keeping detail row logic same as before, essentially nested
                                                        // Not sorting detail rows for now as requested user focus was main columns
                                                        const live = row.live; // reusing live data from row stats
                                                        const isClosed = trade.status === 'CLOSED';

                                                        // Price Logic
                                                        const currentPrice = isClosed ? trade.exit_price : (live.price || trade.entry_price);
                                                        const displayPrice = isClosed ? trade.exit_price : (live.price || null);

                                                        // Day/Date Logic
                                                        const dayChange = live.change_pct || 0;
                                                        const displayDate = isClosed ? trade.exit_date : (dayChange ? `${dayChange > 0 ? '+' : ''}${dayChange.toFixed(2)}%` : '-');

                                                        // PnL Logic
                                                        const pnl = (currentPrice - trade.entry_price) * trade.shares * (trade.direction === 'LONG' ? 1 : -1);
                                                        const pnlPct = ((currentPrice - trade.entry_price) / trade.entry_price) * 100 * (trade.direction === 'LONG' ? 1 : -1);

                                                        // Days Held Logic
                                                        const start = new Date(trade.entry_date);
                                                        const end = isClosed && trade.exit_date ? new Date(trade.exit_date) : new Date();
                                                        const daysHeld = getTradingDaysBetween(trade.entry_date, end);

                                                        return (
                                                            <tr key={trade.id} className="bg-slate-900/40 hover:bg-slate-800/60 transition border-b border-slate-800/30">
                                                                <td className="p-2 border-r border-slate-800 border-l-4 border-l-slate-700 sticky left-0 bg-[#162032] z-10 pl-8 text-slate-500 text-[10px]">
                                                                    ↳ {trade.id}
                                                                </td>
                                                                <td className="p-2 border-r border-slate-800 text-slate-500 text-[10px]">{trade.entry_date}</td>
                                                                <td className="p-2 text-right border-r border-slate-800">
                                                                    <EditableCell
                                                                        value={trade.entry_price}
                                                                        onSave={(val) => {
                                                                            axios.put(`${API_BASE}/trades/${trade.id}`, { entry_price: parseFloat(val) })
                                                                                .then(() => fetchData())
                                                                                .catch(e => console.error(e));
                                                                        }}
                                                                        prefix="$"
                                                                        type="number"
                                                                        width="w-20"
                                                                        className="text-slate-400 font-mono text-[10px]"
                                                                    />
                                                                </td>
                                                                <td className="p-2 text-right border-r border-slate-800">
                                                                    <EditableCell
                                                                        value={trade.shares}
                                                                        onSave={(val) => {
                                                                            axios.put(`${API_BASE}/trades/${trade.id}`, { shares: parseInt(val) })
                                                                                .then(() => fetchData())
                                                                                .catch(e => console.error(e));
                                                                        }}
                                                                        type="number"
                                                                        width="w-16"
                                                                        className="text-slate-500 text-[10px]"
                                                                    />
                                                                </td>
                                                                <td className="p-2 text-right border-r border-slate-800 text-slate-600 text-[10px]">${(trade.entry_price * trade.shares).toFixed(0)}</td>
                                                                <td className={`p-2 text-right border-r border-slate-800 border-l border-l-slate-700 font-mono text-[10px] ${pnl >= 0 ? 'text-green-500/70' : 'text-red-500/70'}`}>
                                                                    ${pnl.toFixed(0)}
                                                                </td>

                                                                {/* Price Column (Exit or Live) */}
                                                                <td className="p-2 text-right border-r border-slate-800 text-slate-400 font-mono text-[10px]">
                                                                    {displayPrice ? `$${displayPrice.toFixed(2)}` : '...'}
                                                                </td>

                                                                {/* Premarket Alignment Column (Empty for child rows) */}
                                                                <td className="p-2 text-center border-r border-slate-800 text-slate-700 text-[10px]">-</td>

                                                                {/* Date/Change Column */}
                                                                <td className={`p-2 text-center border-r border-slate-800 text-[10px] ${!isClosed && dayChange >= 0 ? 'text-green-500/70' : (!isClosed ? 'text-red-500/70' : 'text-slate-500')}`}>
                                                                    {displayDate}
                                                                </td>

                                                                <td className={`p-2 text-right border-r border-slate-800 text-[10px] ${pnlPct >= 0 ? 'text-green-500/70' : 'text-red-500/70'}`}>
                                                                    {pnlPct.toFixed(2)}%
                                                                </td>
                                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.stop_loss || '-'}</td>
                                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.target || '-'}</td>
                                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.target2 || '-'}</td>
                                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.target3 || '-'}</td>
                                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 text-[10px]">{daysHeld}</td>
                                                                <td className="p-2 border-r border-slate-800 text-slate-600 text-[10px]">{trade.strategy || '-'}</td>
                                                                <td colSpan="5" className="p-2 text-center text-slate-600 text-[10px]">
                                                                    <button onClick={() => handleDelete(trade.id)} className="hover:text-red-400">Delete</button>
                                                                </td>
                                                            </tr>
                                                        );
                                                    })
                                                }
                                            </Fragment>
                                        );
                                    })}
                                    {sortedRows.length === 0 && trades.length > 0 && (
                                        <tr>
                                            <td colSpan="20" className="p-12 text-center text-slate-400">
                                                <div className="flex flex-col items-center gap-2">
                                                    <span className="text-4xl">📭</span>
                                                    <span className="font-bold">
                                                        {activeTab === 'active'
                                                            ? "No active positions found."
                                                            : "No trade history found."}
                                                    </span>
                                                    <span className="text-xs text-slate-500">
                                                        {activeTab === 'active'
                                                            ? "You have " + trades.length + " trades in the database, but none are currently 'OPEN'. Check 'Trade History' tab."
                                                            : "No closed trades found."}
                                                    </span>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                    {trades.length === 0 && (
                                        <tr>
                                            <td colSpan="20" className="p-8 text-center text-slate-500">No active trades. Log one to see the tracker!</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                        {/* Legend */}
                        <div className="mt-4 flex gap-4 text-[10px] text-slate-500">
                            <div className="flex items-center gap-1"><div className="w-3 h-3 bg-green-900/40 rounded"></div> Price {'>'} EMA</div>
                            <div className="flex items-center gap-1"><div className="w-3 h-3 bg-red-900/40 rounded"></div> Price {'<'} EMA</div>
                        </div>

                        {/* Trade History Summary Totals */}
                        {activeTab === 'history' && Object.keys(historyGroups).length > 0 && (() => {
                            const closedTrades = Object.values(historyGroups).flat();
                            const totalClosedPL = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
                            const avgTradePercent = closedTrades.length > 0
                                ? closedTrades.reduce((sum, t) => sum + ((t.pnl / (t.entry_price * t.shares)) * 100 || 0), 0) / closedTrades.length
                                : 0;
                            const avgDays = closedTrades.length > 0
                                ? closedTrades.reduce((sum, t) => {
                                    if (t.exit_date && t.entry_date) {
                                        const days = Math.floor((new Date(t.exit_date) - new Date(t.entry_date)) / (1000 * 60 * 60 * 24));
                                        return sum + days;
                                    }
                                    return sum;
                                }, 0) / closedTrades.length
                                : 0;
                            return (
                                <div className="mt-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700">
                                    <h3 className="text-sm font-bold text-slate-300 mb-3">📊 Trade History Summary</h3>
                                    <div className="grid grid-cols-3 gap-4">
                                        <div className="text-center">
                                            <div className="text-[10px] text-slate-500 uppercase">Total Closed P&L</div>
                                            <div className={`text-lg font-bold ${totalClosedPL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {totalClosedPL >= 0 ? '+' : ''}${totalClosedPL.toFixed(2)}
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <div className="text-[10px] text-slate-500 uppercase">Avg % per Trade</div>
                                            <div className={`text-lg font-bold ${avgTradePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {avgTradePercent >= 0 ? '+' : ''}{avgTradePercent.toFixed(2)}%
                                            </div>
                                        </div>
                                        <div className="text-center">
                                            <div className="text-[10px] text-slate-500 uppercase">Avg Days Held</div>
                                            <div className="text-lg font-bold text-white">
                                                {Math.round(avgDays)} days
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                )
            }
        </div >
    );
}





// Inline Editable Cell Component
function EditableCell({ value, onSave, prefix = '', type = 'text', width = 'w-16', className = '' }) {
    const [isEditing, setIsEditing] = useState(false);
    const [tempValue, setTempValue] = useState(value || '');

    useEffect(() => {
        setTempValue(value || '');
    }, [value]);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            save();
        } else if (e.key === 'Escape') {
            setTempValue(value || '');
            setIsEditing(false);
        }
    };

    const save = () => {
        if (tempValue != value) {
            onSave(tempValue);
        }
        setIsEditing(false);
    };

    if (isEditing) {
        return (
            <input
                autoFocus
                type={type}
                className={`bg-slate-700 text-white text-[10px] p-1 rounded border border-blue-500 outline-none ${width}`}
                value={tempValue}
                onChange={(e) => setTempValue(e.target.value)}
                onBlur={save}
                onKeyDown={handleKeyDown}
            />
        );
    }

    return (
        <div
            onClick={() => setIsEditing(true)}
            className={`cursor-pointer hover:bg-slate-800/80 hover:text-blue-300 rounded px-1 transition-colors min-w-[20px] min-h-[16px] text-center flex items-center justify-center ${className}`}
            title="Click to edit"
        >
            {value ? `${prefix}${value}` : <span className="text-slate-700 text-[9px]">-</span>}
        </div>
    );
}

// Stock Chart Component
function StockChart({ data, width, height, metrics }) {
    const { ComposedChart, XAxis, YAxis, Tooltip, CartesianGrid, Area, Line, ReferenceLine, ResponsiveContainer } = Recharts;

    // Calculate domain for Y axis to auto-scale
    const minPrice = Math.min(...data.map(d => d.low)) * 0.98;
    const maxPrice = Math.max(...data.map(d => d.high)) * 1.02;

    return (
        <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data}>
                <defs>
                    <linearGradient id="colorClose" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8884d8" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#8884d8" stopOpacity={0} />
                    </linearGradient>
                </defs>
                <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
                <XAxis
                    dataKey="date"
                    tick={{ fill: '#94a3b8', fontSize: 10 }}
                    axisLine={{ stroke: '#475569' }}
                    minTickGap={30}
                    tickFormatter={(tick) => {
                        const date = new Date(tick);
                        return `${date.getMonth() + 1}/${date.getDate()}`;
                    }}
                />
                <YAxis
                    domain={[minPrice, maxPrice]}
                    tick={{ fill: '#94a3b8', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    orientation="right"
                    tickFormatter={(val) => val.toFixed(0)}
                />
                <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#cbd5e1' }}
                    itemStyle={{ color: '#cbd5e1' }}
                    labelStyle={{ color: '#94a3b8', marginBottom: 5 }}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                    formatter={(value) => ["$" + value.toFixed(2), "Price"]}
                />

                {/* Price Area */}
                <Area type="monotone" dataKey="close" stroke="#8b5cf6" fillOpacity={1} fill="url(#colorClose)" strokeWidth={2} />

                {/* EMAs */}
                <Line type="monotone" dataKey="ema_8" stroke="#22c55e" strokeWidth={1} dot={false} name="EMA 8" />
                <Line type="monotone" dataKey="ema_21" stroke="#f59e0b" strokeWidth={1} dot={false} name="EMA 21" />
                <Line type="monotone" dataKey="ema_35" stroke="#8b5cf6" strokeWidth={1} dot={false} name="EMA 35" />
                <Line type="monotone" dataKey="ema_200" stroke="#ef4444" strokeWidth={1} dot={false} name="EMA 200" />

                {/* Levels */}
                {metrics && metrics.entry > 0 && <ReferenceLine y={metrics.entry} stroke="#3b82f6" strokeDasharray="3 3" label={{ value: 'ENTRY', fill: '#3b82f6', fontSize: 10, position: 'insideLeft' }} />}
                {metrics && metrics.stop_loss > 0 && <ReferenceLine y={metrics.stop_loss} stroke="#ef4444" strokeDasharray="3 3" label={{ value: 'SL', fill: '#ef4444', fontSize: 10, position: 'insideLeft' }} />}
                {metrics && metrics.target > 0 && <ReferenceLine y={metrics.target} stroke="#22c55e" strokeDasharray="3 3" label={{ value: 'TP', fill: '#22c55e', fontSize: 10, position: 'insideLeft' }} />}
            </ComposedChart>
        </ResponsiveContainer>
    );
}

// Risk Calculator Component
function RiskCalculator({ entry, stopLoss, currentPrice }) {
    const [accountBalance, setAccountBalance] = useState(10000);
    const [riskPct, setRiskPct] = useState(1.0);

    // Auto-calc
    const riskAmount = accountBalance * (riskPct / 100);
    const riskPerShare = Math.abs(entry - stopLoss);

    // Avoid infinity
    const shares = riskPerShare > 0 ? Math.floor(riskAmount / riskPerShare) : 0;
    const positionSize = shares * entry;

    return (
        <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
            <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                    <label className="text-[10px] text-slate-500 uppercase font-bold">Account Balance</label>
                    <div className="flex items-center bg-slate-900 rounded border border-slate-700 mt-1">
                        <span className="pl-2 text-slate-500 text-xs">$</span>
                        <input
                            type="number"
                            value={accountBalance}
                            onChange={e => setAccountBalance(Number(e.target.value))}
                            className="bg-transparent text-white text-sm p-1.5 w-full outline-none"
                        />
                    </div>
                </div>
                <div>
                    <label className="text-[10px] text-slate-500 uppercase font-bold">Risk %</label>
                    <div className="flex items-center bg-slate-900 rounded border border-slate-700 mt-1">
                        <input
                            type="number"
                            step="0.1"
                            value={riskPct}
                            onChange={e => setRiskPct(Number(e.target.value))}
                            className="bg-transparent text-white text-sm p-1.5 w-full outline-none"
                        />
                        <span className="pr-2 text-slate-500 text-xs">%</span>
                    </div>
                </div>
            </div>

            <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-700 space-y-2">
                <div className="flex justify-between items-center">
                    <span className="text-slate-400 text-xs">Risk Amount</span>
                    <span className="text-red-400 font-bold text-sm">-${riskAmount.toFixed(0)}</span>
                </div>
                <div className="flex justify-between items-center border-t border-slate-700 pt-2">
                    <span className="text-blue-300 text-sm font-bold">SHARES TO BUY</span>
                    <span className="text-white text-xl font-mono font-bold">{shares}</span>
                </div>
                <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-500">Position Size</span>
                    <span className="text-slate-300">${positionSize.toLocaleString()}</span>
                </div>
            </div>
        </div>
    );
}

// Watchlist Sidebar
function WatchlistSidebar({ onSelectTicker }) {
    const [watchlist, setWatchlist] = useState([]);

    useEffect(() => {
        axios.get(`${API_BASE}/watchlist?_t=${Date.now()}`).then(res => setWatchlist(res.data)).catch(console.error);
        const interval = setInterval(() => {
            axios.get(`${API_BASE}/watchlist?_t=${Date.now()}`).then(res => setWatchlist(res.data)).catch(console.error);
        }, 15000);
        return () => clearInterval(interval);
    }, []);

    const handleDelete = (e, ticker) => {
        e.stopPropagation();
        if (confirm(`Remove ${ticker}?`)) {
            axios.delete(`${API_BASE}/watchlist/${ticker}`).then(() => {
                setWatchlist(prev => prev.filter(i => i.ticker !== ticker));
            });
        }
    };

    return (
        <div className="w-14 hover:w-64 transition-all duration-300 h-screen bg-slate-900 border-l border-slate-800 flex flex-col items-center hover:items-stretch overflow-hidden group fixed right-0 z-40 shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-center group-hover:justify-between h-16 shrink-0">
                <span className="text-xl">⭐️</span>
                <span className="font-bold text-white opacity-0 group-hover:opacity-100 whitespace-nowrap transition-opacity duration-200 ml-2">Watchlist</span>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {watchlist.map(item => (
                    <div key={item.ticker} onClick={() => onSelectTicker(item.ticker)} className="bg-slate-800/50 p-2 rounded cursor-pointer hover:bg-slate-700 group/item relative">
                        <div className="flex justify-between items-center">
                            <span className="font-bold text-white text-sm hidden group-hover:block">{item.ticker}</span>
                            <span className="font-bold text-white text-xs block group-hover:hidden">{item.ticker.slice(0, 3)}</span>
                        </div>
                        <button onClick={(e) => handleDelete(e, item.ticker)} className="absolute right-2 top-2 text-slate-600 hover:text-red-400 opacity-0 group-hover/item:opacity-100 hidden group-hover:block">✕</button>
                    </div>
                ))}
            </div>
        </div>
    );
}

// TradingView Chart Component with separate Volume and RSI panels
function TradingViewChart({ ticker, chartData, elliottWave, metrics, tradeHistory }) {
    const chartContainerRef = React.useRef(null);
    const volumeContainerRef = React.useRef(null);
    const rsiContainerRef = React.useRef(null);
    const chartRef = React.useRef(null);
    const volumeChartRef = React.useRef(null);
    const rsiChartRef = React.useRef(null);
    const markersRef = React.useRef([]); // Store markers to persist across scrolling
    const drawingsRef = React.useRef([]); // Ref to hold series objects for drawings
    const isDraggingRef = React.useRef(false); // Track if currently dragging
    const dragStartPointRef = React.useRef(null); // {time, price} where drag started
    const previewSeriesRef = React.useRef(null); // Temporary line series for preview
    const tvDataRef = React.useRef([]); // Store chart data for access in handlers

    const [drawings, setDrawings] = useState(() => {
        const saved = localStorage.getItem(`drawings_${ticker}`);
        return saved ? JSON.parse(saved) : [];
    });
    const [drawingMode, setDrawingMode] = useState(null); // 'trendline', 'horizontal', 'ray', 'label', or null
    const [tempPoint, setTempPoint] = useState(null); // {time, price} for multi-click tools

    React.useEffect(() => {
        if (!chartContainerRef.current || !volumeContainerRef.current || !rsiContainerRef.current || !chartData || chartData.length === 0) return;

        // Create main price chart (60% height)
        const chart = LightweightCharts.createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            layout: { background: { color: '#1e293b' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: '#475569' },
            timeScale: {
                borderColor: '#475569',
                timeVisible: true,
                visible: false,
                rightOffset: 50, // Espacio a la derecha para dibujar en el futuro
                fixLeftEdge: false,
                fixRightEdge: false
            },
        });
        chartRef.current = chart;

        // Create Volume chart (20% height)
        const volumeChart = LightweightCharts.createChart(volumeContainerRef.current, {
            width: volumeContainerRef.current.clientWidth,
            height: volumeContainerRef.current.clientHeight,
            layout: { background: { color: '#1e293b' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: '#475569' },
            timeScale: {
                borderColor: '#475569',
                timeVisible: true,
                visible: false,
                rightOffset: 50,
                fixLeftEdge: false,
                fixRightEdge: false
            },
        });
        volumeChartRef.current = volumeChart;

        // Create RSI chart (20% height)
        const rsiChart = LightweightCharts.createChart(rsiContainerRef.current, {
            width: rsiContainerRef.current.clientWidth,
            height: rsiContainerRef.current.clientHeight,
            layout: { background: { color: '#1e293b' }, textColor: '#94a3b8' },
            grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
            crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
            rightPriceScale: { borderColor: '#475569' },
            timeScale: {
                borderColor: '#475569',
                timeVisible: true,
                secondsVisible: false,
                visible: true,
                rightOffset: 50,
                fixLeftEdge: false,
                fixRightEdge: false
            },
        });
        rsiChartRef.current = rsiChart;

        // Sync all 3 time scales (Robust & Multi-directional)
        let isSyncing = false;
        const charts = [chart, volumeChart, rsiChart].filter(Boolean);

        try {
            charts.forEach(sourceChart => {
                // Use LogicalRange for more stable internal index syncing
                sourceChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
                    if (isSyncing || !range) return;
                    isSyncing = true;
                    try {
                        charts.forEach(targetChart => {
                            if (targetChart !== sourceChart) {
                                targetChart.timeScale().setVisibleLogicalRange(range);
                            }
                        });
                    } catch (err) {
                        console.warn("Logical range sync error:", err);
                    }
                    isSyncing = false;
                });

                // Synchronize crosshair (vertical time line only)
                sourceChart.subscribeCrosshairMove(param => {
                    if (isSyncing) return;
                    isSyncing = true;
                    try {
                        const syncTime = param.time;
                        charts.forEach(targetChart => {
                            if (targetChart !== sourceChart) {
                                if (!param.point || !syncTime) {
                                    targetChart.setCrosshairPosition(undefined, undefined, undefined);
                                } else {
                                    // Set crosshair position by time (vertical sync)
                                    targetChart.setCrosshairPosition(undefined, syncTime, undefined);
                                }
                            }
                        });
                    } catch (err) {
                        console.warn("Crosshair sync error:", err);
                    }
                    isSyncing = false;
                });
            });
        } catch (err) {
            console.error("Critical Chart Sync Error:", err);
        }

        // Add candlestick series
        const candlestickSeries = chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderUpColor: '#10b981',
            borderDownColor: '#ef4444',
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        const tvData = chartData.map(d => ({
            time: new Date(d.date).getTime() / 1000,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        })).filter(d => d.open && d.high && d.low && d.close);

        candlestickSeries.setData(tvData);
        tvDataRef.current = tvData; // Store in ref for event handlers

        // Add EMAs
        const addEMA = (color, field, title, lineWidth = 2) => {
            const series = chart.addLineSeries({ color, lineWidth, title });
            const data = chartData.filter(d => d[field]).map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d[field],
            }));
            if (data.length > 0) series.setData(data);
        };

        addEMA('#22c55e', 'ema_8', 'EMA 8');
        addEMA('#f59e0b', 'ema_21', 'EMA 21');
        addEMA('#8b5cf6', 'ema_35', 'EMA 35');
        addEMA('#ef4444', 'ema_200', 'EMA 200', 2);

        // Add Volume in its own dedicated panel
        const volumeSeries = volumeChart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: '', // Show on right scale
            scaleMargins: { top: 0.1, bottom: 0 },
        });

        const volumeData = chartData.filter(d => d.volume).map(d => ({
            time: new Date(d.date).getTime() / 1000,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)',
        }));
        if (volumeData.length > 0) volumeSeries.setData(volumeData);

        // Remove Elliott Wave markers per user request for cleaner view

        // Price lines (Only if > 0)
        const addPriceLine = (price, color, title, lineStyle = 0) => {
            if (price > 0) {
                candlestickSeries.createPriceLine({
                    price: price,
                    color: color,
                    lineWidth: 2,
                    lineStyle: lineStyle,
                    axisLabelVisible: true,
                    title: title,
                });
            }
        };

        addPriceLine(metrics.entry, '#3b82f6', 'ENTRY', 2);
        addPriceLine(metrics.stop_loss, '#ef4444', 'SL', 0); // Solid RED
        addPriceLine(metrics.target, '#22c55e', 'TP1', 0);  // Solid GREEN
        addPriceLine(metrics.target2, '#22c55e', 'TP2', 0); // Solid GREEN
        addPriceLine(metrics.target3, '#22c55e', 'TP3', 0); // Solid GREEN

        // Execution Markers (Buy/Sell history)
        if (tradeHistory && tradeHistory.length > 0) {
            markersRef.current = tradeHistory.map(trade => ({
                time: new Date(trade.time).getTime() / 1000,
                position: trade.side === 'BUY' ? 'belowBar' : 'aboveBar',
                color: trade.side === 'BUY' ? '#10b981' : '#ef4444',
                shape: trade.side === 'BUY' ? 'arrowUp' : 'arrowDown',
                text: `${trade.side} @ ${trade.price}`,
                size: 2,
            }));
            candlestickSeries.setMarkers(markersRef.current);
        }

        // Prediction Series (Momentum Path)
        if (chartData.some(d => d.is_projection)) {
            const predictionSeries = chart.addLineSeries({
                color: 'rgba(56, 189, 248, 0.7)',
                lineWidth: 3,
                lineStyle: 2, // Dashed: 0=solid, 1=dotted, 2=dashed, 3=large dashed
                title: 'Momentum Path',
            });
            const projData = chartData.filter(d => d.is_projection).map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d.projected,
            }));
            // Connect to last real candle
            const lastCandle = tvData[tvData.length - 1];
            if (lastCandle) {
                predictionSeries.setData([{ time: lastCandle.time, value: lastCandle.close }, ...projData]);
            } else {
                predictionSeries.setData(projData);
            }
        }

        // Clear drawing series references (they'll be recreated)
        drawingsRef.current = [];

        // Filter and validate drawings before rendering
        const validDrawings = drawings.filter(d => {
            if (!d || !d.type) return false;
            if (d.type === 'trendline') {
                // Validate that we have valid start and end points
                return d.start && d.end &&
                    d.start.time && d.end.time &&
                    typeof d.start.price === 'number' &&
                    typeof d.end.price === 'number' &&
                    !isNaN(d.start.price) && !isNaN(d.end.price);
            }
            if (d.type === 'horizontal') {
                return typeof d.price === 'number' && !isNaN(d.price);
            }
            if (d.type === 'ray') {
                return d.start && d.start.time && typeof d.start.price === 'number' && !isNaN(d.start.price);
            }
            if (d.type === 'label') {
                return d.time && typeof d.price === 'number' && !isNaN(d.price) && d.text;
            }
            return false;
        });

        validDrawings.forEach((d, idx) => {
            try {
                if (d.type === 'trendline') {
                    const s = chart.addLineSeries({
                        color: '#fbbf24',
                        lineWidth: 2,
                        lineStyle: 0,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    s.setData([
                        { time: d.start.time, value: d.start.price },
                        { time: d.end.time, value: d.end.price }
                    ]);
                    drawingsRef.current.push(s);
                }
                if (d.type === 'horizontal') {
                    // Horizontal line - use createPriceLine for infinite horizontal line
                    const priceLine = candlestickSeries.createPriceLine({
                        price: d.price,
                        color: d.color || '#06b6d4',
                        lineWidth: 2,
                        lineStyle: 2, // dashed
                        axisLabelVisible: true,
                        title: d.label || 'Level',
                    });
                    drawingsRef.current.push({ type: 'priceline', ref: priceLine });
                }
                if (d.type === 'ray') {
                    // Ray - line from start point extending to far right
                    const lastTime = tvData[tvData.length - 1]?.time || d.start.time;
                    const futureTime = lastTime + (365 * 24 * 60 * 60); // Extend 1 year into future
                    const s = chart.addLineSeries({
                        color: d.color || '#a78bfa',
                        lineWidth: 2,
                        lineStyle: 0,
                        lastValueVisible: false,
                        priceLineVisible: false,
                    });
                    s.setData([
                        { time: d.start.time, value: d.start.price },
                        { time: futureTime, value: d.start.price }
                    ]);
                    drawingsRef.current.push(s);
                }
                if (d.type === 'label') {
                    // Label - add as marker
                    const marker = {
                        time: d.time,
                        position: 'inLine',
                        color: d.color || '#f59e0b',
                        shape: 'circle',
                        text: d.text,
                        size: 1,
                    };
                    const existingMarkers = candlestickSeries.markers() || [];
                    candlestickSeries.setMarkers([...existingMarkers, marker]);
                }
            } catch (e) {
                console.error('Error rendering drawing:', e, d);
            }
        });

        // If we filtered out invalid drawings, update localStorage
        if (validDrawings.length !== drawings.length) {
            console.log(`Cleaned ${drawings.length - validDrawings.length} invalid drawings`);
            localStorage.setItem(`drawings_${ticker}`, JSON.stringify(validDrawings));
            setDrawings(validDrawings);
        }

        // Click handler for drawing
        const handleChartClick = (param) => {
            if (!drawingMode || !param.point || !param.time) return;

            const price = candlestickSeries.coordinateToPrice(param.point.y);
            const time = param.time;

            if (drawingMode === 'trendline') {
                // TWO-CLICK with preview: point A then point B
                if (!tempPoint) {
                    // First click - set starting point
                    setTempPoint({ time, price });
                } else {
                    // Second click - finalize the line
                    const newDrawing = {
                        type: 'trendline',
                        start: tempPoint,
                        end: { time, price }
                    };
                    const updated = [...drawings, newDrawing];
                    setDrawings(updated);
                    localStorage.setItem(`drawings_${ticker}`, JSON.stringify(updated));
                    setTempPoint(null);
                    setDrawingMode(null);
                }
            }
            if (drawingMode === 'horizontal') {
                // Single click to add horizontal line
                const newDrawing = {
                    type: 'horizontal',
                    price: price,
                    color: '#06b6d4',
                    label: `Level ${price.toFixed(2)}`
                };
                const updated = [...drawings, newDrawing];
                setDrawings(updated);
                localStorage.setItem(`drawings_${ticker}`, JSON.stringify(updated));
                setDrawingMode(null);
            }
            if (drawingMode === 'ray') {
                // Single click to add ray from that point
                const newDrawing = {
                    type: 'ray',
                    start: { time, price },
                    color: '#a78bfa'
                };
                const updated = [...drawings, newDrawing];
                setDrawings(updated);
                localStorage.setItem(`drawings_${ticker}`, JSON.stringify(updated));
                setDrawingMode(null);
            }
            if (drawingMode === 'label') {
                // Prompt for label text
                const text = prompt('Enter label text:', 'Note');
                if (text) {
                    const newDrawing = {
                        type: 'label',
                        time: time,
                        price: price,
                        text: text,
                        color: '#f59e0b'
                    };
                    const updated = [...drawings, newDrawing];
                    setDrawings(updated);
                    localStorage.setItem(`drawings_${ticker}`, JSON.stringify(updated));
                }
                setDrawingMode(null);
            }
        };

        chart.subscribeClick(handleChartClick);

        // NO llamar fitContent() aquí para prevenir auto-scroll

        // RSI Chart - Color Coded Histogram
        if (chartData.some(d => d.rsi_weekly)) {
            const rsiSeries = rsiChart.addHistogramSeries({
                title: 'Weekly RSI',
                priceFormat: { type: 'price', precision: 1 },
            });

            const colorMap = {
                green: '#10b981', // Emerald 500
                blue: '#3b82f6',  // Blue 500
                pink: '#f472b6',  // Pink 400
                yellow: '#f59e0b', // Amber 500
                orange: '#f97316', // Orange 500
                red: '#ef4444'     // Red 500
            };

            const rsiData = chartData.filter(d => d.rsi_weekly).map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d.rsi_weekly,
                color: colorMap[d.rsi_color] || '#ffffff'
            }));
            rsiSeries.setData(rsiData);

            // Add a white line on top of the histogram for better readability
            const rsiLineSeries = rsiChart.addLineSeries({
                color: 'rgba(255, 255, 255, 0.8)',
                lineWidth: 1,
                lastValueVisible: false,
                priceLineVisible: false,
                crosshairMarkerVisible: true
            });
            rsiLineSeries.setData(rsiData.map(d => ({ time: d.time, value: d.value })));

            // Add RSI Levels (70, 30, 50) - Only show axis labels for 70 and 30 to avoid clutter
            const rsiLevels = [
                { price: 70, color: 'rgba(239, 68, 68, 0.4)', title: '', lineWidth: 1 },
                { price: 30, color: 'rgba(34, 197, 94, 0.4)', title: '', lineWidth: 1 },
                { price: 50, color: 'rgba(148, 163, 184, 0.1)', title: '', lineWidth: 1 }
            ];

            rsiLevels.forEach(level => {
                rsiSeries.createPriceLine({
                    price: level.price,
                    color: level.color,
                    lineWidth: level.lineWidth,
                    lineStyle: 2, // Dashed
                    axisLabelVisible: true,
                    title: level.title,
                });
            });

            if (chartData.some(d => d.rsi_sma_3)) {
                const rsiSma3Series = rsiChart.addLineSeries({
                    color: '#10b981', // Emerald
                    lineWidth: 1.5,
                    title: 'W.EMA 3',
                });
                const rsiSma3Data = chartData.filter(d => d.rsi_sma_3).map(d => ({
                    time: new Date(d.date).getTime() / 1000,
                    value: d.rsi_sma_3,
                }));
                rsiSma3Series.setData(rsiSma3Data);
            }

            if (chartData.some(d => d.rsi_sma_14)) {
                const rsiSma14Series = rsiChart.addLineSeries({
                    color: '#f43f5e', // Rose
                    lineWidth: 1.5,
                    title: 'W.EMA 14',
                });
                const rsiSma14Data = chartData.filter(d => d.rsi_sma_14).map(d => ({
                    time: new Date(d.date).getTime() / 1000,
                    value: d.rsi_sma_14,
                }));
                rsiSma14Series.setData(rsiSma14Data);
            }

            if (chartData.some(d => d.rsi_sma_21)) {
                const rsiSma21Series = rsiChart.addLineSeries({
                    color: '#8b5cf6', // Violet
                    lineWidth: 1,
                    lineStyle: 2, // Dashed
                    title: 'W.EMA 21',
                });
                const rsiSma21Data = chartData.filter(d => d.rsi_sma_21).map(d => ({
                    time: new Date(d.date).getTime() / 1000,
                    value: d.rsi_sma_21,
                }));
                rsiSma21Series.setData(rsiSma21Data);
            }

            // Removed redundant fitContent to preserve synced timescale across panels
        }

        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight,
                });
            }
            if (volumeContainerRef.current && volumeChartRef.current) {
                volumeChartRef.current.applyOptions({
                    width: volumeContainerRef.current.clientWidth,
                    height: volumeContainerRef.current.clientHeight,
                });
            }
            if (rsiContainerRef.current && rsiChartRef.current) {
                rsiChartRef.current.applyOptions({
                    width: rsiContainerRef.current.clientWidth,
                    height: rsiContainerRef.current.clientHeight,
                });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) chartRef.current.remove();
            if (volumeChartRef.current) volumeChartRef.current.remove();
            if (rsiChartRef.current) rsiChartRef.current.remove();
        };
    }, [chartData, elliottWave, metrics, tradeHistory, drawings, drawingMode, tempPoint]);

    // Keyboard shortcuts
    React.useEffect(() => {
        const handleKeyPress = (e) => {
            // Don't trigger if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key.toLowerCase()) {
                case 't':
                    setDrawingMode(prev => prev === 'trendline' ? null : 'trendline');
                    break;
                case 'h':
                    setDrawingMode(prev => prev === 'horizontal' ? null : 'horizontal');
                    break;
                case 'r':
                    setDrawingMode(prev => prev === 'ray' ? null : 'ray');
                    break;
                case 'l':
                    setDrawingMode(prev => prev === 'label' ? null : 'label');
                    break;
                case 'escape':
                    setDrawingMode(null);
                    setTempPoint(null);
                    break;
                case 'delete':
                    if (e.ctrlKey || e.metaKey) {
                        clearDrawings();
                    }
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, []);

    const clearDrawings = () => {
        setDrawings([]);
        localStorage.removeItem(`drawings_${ticker}`);
        setDrawingMode(null);
        setTempPoint(null);
    };

    return (
        <div className="relative" style={{ width: '100%', height: '100%', display: 'flex' }}>
            {/* Drawing Toolbar */}
            <div className="absolute left-4 top-4 z-10 flex flex-col gap-1.5 bg-gradient-to-br from-slate-800/95 to-slate-900/95 backdrop-blur-md p-2.5 rounded-xl border border-slate-600/50 shadow-2xl">
                {/* Header with count */}
                {drawings.length > 0 && (
                    <div className="flex items-center justify-between mb-1 pb-1.5 border-b border-slate-700">
                        <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Drawings</span>
                        <span className="bg-blue-500/20 text-blue-300 text-[10px] font-bold px-1.5 py-0.5 rounded">{drawings.length}</span>
                    </div>
                )}

                <button
                    onClick={() => setDrawingMode(drawingMode === 'trendline' ? null : 'trendline')}
                    className={`group relative w-11 h-11 flex items-center justify-center rounded-lg transition-all duration-200 text-lg ${drawingMode === 'trendline' ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/50 scale-105' : 'hover:bg-slate-700 text-slate-300 hover:text-white hover:scale-105'}`}
                    title="Trend Line (Hotkey: T)"
                >
                    ✏️
                    <span className="absolute -bottom-1 -right-1 bg-slate-900 text-[8px] text-slate-500 px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity font-mono">T</span>
                </button>
                <div className="h-px bg-gradient-to-r from-transparent via-slate-700 to-transparent my-0.5"></div>
                <button
                    onClick={() => setDrawingMode(drawingMode === 'horizontal' ? null : 'horizontal')}
                    className={`group relative w-11 h-11 flex items-center justify-center rounded-lg transition-all duration-200 text-lg ${drawingMode === 'horizontal' ? 'bg-cyan-500 text-white shadow-lg shadow-cyan-500/50 scale-105' : 'hover:bg-slate-700 text-slate-300 hover:text-white hover:scale-105'}`}
                    title="Horizontal Line (Hotkey: H)"
                >
                    ➖
                    <span className="absolute -bottom-1 -right-1 bg-slate-900 text-[8px] text-slate-500 px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity font-mono">H</span>
                </button>
                <button
                    onClick={() => setDrawingMode(drawingMode === 'ray' ? null : 'ray')}
                    className={`group relative w-11 h-11 flex items-center justify-center rounded-lg transition-all duration-200 text-lg ${drawingMode === 'ray' ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/50 scale-105' : 'hover:bg-slate-700 text-slate-300 hover:text-white hover:scale-105'}`}
                    title="Ray (Hotkey: R)"
                >
                    ➡️
                    <span className="absolute -bottom-1 -right-1 bg-slate-900 text-[8px] text-slate-500 px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity font-mono">R</span>
                </button>
                <button
                    onClick={() => setDrawingMode(drawingMode === 'label' ? null : 'label')}
                    className={`group relative w-11 h-11 flex items-center justify-center rounded-lg transition-all duration-200 text-lg ${drawingMode === 'label' ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/50 scale-105' : 'hover:bg-slate-700 text-slate-300 hover:text-white hover:scale-105'}`}
                    title="Add Label (Hotkey: L)"
                >
                    🏷️
                    <span className="absolute -bottom-1 -right-1 bg-slate-900 text-[8px] text-slate-500 px-1 rounded opacity-0 group-hover:opacity-100 transition-opacity font-mono">L</span>
                </button>
                <div className="h-px bg-gradient-to-r from-transparent via-slate-700 to-transparent my-0.5"></div>
                <button
                    onClick={clearDrawings}
                    className="group relative w-11 h-11 flex items-center justify-center rounded-lg hover:bg-red-900/50 text-red-400 hover:text-red-300 border border-transparent hover:border-red-700/50 transition-all duration-200 text-lg hover:scale-105"
                    title="Clear All Drawings (Hotkey: Ctrl+Del)"
                >
                    🗑️
                    <span className="absolute -bottom-1 -right-1 bg-slate-900 text-[7px] text-slate-500 px-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity font-mono">⌫</span>
                </button>
                {drawingMode && (
                    <div className="absolute left-16 top-0 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-[10px] px-3 py-1.5 rounded-lg whitespace-nowrap font-bold shadow-xl animate-pulse">
                        {drawingMode === 'trendline' && (tempPoint ? "Click Second Point" : "Click First Point")}
                        {drawingMode === 'horizontal' && "Click Price Level"}
                        {drawingMode === 'ray' && "Click Starting Point"}
                        {drawingMode === 'label' && "Click to Add Label"}
                        <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-gradient-to-r from-blue-600 to-purple-600 rotate-45"></div>
                    </div>
                )}
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div ref={chartContainerRef} style={{ width: '100%', height: '60%' }} />
                <div ref={volumeContainerRef} style={{ width: '100%', height: '20%', borderTop: '1px solid #334155' }} />
                <div ref={rsiContainerRef} style={{ width: '100%', height: '20%', borderTop: '1px solid #334155' }} />
            </div>
        </div>
    );
}

function MetricCard({ label, value, subtext, color = "text-white", className = "" }) {
    return (
        <div className={`bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-xl transition-all hover:scale-[1.02] hover:bg-slate-700/50 ${className}`}>
            <div className="text-slate-400 text-[10px] uppercase tracking-[0.2em] font-black mb-3 opacity-60">{label}</div>
            <div className={`text-3xl font-black tracking-tight ${color}`}>{value}</div>
            {subtext && <div className="text-[10px] text-slate-500 font-medium mt-2 flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-slate-600"></span>
                {subtext}
            </div>}
        </div>
    );
}


function DetailView({ ticker, onClose, overrideMetrics }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const chartContainerRef = React.useRef(null);
    const [chartDimensions, setChartDimensions] = React.useState(null);

    useEffect(() => {
        setLoading(true);
        axios.post(`${API_BASE}/analyze`, { ticker })
            .then(res => {
                if (res.data.error) {
                    alert(res.data.error);
                    onClose();
                } else {
                    // If overrideMetrics provided and backend returns zeros, use overrides
                    if (overrideMetrics && res.data.metrics) {
                        const m = res.data.metrics;
                        if (m.entry === 0 || m.target === 0 || m.stop_loss === 0) {
                            res.data.metrics = {
                                ...m,
                                entry: overrideMetrics.entry || m.entry,
                                target: overrideMetrics.target || m.target,
                                stop_loss: overrideMetrics.stop_loss || m.stop_loss
                            };
                        }
                    }
                    setData(res.data);
                }
            })
            .catch(err => {
                console.error(err);
                alert("Error analyzing ticker");
            })
            .finally(() => setLoading(false));
    }, [ticker]);

    const handleAddToWatchlist = async () => {
        try {
            const currentPrice = data?.chart_data?.[data.chart_data.length - 1]?.close || 0;
            const payload = {
                ticker: ticker.toUpperCase(),
                entry_price: currentPrice,
                alert_price: data?.metrics?.entry || null,
                stop_alert: data?.metrics?.stop_loss || null,
                strategy: data?.metrics?.is_bull_flag ? 'Bull Flag' : 'Manual Analysis',
                notes: 'Added from Details'
            };

            const response = await authFetch('/api/watchlist/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                alert(`${ticker} agregado al Watchlist!`);
            } else {
                const err = await response.json();
                alert(`Error: ${err.detail || 'No se pudo agregar'}`);
            }
        } catch (e) {
            console.error(e);
            alert("Error al conectar con la API de Watchlist");
        }
    };

    // Update chart dimensions when data loads
    React.useEffect(() => {
        if (!chartContainerRef.current || !data) return;

        const updateDims = () => {
            const rect = chartContainerRef.current.getBoundingClientRect();
            setChartDimensions({ width: rect.width, height: rect.height });
        };

        // Small delay to ensure chart is rendered
        setTimeout(updateDims, 100);
        window.addEventListener('resize', updateDims);
        return () => window.removeEventListener('resize', updateDims);
    }, [data]);

    if (loading) return (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center backdrop-blur-sm">
            <div className="text-blue-400 text-xl animate-pulse">Analyzing Market Structure...</div>
        </div>
    );

    if (!data) return null;

    const { metrics, chart_data } = data;

    // Ensure metrics has required fields with defaults
    // If overrideMetrics provided, be more lenient
    const hasOverrides = overrideMetrics && (overrideMetrics.entry || overrideMetrics.target || overrideMetrics.stop_loss);

    // Relaxed validation: Require chart_data, but allow zero metrics (common for indices)
    if (!chart_data || chart_data.length === 0) {
        return (
            <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center backdrop-blur-sm">
                <div className="text-red-400 text-xl">No chart data available for {ticker}</div>
            </div>
        );
    }

    // Calculate min/max for Y-axis scaling (Ignore zeros for stops/targets)
    const prices = chart_data.map(d => d.low);
    const validMetrics = [metrics.stop_loss, metrics.target].filter(v => v > 0);
    const minPrice = Math.min(...prices, ...validMetrics) * 0.95;
    const maxPrice = Math.max(...chart_data.map(d => d.high), ...validMetrics) * 1.05;

    return (
        <div className="fixed inset-0 z-50 bg-slate-900/95 flex flex-col p-6 overflow-hidden">
            {/* Header */}
            <div className="flex justify-between items-start mb-6">
                <div>
                    <div className="flex items-center gap-4">
                        <h2 className="text-4xl font-bold text-white tracking-tight">{ticker}</h2>
                        {/* Grade Badge */}
                        {data.grade && (
                            <div className={`px-6 py-3 rounded-lg border-2 ${data.grade === 'A' ? 'bg-green-900/30 border-green-500 text-green-400' :
                                data.grade === 'B' ? 'bg-blue-900/30 border-blue-500 text-blue-400' :
                                    data.grade === 'C' ? 'bg-yellow-900/30 border-yellow-500 text-yellow-400' :
                                        'bg-slate-800/50 border-slate-600 text-slate-400'
                                }`}>
                                <div className="text-xs uppercase tracking-wide opacity-75">Setup Quality</div>
                                <div className="text-5xl font-black">{data.grade}</div>
                            </div>
                        )}
                    </div>
                    <div className="flex gap-4 mt-2">
                        {/* Cleanup: Removed technical badges for cleaner analysis */}
                    </div>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={handleAddToWatchlist}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-indigo-900/20 transition flex items-center gap-2"
                    >
                        <span>⭐</span> Add to Watchlist
                    </button>
                    <button
                        onClick={onClose}
                        className="bg-slate-800 hover:bg-slate-700 text-white px-6 py-2 rounded-lg border border-slate-600 transition flex items-center gap-2 font-bold"
                    >
                        <span>✕</span> Close
                    </button>
                </div>
            </div>

            {/* Content Component Grid - Cleanup: Occupy full width */}
            <div className="flex-1 grid grid-cols-12 gap-6 min-h-0">
                <div className="col-span-12 bg-slate-800 rounded-xl border border-slate-700 p-4 flex flex-col">
                    <div className="flex-1 w-full min-h-0">
                        <TradingViewChart
                            ticker={ticker}
                            chartData={chart_data}
                            elliottWave={data.elliott_wave}
                            metrics={metrics}
                            tradeHistory={data.trade_history}
                        />
                    </div>
                </div>
            </div>
        </div >
    );
}

// Watchlist Tab Component
function WatchlistTab({ onTickerClick }) {
    const [watchlist, setWatchlist] = useState([]);
    const [newTicker, setNewTicker] = useState('');
    const [newHypothesis, setNewHypothesis] = useState('');
    const [loading, setLoading] = useState(true);
    const [premarket, setPremarket] = useState({});

    const fetchWatchlist = async () => {
        try {
            const res = await axios.get(`${API_BASE}/watchlist`);
            setWatchlist(res.data);
            // Fetch pre-market for all tickers
            res.data.forEach(item => fetchPremarket(item.ticker));
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchPremarket = async (ticker) => {
        try {
            const res = await axios.get(`${API_BASE}/premarket/${ticker}`);
            setPremarket(prev => ({ ...prev, [ticker]: res.data }));
        } catch (e) {
            console.error(`Error fetching premarket for ${ticker}:`, e);
        }
    };

    useEffect(() => {
        fetchWatchlist();
        const interval = setInterval(fetchWatchlist, 60000); // Refresh every minute
        return () => clearInterval(interval);
    }, []);

    const handleAdd = async (e) => {
        e.preventDefault();
        if (!newTicker.trim()) return;

        try {
            await axios.post(`${API_BASE}/watchlist`, {
                ticker: newTicker.toUpperCase(),
                hypothesis: newHypothesis
            });
            setNewTicker('');
            setNewHypothesis('');
            fetchWatchlist();
        } catch (e) {
            alert('Error adding ticker');
            console.error(e);
        }
    };

    const handleDelete = async (ticker) => {
        if (!confirm(`Remove ${ticker} from watchlist?`)) return;
        try {
            await axios.delete(`${API_BASE}/watchlist/${ticker}`);
            fetchWatchlist();
        } catch (e) {
            console.error(e);
        }
    };

    if (loading) return <div className="p-8 text-center text-slate-500">Loading...</div>;

    return (
        <div className="p-6 container mx-auto max-w-7xl">
            <div className="flex justify-between items-start mb-8">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                        ⭐️ Watchlist
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">Track tickers with custom hypotheses and pre-market data</p>
                </div>
                <div className="text-sm text-slate-500">
                    Auto-refreshes every minute
                </div>
            </div>

            {/* Add Form */}
            <div className="bg-slate-800 p-6 rounded-xl border border-slate-700 mb-6">
                <h3 className="text-slate-300 font-bold mb-4">Add to Watchlist</h3>
                <form onSubmit={handleAdd} className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs text-slate-400 uppercase font-bold block mb-2">Ticker Symbol</label>
                            <input
                                type="text"
                                value={newTicker}
                                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                                placeholder="e.g. NVDA"
                                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500 uppercase"
                                required
                            />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 uppercase font-bold block mb-2">Hypothesis / Notes</label>
                            <input
                                type="text"
                                value={newHypothesis}
                                onChange={(e) => setNewHypothesis(e.target.value)}
                                placeholder="e.g. Breakout above resistance"
                                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                            />
                        </div>
                    </div>
                    <button
                        type="submit"
                        className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-blue-900/20 transition"
                    >
                        Add to Watchlist
                    </button>
                </form>
            </div>

            {/* Watchlist Table */}
            {watchlist.length === 0 ? (
                <div className="text-center py-20 border-2 border-dashed border-slate-800 rounded-xl">
                    <div className="text-4xl mb-4">⭐️</div>
                    <p className="text-slate-500 text-lg">Your watchlist is empty</p>
                    <p className="text-slate-600 text-sm">Add tickers manually or from Scanner/Options</p>
                </div>
            ) : (
                <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                    <table className="w-full text-left">
                        <thead className="bg-slate-900 text-slate-400 text-xs uppercase font-bold">
                            <tr>
                                <th className="p-4">Ticker</th>
                                <th className="p-4">Hypothesis</th>
                                <th className="p-4 text-center">Pre-Market</th>
                                <th className="p-4 text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700">
                            {watchlist.map(item => {
                                const pm = premarket[item.ticker];
                                const pmChange = pm?.extended_change_pct;
                                const pmColor = pmChange > 0 ? 'text-green-400' : pmChange < 0 ? 'text-red-400' : 'text-slate-400';

                                return (
                                    <tr key={item.ticker} className="hover:bg-slate-700/30 transition">
                                        <td className="p-4">
                                            <button
                                                onClick={() => onTickerClick(item.ticker)}
                                                className="font-bold text-white hover:text-blue-400 transition"
                                            >
                                                {item.ticker}
                                            </button>
                                        </td>
                                        <td className="p-4 text-slate-300 text-sm">
                                            {item.hypothesis || <span className="italic text-slate-600">No hypothesis</span>}
                                        </td>
                                        <td className="p-4 text-center">
                                            {pmChange !== null && pmChange !== undefined ? (
                                                <div className={`font-bold ${pmColor}`}>
                                                    {pmChange > 0 ? '+' : ''}{pmChange}%
                                                    {pm.is_premarket && <span className="text-[10px] ml-1 opacity-60">(pre)</span>}
                                                    {pm.is_postmarket && <span className="text-[10px] ml-1 opacity-60">(post)</span>}
                                                </div>
                                            ) : (
                                                <span className="text-slate-600 text-sm">—</span>
                                            )}
                                        </td>
                                        <td className="p-4 text-center">
                                            <button
                                                onClick={() => handleDelete(item.ticker)}
                                                className="text-slate-500 hover:text-red-400 text-sm transition px-2"
                                            >
                                                Remove
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Watchlist News Section */}
            {watchlist.length > 0 && (
                <div className="mt-6">
                    <PortfolioNewsWidget tickers={watchlist.map(w => w.ticker)} />
                </div>
            )}
        </div>
    );
}

// Algorithmic Scanner Component
function Scanner({ onTickerClick }) {
    const [results, setResults] = useState([]);
    const [stats, setStats] = useState(null);
    const [scanning, setScanning] = useState(false);
    const [limit, setLimit] = useState(20000);
    const [progress, setProgress] = useState({ total: 0, current: 0 });
    const [sortConfig, setSortConfig] = useState({ key: 'score', direction: 'desc' });
    const [strategy, setStrategy] = useState('weekly_rsi');

    const [showAboveSMA, setShowAboveSMA] = useState(false);

    useEffect(() => {
        let interval;
        if (scanning) {
            interval = setInterval(async () => {
                try {
                    const res = await axios.get(`${API_BASE}/scan/progress`);
                    setProgress(res.data);

                    // If scan finished while we were polling, capture results
                    if (res.data.is_running === false) {
                        setScanning(false);
                        if (res.data.results && Array.isArray(res.data.results)) {
                            // Only update if we haven't already (or if we want to overwrite)
                            if (results.length === 0 || res.data.results.length !== results.length) {
                                setResults(res.data.results);
                                setStats({
                                    scanned: res.data.scanned || (res.data.total > 0 ? res.data.total : 0),
                                    count: res.data.results.length,
                                    spy_ret_3m: res.data.spy_ret_3m || 0
                                });
                            }
                        }
                    }
                } catch (e) {
                    console.error("Error fetching progress", e);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [scanning, results.length]);

    const runScan = async () => {
        setScanning(true);
        setResults([]);
        setStats(null);
        setProgress({ total: 0, current: 0 });
        try {
            const res = await axios.post(`${API_BASE}/scan`, { limit, strategy });
            // The scan is now backgrounded, we don't expect results in the POST response
            if (res.data && res.data.status === "scanning") {
                // Set total immediately so progress bar appears
                setProgress({ total: res.data.limit || limit, current: 0 });
            } else {
                if (res.data && res.data.error) alert("Scan Error: " + res.data.error);
                setScanning(false);
            }
        } catch (e) {
            console.error(e);
            alert("Scan failed to initiate: " + (e.response?.data?.detail || e.message));
            setScanning(false);
        }
    };

    const handleCancelScan = () => {
        alert("Cancel feature coming soon!");
        setScanning(false);
    };

    const handleSort = (key) => {
        let direction = 'desc';
        if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = 'asc';
        }
        setSortConfig({ key, direction });
    };

    const sortedResults = useMemo(() => {
        let sortableItems = [...results];

        // Filter: Show Only > SMA200 if enabled
        if (showAboveSMA) {
            sortableItems = sortableItems.filter(item => item.sma200_d && item.price > item.sma200_d);
        }

        if (sortConfig.key !== null) {
            sortableItems.sort((a, b) => {
                let aVal = a[sortConfig.key];
                let bVal = b[sortConfig.key];
                if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
                if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
                return 0;
            });
        }
        return sortableItems;
    }, [results, sortConfig, showAboveSMA]);

    const handleDownloadPDF = () => {
        if (!sortedResults.length) return;

        try {
            if (!window.jspdf) {
                alert("PDF library not loaded yet. Please refresh the page.");
                return;
            }
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF();

            const tableColumn = ["Ticker", "Score", "Price", "RSI", "MACD", "EMA60", "DMI (+/-)", "Vol Ratio"];
            const tableRows = [];

            sortedResults.forEach(ticket => {
                const ticketData = [
                    ticket.ticker,
                    ticket.score,
                    ticket.price?.toFixed(2),
                    ticket.rsi?.toFixed(2),
                    ticket.macd_d?.toFixed(2),
                    ticket.ema60_d?.toFixed(2),
                    `${ticket.di_plus?.toFixed(0)} / ${ticket.di_minus?.toFixed(0)}`,
                    `${ticket.vol_ratio?.toFixed(1)}x`
                ];
                tableRows.push(ticketData);
            });

            doc.setFontSize(18);
            doc.text("Weekly RSI Scanner Results", 14, 15);

            doc.setFontSize(10);
            doc.setTextColor(100);
            doc.text(`Generated on: ${new Date().toLocaleString()}`, 14, 22);
            doc.text(`Strategy: Weekly RSI Reversal (30-50) + Bullish EMA Trend`, 14, 27);
            doc.text(`Total Candidates: ${sortedResults.length}`, 14, 32);

            doc.autoTable({
                head: [tableColumn],
                body: tableRows,
                startY: 40,
                styles: { fontSize: 8, cellPadding: 2 },
                headStyles: { fillColor: [41, 128, 185], textColor: 255, fontStyle: 'bold' },
                alternateRowStyles: { fillColor: [240, 240, 240] },
                margin: { top: 40 }
            });

            doc.save(`momentum_scan_${new Date().toISOString().slice(0, 10)}.pdf`);
        } catch (error) {
            console.error("PDF Generation Error:", error);
            alert("Failed to generate PDF. Make sure libraries are loaded.");
        }
    };

    const handleDownloadExcel = () => {
        if (!sortedResults.length) return;

        try {
            if (!window.XLSX) {
                alert("Excel library not loaded yet. Please refresh the page.");
                return;
            }
            const XLSX = window.XLSX;

            // Prepare data for Excel
            const dataToExport = sortedResults.map(ticket => ({
                "Ticker": ticket.ticker,
                "Score": ticket.score,
                "Price": ticket.price,
                "RSI (Weekly)": ticket.rsi,
                "MACD": ticket.macd_d,
                "EMA60": ticket.ema60_d,
                "DMI+": ticket.di_plus,
                "DMI-": ticket.di_minus,
                "ADX": ticket.adx,
                "Volume Ratio": ticket.vol_ratio,
                "Bullish Trend": ticket.is_bullish ? "Yes" : "No",
                "Stars": ticket.stars || 1,
                "Sector": ticket.sector || "Unknown"
            }));

            // Create Worksheet
            const ws = XLSX.utils.json_to_sheet(dataToExport);

            // Create Workbook
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, "Scanner Results");

            // Save File
            XLSX.writeFile(wb, `momentum_scan_${new Date().toISOString().slice(0, 10)}.xlsx`);

        } catch (error) {
            console.error("Excel Generation Error:", error);
            alert("Failed to generate Excel. Make sure libraries are loaded.");
        }
    };

    const renderTable = (data, title, colorClass, icon) => (
        <div className={`overflow-hidden rounded-xl border border-slate-700 shadow-xl ${colorClass === 'green' ? 'shadow-green-900/10' : 'shadow-red-900/10'}`}>
            <div className={`px-4 py-3 border-b border-slate-700 flex items-center justify-between ${colorClass === 'green' ? 'bg-green-900/20' : 'bg-red-900/20'}`}>
                <h3 className={`font-bold text-lg flex items-center gap-2 ${colorClass === 'green' ? 'text-green-400' : 'text-red-400'}`}>
                    {icon} {title}
                </h3>
                <span className="text-xs text-slate-400 bg-slate-800 px-2 py-1 rounded">{data.length} Signals</span>
            </div>
            <div className="overflow-x-auto bg-slate-800">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-900 text-slate-400 uppercase font-bold text-xs">
                        <tr>
                            <th className="p-2 cursor-pointer hover:text-white transition" onClick={() => handleSort('ticker')}>
                                Ticker
                            </th>
                            <th className="p-2 text-center text-orange-400 cursor-pointer hover:text-white transition" onClick={() => handleSort('stars')}>
                                Stars
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('price')}>
                                Price
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('rsi')}>
                                RSI(W)
                            </th>
                            <th className="p-2 text-center cursor-pointer hover:text-white transition" title="W.RSI Phase (6-tier)" onClick={() => handleSort('rsi_color')}>
                                Phase
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('smi')}>
                                SMI(W)
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('macd_d')}>
                                MACD
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('ema60_d')}>
                                EMA60
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('sma200_d')}>
                                SMA200
                            </th>
                            <th className="p-2 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('di_plus')}>
                                DMI & Strength
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('vol_ratio')}>
                                Vol
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('vol_week_vs_month')} title="Volume: Weekly (5d) vs Monthly (21d) Avg">
                                Vol W/M
                            </th>
                            <th className="p-2 text-center cursor-pointer hover:text-white transition text-purple-400" onClick={() => handleSort('stage')} title="Weinstein Stage (1-4)">
                                Stage
                            </th>
                            <th className="p-2 text-center" title="52-Week Range Position">
                                52w
                            </th>
                            <th className="p-2 text-center text-blue-400" title="DI+ > DI- Alignment (D/W)">
                                DI
                            </th>
                            <th className="p-2 text-center cursor-pointer hover:text-white transition text-green-400" onClick={() => handleSort('momentum_score')} title="Momentum Score (0-100)">
                                Score
                            </th>
                            <th className="p-2 text-center">Chart</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {data.map((row, idx) => (
                            <tr key={idx} className="hover:bg-slate-700/50 transition duration-150">
                                <td className="p-2 cursor-pointer group" onClick={() => onTickerClick(row.ticker)}>
                                    <div className="font-bold text-white group-hover:text-blue-400 transition">{row.ticker}</div>
                                    <div className="text-[9px] text-slate-500 truncate max-w-[60px]">{row.sector || 'Other'}</div>
                                </td>
                                <td className="p-2 text-center text-xs whitespace-nowrap">
                                    {'⭐'.repeat(row.stars || 1)}
                                </td>
                                <td className="p-2 text-right font-mono text-white text-xs">${row.price?.toFixed(2)}</td>
                                <td className={`p-2 text-right font-bold text-xs ${row.rsi < 35 ? 'text-green-400' : 'text-blue-300'}`}>
                                    {row.rsi?.toFixed(1)}
                                </td>
                                {/* W.RSI Phase */}
                                <td className="p-2 text-center">
                                    {(() => {
                                        const colorMap = {
                                            green: 'bg-green-500',
                                            blue: 'bg-blue-500',
                                            yellow: 'bg-yellow-500',
                                            orange: 'bg-orange-500',
                                            pink: 'bg-pink-400',
                                            red: 'bg-red-500',
                                            gray: 'bg-slate-600'
                                        };
                                        const labelMap = {
                                            green: 'Strong',
                                            blue: 'Accum',
                                            yellow: 'Pull↑',
                                            orange: 'Pull↓',
                                            pink: 'Corr',
                                            red: 'Bear',
                                            gray: '-'
                                        };
                                        const c = row.rsi_color || 'gray';
                                        return (
                                            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold text-white ${colorMap[c]}`}>
                                                {labelMap[c]}
                                            </span>
                                        );
                                    })()}
                                </td>
                                <td className={`p-2 text-right font-bold text-xs ${row.smi_bullish ? 'text-green-400' : 'text-red-400'}`}>
                                    {row.smi?.toFixed(1)}
                                </td>
                                <td className="p-2 text-right text-xs font-mono">
                                    <span className={row.macd_d > 0 ? 'text-green-400' : 'text-red-400'}>
                                        {row.macd_d?.toFixed(2)}
                                    </span>
                                </td>
                                <td className={`p-2 text-right font-mono text-xs ${row.price > row.ema60_d ? 'text-green-400 font-bold' : 'text-slate-500'}`}>
                                    {row.ema60_d?.toFixed(0)}
                                </td>
                                <td className={`p-2 text-right font-mono text-xs ${row.sma200_d && row.price > row.sma200_d ? 'text-green-400 font-bold' : 'text-red-400'}`}>
                                    {row.sma200_d ? row.sma200_d.toFixed(0) : '-'}
                                </td>
                                <td className="p-2 text-center">
                                    <div className={`text-[10px] font-bold ${row.is_bullish ? 'text-green-400' : 'text-slate-500'}`}>
                                        {row.di_plus > row.di_minus ? 'BULL' : 'NEUT'} {row.di_plus_above_adx ? '⚡' : ''}
                                    </div>
                                    <div className="text-[9px] text-slate-500 font-mono">
                                        {row.di_plus?.toFixed(0)}/{row.di_minus?.toFixed(0)}/{row.adx?.toFixed(0)}
                                    </div>
                                </td>
                                <td className={`p-2 text-right font-bold text-xs ${row.is_vol_growing ? 'text-orange-400' : 'text-slate-500'}`}>
                                    {row.vol_ratio?.toFixed(1)}x
                                </td>
                                {/* Vol Week vs Month */}
                                <td className={`p-2 text-right font-bold text-xs ${row.vol_week_vs_month > 1.1 ? 'text-green-400' :
                                    row.vol_week_vs_month > 1.0 ? 'text-yellow-400' :
                                        row.vol_week_vs_month < 0.9 ? 'text-red-400' : 'text-slate-500'
                                    }`}>
                                    {row.vol_week_vs_month ? `${row.vol_week_vs_month.toFixed(2)}x` : '-'}
                                </td>
                                {/* Stage */}
                                <td className="p-2 text-center">
                                    {(() => {
                                        const stage = row.stage;
                                        if (!stage || stage.stage === 0) return <span className="text-slate-600">-</span>;
                                        const colors = {
                                            blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
                                            green: 'bg-green-500/20 text-green-400 border-green-500/30',
                                            yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
                                            red: 'bg-red-500/20 text-red-400 border-red-500/30',
                                            gray: 'bg-slate-500/20 text-slate-400 border-slate-500/30'
                                        };
                                        return (
                                            <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${colors[stage.color] || colors.gray}`} title={stage.label}>
                                                S{stage.stage}
                                            </span>
                                        );
                                    })()}
                                </td>
                                {/* 52w Range */}
                                <td className="p-2 text-center" style={{ minWidth: '50px' }}>
                                    {(() => {
                                        const range = row.range_52w;
                                        if (!range || range.high === 0) return <span className="text-slate-600">-</span>;
                                        const pct = range.position_pct;
                                        const color = pct > 70 ? 'bg-green-500' : pct > 30 ? 'bg-yellow-500' : 'bg-red-500';
                                        return (
                                            <div className="relative w-full h-2 bg-slate-700 rounded-full overflow-hidden" title={`$${range.low} - $${range.high} (${pct.toFixed(0)}%)`}>
                                                <div className={`absolute h-3 w-1 ${color} rounded-full -top-0.5`} style={{ left: `${Math.min(95, Math.max(5, pct))}%` }}></div>
                                            </div>
                                        );
                                    })()}
                                </td>
                                {/* DI Alignment (D/W) */}
                                <td className="p-2 text-center">
                                    {(() => {
                                        const di = row.di_alignment;
                                        if (!di) return <span className="text-slate-600">-</span>;
                                        return (
                                            <div className="flex gap-0.5 justify-center">
                                                <span className={`px-1 py-0.5 rounded text-[8px] font-bold ${di.d1 === true ? 'bg-green-500/20 text-green-400' : di.d1 === false ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-500'}`}>D</span>
                                                <span className={`px-1 py-0.5 rounded text-[8px] font-bold ${di.w1 === true ? 'bg-green-500/20 text-green-400' : di.w1 === false ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-500'}`}>W</span>
                                            </div>
                                        );
                                    })()}
                                </td>
                                {/* Momentum Score */}
                                <td className="p-2 text-center">
                                    {(() => {
                                        const score = row.momentum_score;
                                        if (score === undefined || score === null) return <span className="text-slate-600">-</span>;
                                        let colorClass = 'text-red-400';
                                        if (score >= 70) colorClass = 'text-green-400';
                                        else if (score >= 40) colorClass = 'text-yellow-400';
                                        return <span className={`font-bold ${colorClass}`}>{score}</span>;
                                    })()}
                                </td>
                                <td className="p-2 text-center">
                                    <button
                                        onClick={() => onTickerClick(row.ticker)}
                                        className="bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white px-2 py-0.5 rounded text-[10px] transition border border-blue-600/30"
                                    >
                                        Go
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );

    return (
        <div className="p-6 container mx-auto max-w-7xl animate-fade-in">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        Weekly RSI Market Scanner
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">Detecting Early Reversals (30-50 RSI) with EMA(3/14) Bullish Alignment.</p>
                </div>
                <div className="flex gap-4 items-center">
                    <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2">
                        <input
                            type="checkbox"
                            id="smaFilter"
                            checked={showAboveSMA}
                            onChange={(e) => setShowAboveSMA(e.target.checked)}
                            className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-600 ring-offset-gray-800"
                        />
                        <label htmlFor="smaFilter" className="text-slate-300 text-sm cursor-pointer select-none">
                            Show &gt; SMA200
                        </label>
                    </div>

                    <select
                        value={strategy}
                        onChange={(e) => setStrategy(e.target.value)}
                        className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2"
                    >
                        <option value="weekly_rsi">📊 Weekly RSI</option>
                        <option value="vcp">🔺 VCP (Minervini)</option>
                    </select>

                    <select
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2"
                    >
                        <option value="10000">Min Vol: 10k</option>
                        <option value="50000">Min Vol: 50k</option>
                        <option value="100000">Min Vol: 100k</option>
                        <option value="500000">Min Vol: 500k</option>
                    </select>

                    {sortedResults.length > 0 && (
                        <>
                            <button
                                onClick={handleDownloadExcel}
                                className="bg-green-700 hover:bg-green-600 text-white px-4 py-2 rounded-lg font-medium shadow-lg transition flex items-center gap-2"
                            >
                                <span>📗</span> Excel
                            </button>
                            <button
                                onClick={handleDownloadPDF}
                                className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg font-medium shadow-lg transition flex items-center gap-2"
                            >
                                <span>📄</span> PDF
                            </button>
                        </>
                    )}

                    <div className="flex gap-2">
                        <button
                            onClick={runScan}
                            disabled={scanning}
                            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-blue-900/40 relative overflow-hidden group flex items-center gap-2"
                        >
                            {scanning ? <span className="animate-spin">📡</span> : <span>🚀</span>}
                            <span>{scanning ? 'Scanning...' : 'Run Scan'}</span>
                        </button>

                        {scanning && (
                            <button
                                onClick={handleCancelScan}
                                className="bg-red-600/20 hover:bg-red-600/40 text-red-500 border border-red-900/50 px-4 py-2 rounded-lg font-bold transition flex items-center gap-2"
                            >
                                <span>🛑</span> Cancel
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {stats && (
                <div className="grid grid-cols-4 gap-4 mb-8">
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <div className="text-slate-400 text-xs uppercase font-bold">Scanned</div>
                        <div className="text-2xl font-bold text-white">{stats.scanned}</div>
                    </div>
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <div className="text-slate-400 text-xs uppercase font-bold">Matches</div>
                        <div className="text-2xl font-bold text-blue-400">{stats.count}</div>
                    </div>
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <div className="text-slate-400 text-xs uppercase font-bold">SPY 3M Return</div>
                        <div className={`text-2xl font-bold ${stats.spy_ret_3m > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {stats.spy_ret_3m > 0 ? '+' : ''}{stats.spy_ret_3m?.toFixed(2)}%
                        </div>
                    </div>
                </div>
            )}

            {!stats && !scanning && (
                <div className="text-center py-20 border-2 border-dashed border-slate-800 rounded-xl">
                    <div className="text-6xl mb-4">📡</div>
                    <h3 className="text-xl font-bold text-white">Scanner Ready</h3>
                    <p className="text-slate-400 mt-2">Press "Run w.rsi Scan" to find weekly reversal setups.</p>
                </div>
            )}

            {scanning && (
                <div className="text-center py-20">
                    <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mb-4"></div>
                    <h3 className="text-xl font-bold text-white">Processing Market Data...</h3>

                    {/* Progress Bar */}
                    {progress.total > 0 && (
                        <div className="max-w-md mx-auto mt-6">
                            <div className="flex justify-between text-xs text-slate-400 mb-2 font-mono">
                                <span>Processing Tickers</span>
                                <span>{progress.current} / {progress.total}</span>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden border border-slate-700">
                                <div
                                    className="bg-blue-500 h-2.5 rounded-full transition-all duration-300 ease-out"
                                    style={{ width: `${Math.min((progress.current / progress.total) * 100, 100)}%` }}
                                ></div>
                            </div>
                            <div className="text-center text-xs text-slate-500 mt-2 font-mono h-4">
                                {progress.last_ticker || "Starting..."}
                            </div>
                            <div className="text-center text-xs text-slate-500 mt-2">
                                {Math.round((progress.current / progress.total) * 100)}% Complete
                            </div>

                        </div>
                    )}

                    {!progress.total && <p className="text-slate-400 mt-2">Initializing scanner engine...</p>}
                </div>
            )}

            {sortedResults.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {renderTable(sortedResults.filter(r => r.score >= 70), "High Probability Setups", "green", "🚀")}
                    {renderTable(sortedResults.filter(r => r.score < 70 && r.is_bullish), "Watchlist Candidates", "yellow", "👀")}
                </div>
            )}
        </div>
    );
}
// Options Scanner Component
function OptionsScanner() {
    const [stats, setStats] = useState([]);
    const [loading, setLoading] = useState(false);
    const [lastScan, setLastScan] = useState(null);

    const runScan = async () => {
        setLoading(true);
        try {
            const res = await axios.post(`${API_BASE}/scan-options`);
            setStats(res.data);
            setLastScan(new Date());
        } catch (e) {
            console.error(e);
            alert("Failed to fetch options data");
        } finally {
            setLoading(false);
        }
    };

    const renderTable = (data, title, colorClass, icon) => (
        <div className={`overflow-hidden rounded-xl border border-slate-700 shadow-xl ${colorClass === 'green' ? 'shadow-green-900/10' : 'shadow-red-900/10'}`}>
            <div className={`px-4 py-3 border-b border-slate-700 flex items-center justify-between ${colorClass === 'green' ? 'bg-green-900/20' : 'bg-red-900/20'}`}>
                <h3 className={`font-bold text-lg flex items-center gap-2 ${colorClass === 'green' ? 'text-green-400' : 'text-red-400'}`}>
                    {icon} {title}
                </h3>
                <span className="text-xs text-slate-400 bg-slate-800 px-2 py-1 rounded">{data.length} Signals</span>
            </div>
            <div className="overflow-x-auto bg-slate-800">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-900 text-slate-400 uppercase font-bold text-xs">
                        <tr>
                            <th className="p-3">Ticker</th>
                            <th className="p-3">Swing Setup</th>
                            <th className="p-3">DTE/Exp</th>
                            <th className="p-3 text-right">Conviction</th>
                            <th className="p-3 text-right">Vol/IV</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {data.map((row, idx) => (
                            <tr key={idx} className="hover:bg-slate-700/50 transition duration-150 border-b border-slate-700/30">
                                <td className="p-3 align-top">
                                    <div className="font-bold text-white text-base">{row.ticker}</div>
                                    <div className={`text-[10px] font-bold px-1.5 py-0.5 rounded border inline-block mt-1 ${row.type === 'CALL' ? 'border-green-500/50 text-green-400 bg-green-900/10' : 'border-red-500/50 text-red-400 bg-red-900/10'}`}>
                                        {row.type}
                                    </div>
                                </td>
                                <td className="p-3">
                                    <div className="flex flex-col gap-1">
                                        <div className="flex items-center gap-2 text-xs">
                                            <span className="text-slate-500 w-12">ENTRY:</span>
                                            <span className="font-mono text-white font-bold">${row.entry}</span>
                                        </div>
                                        <div className="flex items-center gap-2 text-xs">
                                            <span className="text-slate-500 w-12">TARGET:</span>
                                            <span className="font-mono text-green-400 font-bold">${row.target}</span>
                                        </div>
                                        <div className="flex items-center gap-2 text-xs">
                                            <span className="text-slate-500 w-12">STOP:</span>
                                            <span className="font-mono text-red-400 font-bold">${row.stop}</span>
                                        </div>
                                    </div>
                                </td>
                                <td className="p-3">
                                    <div className="flex flex-col">
                                        <span className="text-white font-bold text-xs">{row.dte || '?'} Days</span>
                                        <span className="text-[10px] text-slate-500">{row.expiration}</span>
                                        <span className="text-[9px] text-slate-600 mt-1">${row.strike} Strike</span>
                                    </div>
                                </td>
                                <td className="p-3 text-right align-top">
                                    <div className={`font-black text-lg ${row.vol_oi_ratio > 3 ? 'text-yellow-400' : 'text-slate-300'}`}>
                                        {row.vol_oi_ratio}x
                                    </div>
                                    <div className="text-[9px] text-slate-500 uppercase font-bold">Vol/OI Ratio</div>
                                </td>
                                <td className="p-3 text-right text-slate-300 align-top">
                                    <div className="font-mono font-bold">{row.volume.toLocaleString()}</div>
                                    <div className="text-[10px] text-slate-500">{row.impliedVolatility}% IV</div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );

    const hasData = stats.bullish?.length > 0 || stats.bearish?.length > 0;

    return (
        <div className="p-6 container mx-auto max-w-7xl animate-fade-in">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        Options Flow Intelligence
                        <span className="text-sm font-normal text-purple-400 border border-purple-500/30 bg-purple-500/10 px-2 py-1 rounded">Swing Edition</span>
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">High-conviction institutional signals with ~30-day expirations and actionable trade setups.</p>
                </div>
                <button
                    onClick={runScan}
                    disabled={loading}
                    className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-purple-900/20 transition flex items-center gap-2"
                >
                    {loading ? 'Scanning Chain...' : 'Run Options Scan'}
                </button>
            </div>

            {!hasData && !loading && (
                <div className="text-center py-20 border-2 border-dashed border-slate-800 rounded-xl">
                    <div className="text-4xl mb-4">🔮</div>
                    <p className="text-slate-500 text-lg">Hit Run to scan for unusual activity.</p>
                </div>
            )}

            {loading && (
                <div className="flex justify-center py-20">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
                </div>
            )}

            {hasData && (
                <div className="space-y-8">
                    {/* Expert Recommendations Section */}
                    {stats.expert_recommendations && stats.expert_recommendations.length > 0 && (
                        <div className="bg-slate-800/50 rounded-xl border border-purple-500/20 p-6">
                            <h3 className="text-purple-300 text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
                                <span>🧠 Expert Insights</span>
                                <span className="bg-purple-500/10 text-purple-400 text-[10px] px-2 py-0.5 rounded-full border border-purple-500/30">AI Analysis</span>
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                {stats.expert_recommendations.map((rec, i) => {
                                    const isBullish = rec.sentiment === 'BULLISH';
                                    const isBearish = rec.sentiment === 'BEARISH';
                                    const colorClass = isBullish ? 'text-green-400 border-green-500/30 bg-green-900/10' :
                                        (isBearish ? 'text-red-400 border-red-500/30 bg-red-900/10' : 'text-slate-300 border-slate-500/30 bg-slate-800');

                                    return (
                                        <div key={i} className={`p-4 rounded-lg border ${colorClass} relative overflow-hidden`}>
                                            <div className="flex justify-between items-start mb-2">
                                                <div className="text-lg font-bold text-white">{rec.ticker}</div>
                                                <div className={`text-[10px] font-bold px-2 py-0.5 rounded border ${isBullish ? 'border-green-500 text-green-400' : (isBearish ? 'border-red-500 text-red-400' : 'border-slate-500 text-slate-400')}`}>
                                                    {rec.conviction} CONVICTION
                                                </div>
                                            </div>
                                            <div className="text-xl font-black mb-1 uppercase tracking-tight">{rec.action}</div>
                                            <div className="text-xs opacity-70 leading-relaxed italic border-t border-white/5 pt-2 mt-2">
                                                "{rec.reason}"
                                            </div>

                                            {/* Technical Levels */}
                                            {rec.target > 0 && (
                                                <div className="mt-3 pt-3 border-t border-white/10 text-xs bg-black/20 -mx-4 -mb-4 p-4">
                                                    <div className="flex justify-between items-center mb-1">
                                                        <span className="text-slate-400 font-medium">TARGET</span>
                                                        <span className="font-mono text-green-400 font-bold text-sm">${rec.target.toFixed(2)}</span>
                                                    </div>
                                                    <div className="flex justify-between items-center mb-1">
                                                        <span className="text-slate-400 font-medium">STOP LOSS</span>
                                                        <span className="font-mono text-red-400 font-bold text-sm">${rec.stop_loss.toFixed(2)}</span>
                                                    </div>
                                                    <div className="flex justify-between items-center pt-2 mt-2 border-t border-white/5">
                                                        <span className="text-slate-500">Entry Ref</span>
                                                        <span className="font-mono text-slate-400">${rec.entry.toFixed(2)}</span>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Bullish Column */}
                        {renderTable(stats.bullish || [], "Bullish Flow (Upside)", "green", "🚀")}

                        {/* Bearish Column */}
                        {renderTable(stats.bearish || [], "Bearish Flow (Downside)", "red", "🐻")}
                    </div>
                </div>
            )}
        </div>
    );
}


// Market Clock Component
function MarketClock() {
    const [nyTime, setNyTime] = useState("--:--:--");
    const [baTime, setBaTime] = useState("--:--:--");

    // Status state
    const [statusNy, setStatusNy] = useState({ label: 'NY: ...', color: 'text-slate-500' });
    const [statusBa, setStatusBa] = useState({ label: 'BA: ...', color: 'text-slate-500' });

    useEffect(() => {
        const timer = setInterval(() => {
            try {
                const now = new Date();
                const day = now.getDay(); // 0 = Sunday, 6 = Saturday
                const isWeekend = day === 0 || day === 6;

                // NY Time Logic
                const nyFn = new Intl.DateTimeFormat('en-US', {
                    timeZone: 'America/New_York', hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: false
                });
                const ny = nyFn.format(now);
                setNyTime(ny);

                // NY Status
                const [hNy, mNy] = ny.split(':').map(Number);
                const totalMinNy = hNy * 60 + mNy;

                let sNy = { label: 'NY: CLOSED', color: 'text-slate-500' };
                if (!isWeekend) {
                    if (totalMinNy >= 570 && totalMinNy < 960) sNy = { label: 'NY: OPEN', color: 'text-green-400' };
                    else if (totalMinNy >= 240 && totalMinNy < 570) sNy = { label: 'NY: PRE', color: 'text-yellow-400' };
                    else if (totalMinNy >= 960 && totalMinNy < 1200) sNy = { label: 'NY: POST', color: 'text-blue-400' };
                }

                setStatusNy(prev => (prev.label === sNy.label ? prev : sNy));

                // BA Time Logic
                const baFn = new Intl.DateTimeFormat('en-GB', {
                    timeZone: 'America/Argentina/Buenos_Aires', hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: false
                });
                const ba = baFn.format(now);
                setBaTime(ba);

                // BA Status (BYMA approx 11:00 - 17:00)
                const [hBa, mBa] = ba.split(':').map(Number);
                const totalMinBa = hBa * 60 + mBa;

                let sBa = { label: 'BA: CLOSED', color: 'text-slate-500' };
                if (!isWeekend) {
                    if (totalMinBa >= 660 && totalMinBa < 1020) sBa = { label: 'BA: OPEN', color: 'text-sky-400' };
                }

                setStatusBa(prev => (prev.label === sBa.label ? prev : sBa));

            } catch (e) {
                console.error("MarketClock Error:", e);
            }
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const getStatusClass = (status) => {
        // Safe extraction of base color for border/bg opacity
        const baseColor = status.color.replace('text-', '');
        return `text-[10px] font-black px-2 py-0.5 rounded border border-${baseColor}/30 bg-${baseColor}/10 ${status.color}`;
    };

    return (
        <div className="flex gap-3">
            {/* NY Clock */}
            <div className="flex items-center gap-3 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-lg shadow-inner">
                <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 uppercase font-black leading-none">New York</span>
                    <span className="text-sm font-mono font-bold text-white leading-tight">{nyTime}</span>
                </div>
                <div className="h-6 w-px bg-slate-700"></div>
                <div className={getStatusClass(statusNy)}>
                    {statusNy.label}
                </div>
            </div>

            {/* BA Clock */}
            <div className="flex items-center gap-3 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-lg shadow-inner">
                <div className="flex flex-col">
                    <span className="text-[9px] text-slate-500 uppercase font-black leading-none">Buenos Aires</span>
                    <span className="text-sm font-mono font-bold text-white leading-tight">{baTime}</span>
                </div>
                <div className="h-6 w-px bg-slate-700"></div>
                <div className={getStatusClass(statusBa)}>
                    {statusBa.label}
                </div>
            </div>
        </div>
    );
}

// Economic Calendar Component
function EconomicCalendar({ events }) {
    if (!events || events.length === 0) return null;

    return (
        <div className="bg-slate-800/40 rounded-xl border border-slate-700 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between bg-slate-900/50">
                <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Economic Calendar</h3>
                <span className="text-[10px] bg-red-900/20 text-red-400 px-2 py-0.5 rounded border border-red-500/30">High Impact</span>
            </div>
            <div className="p-4 space-y-4">
                {events.map((event, i) => (
                    <div key={i} className="relative pl-6 border-l-2 border-slate-700 py-1">
                        <div className="absolute -left-[9px] top-2 w-4 h-4 rounded-full bg-slate-900 border-2 border-slate-700 flex items-center justify-center">
                            <div className={`w-1.5 h-1.5 rounded-full ${event.impact === 'High' ? 'bg-red-500' : 'bg-yellow-500'}`}></div>
                        </div>
                        <div className="flex justify-between items-start">
                            <div>
                                <div className="text-xs font-bold text-white">{event.event}</div>
                                <div className="text-[10px] text-slate-500 font-mono mt-0.5">{event.date} • {event.time}</div>
                            </div>
                            <div className="text-[10px] font-mono font-bold text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                                {event.impact}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Market Breadth Component
function MarketBreadth({ breadth }) {
    if (!breadth) return null;

    const sentimentColor = breadth.sentiment > 60 ? 'text-green-400' : (breadth.sentiment < 40 ? 'text-red-400' : 'text-yellow-400');
    const borderClass = breadth.sentiment > 60 ? 'border-green-500' : (breadth.sentiment < 40 ? 'border-red-500' : 'border-yellow-500');

    return (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-5 shadow-xl">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest mb-1">Market Sentiment</h3>
                    <div className={`text-3xl font-black ${sentimentColor}`}>{breadth.sentiment}%</div>
                </div>
                <div className="w-24 h-24 relative">
                    <svg className="w-full h-full transform -rotate-90">
                        <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-slate-700" />
                        <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="transparent" strokeDasharray={251} strokeDashoffset={251 - (251 * breadth.sentiment / 100)} className={`${sentimentColor} transition-all duration-1000`} />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center text-[10px] font-black text-slate-500 uppercase">Sentiment</div>
                </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-3">
                    <div>
                        <div className="flex justify-between text-[10px] mb-1">
                            <span className="text-slate-500 font-bold uppercase">A/D Ratio</span>
                            <span className="text-green-400 font-bold">{breadth.ad_ratio}%</span>
                        </div>
                        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-green-500 h-full transition-all duration-700" style={{ width: `${breadth.ad_ratio}%` }}></div>
                        </div>
                    </div>
                    <div>
                        <div className="flex justify-between text-[10px] mb-1">
                            <span className="text-slate-500 font-bold uppercase">H/L Ratio</span>
                            <span className="text-blue-400 font-bold">{breadth.hl_ratio}%</span>
                        </div>
                        <div className="w-full bg-slate-900 rounded-full h-1.5 overflow-hidden">
                            <div className="bg-blue-500 h-full transition-all duration-700" style={{ width: `${breadth.hl_ratio}%` }}></div>
                        </div>
                    </div>
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3 flex flex-col justify-center border border-slate-700/50">
                    <div className="flex items-center gap-2 mb-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
                        <span className="text-[10px] text-slate-400 uppercase tracking-tighter">Advancing: <span className="text-white font-bold ml-1">{breadth.advancing}</span></span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-red-500"></div>
                        <span className="text-[10px] text-slate-400 uppercase tracking-tighter">Declining: <span className="text-white font-bold ml-1">{breadth.declining}</span></span>
                    </div>
                </div>
            </div>
        </div>
    );
}

// Tiny Sparkline Component for Index Cards
function TinySparkline({ data, color }) {
    const { ResponsiveContainer, LineChart, Line, YAxis } = Recharts;
    if (!data || data.length === 0) return null;

    // Determine min/max for domain to make chart look good
    const minVal = Math.min(...data);
    const maxVal = Math.max(...data);
    const padding = (maxVal - minVal) * 0.1;

    // Create objects for Recharts
    const chartData = data.map((val, i) => ({ i, val }));

    return (
        <div className="h-10 w-full mt-2 opacity-80" onClick={(e) => e.stopPropagation()}>
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                    <YAxis domain={[minVal - padding, maxVal + padding]} hide />
                    <Line type="monotone" dataKey="val" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}

// Market Dashboard Component
function MarketDashboard({ onTickerClick }) {
    const [marketData, setMarketData] = useState(null);
    const [loading, setLoading] = useState(true);

    // AI Analyst State
    const [aiInsight, setAiInsight] = useState(null);
    const [aiInsightMeta, setAiInsightMeta] = useState(null); // Cache info: session, generated_at, cached
    const [analyzing, setAnalyzing] = useState(false);

    // Portfolio P&L State for Dashboard
    const [portfolioMetrics, setPortfolioMetrics] = useState(null);

    const fetchInsight = () => {
        setAnalyzing(true);
        axios.get(`${API_BASE}/ai/insight?_t=${Date.now()}`)
            .then(res => {
                setAiInsight(res.data.insight);
                setAiInsightMeta({
                    session: res.data.session || 'Live',
                    generated_at: res.data.generated_at || 'Just now',
                    cached: res.data.cached || false,
                    next_update: res.data.next_update
                });
                setAnalyzing(false);
            })
            .catch(err => {
                console.error("AI Error:", err);
                setAiInsight("Error contacting AI Analyst.");
                setAiInsightMeta(null);
                setAnalyzing(false);
            });
    };

    const SECTOR_ETFS = {
        "Technology": "XLK",
        "Financials": "XLF",
        "Health Care": "XLV",
        "Cons. Discret.": "XLY",
        "Cons. Staples": "XLP",
        "Energy": "XLE",
        "Industrials": "XLI",
        "Materials": "XLB",
        "Real Estate": "XLRE",
        "Comms": "XLC",
        "Utilities": "XLU"
    };

    const formatExpertText = (text) => {
        if (!text) return "";
        return text.replace(/\*\*(.*?)\*\*/g, (match, p1) => {
            if (/^[A-Z]{2,5}$/.test(p1)) {
                return `<span class="text-white font-bold cursor-pointer hover:text-indigo-400 underline decoration-indigo-500/30" onclick="window.dispatchEvent(new CustomEvent('tickerClick', {detail: '${p1}'}))">${p1}</span>`;
            }
            return `<strong class="text-white">${p1}</strong>`;
        });
    };

    useEffect(() => {
        setLoading(true);

        // Fetch market status
        axios.get(`${API_BASE}/market-status?_t=${Date.now()}`)
            .then(res => {
                setMarketData(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });

        // Fetch portfolio metrics for P&L display
        authFetch(`${API_BASE}/trades/unified/metrics`)
            .then(res => res.ok ? res.json() : Promise.reject('Auth failed'))
            .then(data => {
                setPortfolioMetrics(data);
            })
            .catch(err => {
                console.error('Portfolio metrics error:', err);
            });
    }, []);

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-slate-500">
            <div className="animate-spin text-4xl mb-4">🌀</div>
            <div>Initializing Market Intelligence...</div>
            <div className="text-xs text-slate-700 mt-2">Checking API Connection...</div>
        </div>
    );

    if (!marketData) return (
        <div className="p-8 text-center">
            <div className="text-red-400 mb-2">⚠ Error loading market data</div>
            <button onClick={() => window.location.reload()} className="bg-slate-800 px-4 py-2 rounded text-white text-sm">Retry</button>
        </div>
    );

    const { indices, sectors, expert_summary, breadth, calendar } = marketData;



    const renderTrafficLight = (ticker, info) => {
        if (!info) return (
            <div className="p-4 rounded-xl border border-slate-700 bg-slate-800/50 flex flex-col items-center justify-center opacity-50">
                <div className="text-sm font-bold opacity-50 mb-1">{ticker}</div>
                <div className="text-xl font-bold text-slate-500">N/A</div>
            </div>
        );

        const colorClass = info.color === 'Green' ? 'bg-green-500/20 text-green-400 border-green-500/50' :
            (info.color === 'Red' ? 'bg-red-500/20 text-red-400 border-red-500/50' : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50');

        return (
            <div
                onClick={() => onTickerClick(ticker)}
                className={`p-4 rounded-xl border ${colorClass} flex flex-col items-center justify-center cursor-pointer transition-all hover:brightness-125 hover:scale-[1.02] shadow-sm`}
            >
                <div className="text-sm font-bold opacity-70 mb-1">{ticker}</div>
                <div className="text-2xl font-bold">{info.desc}</div>
                <div className="text-xs mt-2 opacity-60">Price: ${info.price} / EMA21: ${info.ema21}</div>
                <TinySparkline
                    data={info.sparkline}
                    color={info.color === 'Green' ? '#4ade80' : (info.color === 'Red' ? '#f87171' : '#facc15')}
                />
            </div>
        );
    };



    const sorted1m = [...sectors].sort((a, b) => b['1m'] - a['1m']).slice(0, 5);
    const sorted2m = [...sectors].sort((a, b) => b['2m'] - a['2m']).slice(0, 5);
    const sorted3m = [...sectors].sort((a, b) => b['3m'] - a['3m']).slice(0, 5);

    return (
        <div className="space-y-6">
            {/* My Portfolio widget removed - user requested */}

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                {/* Main Content (9 Columns) */}
                <div className="lg:col-span-8 space-y-8">
                    {/* AI Analyst Section */}
                    <div className="bg-gradient-to-r from-purple-900/40 to-slate-900/40 border border-purple-700/30 rounded-xl p-6 relative overflow-hidden shadow-lg">
                        <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                            <svg className="w-32 h-32 text-purple-400" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z" /></svg>
                        </div>

                        {!aiInsight ? (
                            <div className="flex flex-col items-center justify-center text-center py-4 relative z-10">
                                <h2 className="text-xl font-bold text-white mb-2">🧠 Market Brain (AI Analyst)</h2>
                                <p className="text-slate-400 text-sm mb-4">Powered by Google Gemini AI</p>
                                <div className="flex gap-3 flex-wrap justify-center">
                                    <button
                                        onClick={fetchInsight}
                                        disabled={analyzing}
                                        className={`px-5 py-2 rounded-lg font-bold text-white transition-all shadow-lg flex items-center gap-2 ${analyzing ? 'bg-purple-600/50 cursor-not-allowed' : 'bg-purple-600 hover:bg-purple-500 hover:scale-105'}`}
                                    >
                                        {analyzing ? (
                                            <><span className="animate-spin">🔄</span> Analyzing...</>
                                        ) : (
                                            <><span>📊</span> Market Analysis</>
                                        )}
                                    </button>
                                    <button
                                        onClick={() => {
                                            setAnalyzing(true);
                                            axios.get(`${API_BASE}/ai/portfolio-insight?_t=${Date.now()}`)
                                                .then(res => { setAiInsight(res.data.insight); setAnalyzing(false); })
                                                .catch(err => { setAiInsight("Error: " + (err.response?.data?.detail || err.message)); setAnalyzing(false); });
                                        }}
                                        disabled={analyzing}
                                        className={`px-5 py-2 rounded-lg font-bold text-white transition-all shadow-lg flex items-center gap-2 ${analyzing ? 'bg-green-600/50 cursor-not-allowed' : 'bg-green-600 hover:bg-green-500 hover:scale-105'}`}
                                    >
                                        <span>💼</span> Analyze My Portfolio
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <div className="relative z-10">
                                <div className="flex items-center justify-between mb-2">
                                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                        <span>🧠</span> AI ANALYST INSIGHT
                                    </h2>
                                    <div className="flex gap-2">
                                        <button onClick={fetchInsight} className="text-purple-400 hover:text-purple-300 text-xs px-2 py-1 border border-purple-500/30 rounded">🔄 Refresh</button>
                                        <button onClick={() => setAiInsight(null)} className="text-slate-500 hover:text-white text-xs px-2 py-1 border border-slate-600 rounded">✕ Clear</button>
                                    </div>
                                </div>
                                {/* Cache Info Badge */}
                                {aiInsightMeta && (
                                    <div className="flex items-center gap-2 mb-3 text-xs">
                                        <span className={`px-2 py-0.5 rounded-full ${aiInsightMeta.cached ? 'bg-green-900/50 text-green-400 border border-green-700' : 'bg-yellow-900/50 text-yellow-400 border border-yellow-700'}`}>
                                            {aiInsightMeta.cached ? '📦 Cached' : '⚡ Live'}
                                        </span>
                                        <span className="text-slate-500">{aiInsightMeta.session}</span>
                                        <span className="text-slate-600">•</span>
                                        <span className="text-slate-500">{aiInsightMeta.generated_at}</span>
                                    </div>
                                )}

                                {/* Parse and render the insight beautifully */}
                                {(() => {
                                    const text = aiInsight;
                                    const sentimentMatch = text.match(/\*\*Sentiment:\*\*\s*(\d+)\/100\s*\(([^)]+)\)/);
                                    const analysisMatch = text.match(/\*\*Analysis:\*\*\s*([\s\S]*?)(?=\*\*Actionable|$)/);
                                    const actionMatch = text.match(/\*\*Actionable Insight:\*\*\s*([\s\S]*?)$/);

                                    if (sentimentMatch) {
                                        const score = parseInt(sentimentMatch[1]);
                                        const mood = sentimentMatch[2];
                                        const analysis = analysisMatch ? analysisMatch[1].trim() : '';
                                        const action = actionMatch ? actionMatch[1].trim() : '';
                                        const moodColor = score >= 70 ? 'text-green-400' : score >= 40 ? 'text-yellow-400' : 'text-red-400';
                                        const barColor = score >= 70 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';

                                        return (
                                            <div className="space-y-4">
                                                {/* Sentiment Gauge */}
                                                <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
                                                    <div className="flex items-center justify-between mb-2">
                                                        <span className="text-slate-400 text-sm font-medium">Market Sentiment</span>
                                                        <span className={`text-2xl font-bold ${moodColor}`}>{score}/100</span>
                                                    </div>
                                                    <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
                                                        <div className={`${barColor} h-full rounded-full transition-all duration-500`} style={{ width: `${score}%` }}></div>
                                                    </div>
                                                    <div className={`text-center mt-2 text-lg font-bold ${moodColor}`}>
                                                        {mood.includes('Optimistic') || mood.includes('Bullish') || mood.includes('Greed') ? '📈' : mood.includes('Fear') || mood.includes('Bearish') ? '📉' : '⚖️'} {mood}
                                                    </div>
                                                </div>

                                                {/* Analysis */}
                                                {analysis && (
                                                    <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-700/30">
                                                        <h4 className="text-purple-400 text-xs font-bold uppercase tracking-wider mb-2">📊 Analysis</h4>
                                                        <p className="text-slate-300 text-sm leading-relaxed">{analysis}</p>
                                                    </div>
                                                )}

                                                {/* Actionable Insight */}
                                                {action && (
                                                    <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 rounded-lg p-4 border border-blue-500/30">
                                                        <h4 className="text-blue-400 text-xs font-bold uppercase tracking-wider mb-2">🎯 Actionable Insight</h4>
                                                        <p className="text-white text-sm font-medium leading-relaxed">{action}</p>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    } else {
                                        // Fallback: just show the raw text nicely formatted
                                        return (
                                            <div className="bg-slate-800/30 rounded-lg p-4 border border-slate-700/30 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap">
                                                {text.replace(/\*\*/g, '')}
                                            </div>
                                        );
                                    }
                                })()}
                            </div>
                        )}
                    </div>

                    {/* Legacy Expert Summary (Fallback) */}
                    {expert_summary && !aiInsight && (
                        <div className="bg-slate-900/20 border border-slate-800 rounded-xl p-4 opacity-70 hover:opacity-100 transition">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-xs font-bold text-slate-500 uppercase">Legacy Briefing</span>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                                <div><strong className="text-slate-400">Setup:</strong> <span dangerouslySetInnerHTML={{ __html: formatExpertText(expert_summary.setup) }}></span></div>
                                <div><strong className="text-slate-400">Internals:</strong> <span dangerouslySetInnerHTML={{ __html: formatExpertText(expert_summary.internals) }}></span></div>
                                <div><strong className="text-blue-400">Action:</strong> "{expert_summary.play}"</div>
                            </div>
                        </div>
                    )}

                    {/* Section 1: Market Health Indices + Crypto */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        {renderTrafficLight('SPY', indices.SPY)}
                        {renderTrafficLight('QQQ', indices.QQQ)}
                        {renderTrafficLight('IWM', indices.IWM)}

                        {indices.VIX ? (
                            <div
                                onClick={() => onTickerClick('^VIX')}
                                className={`p-4 rounded-xl border flex flex-col items-center justify-center cursor-pointer transition-all hover:brightness-110 hover:scale-[1.02] ${indices.VIX.level === 'Low' ? 'bg-blue-500/20 border-blue-500/50 text-blue-300' : 'bg-orange-500/20 border-orange-500/50 text-orange-300'}`}
                            >
                                <div className="text-sm font-bold opacity-70 mb-1">VIX (Risk)</div>
                                <div className="text-2xl font-bold">{indices.VIX.price}</div>
                                <div className="text-xs mt-2 opacity-80 uppercase tracking-widest">{indices.VIX.level}</div>
                                <TinySparkline
                                    data={indices.VIX.sparkline}
                                    color={indices.VIX.level === 'Low' ? '#60a5fa' : '#fb923c'}
                                />
                            </div>
                        ) : (
                            <div className="p-4 rounded-xl border border-slate-700 bg-slate-800/50 flex flex-col items-center justify-center">
                                <div className="text-sm font-bold opacity-50 mb-1">VIX (Risk)</div>
                                <div className="text-xl font-bold text-slate-500">N/A</div>
                            </div>
                        )}

                        {/* Bitcoin Card */}
                        {indices.BTC ? (
                            <div
                                onClick={() => onTickerClick('BTC-USD')}
                                className={`p-4 rounded-xl border flex flex-col items-center justify-center cursor-pointer transition-all hover:brightness-110 hover:scale-[1.02] ${indices.BTC.color === 'Green' ? 'bg-amber-500/20 border-amber-500/50 text-amber-300' : 'bg-orange-500/20 border-orange-500/50 text-orange-300'}`}
                            >
                                <div className="text-sm font-bold opacity-70 mb-1">₿ BTC</div>
                                <div className="text-xl font-bold">${indices.BTC.price.toLocaleString()}</div>
                                <div className={`text-xs mt-2 font-bold ${indices.BTC.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {indices.BTC.change_24h >= 0 ? '+' : ''}{indices.BTC.change_24h}% 24h
                                </div>
                                <TinySparkline
                                    data={indices.BTC.sparkline}
                                    color={indices.BTC.change_24h >= 0 ? '#4ade80' : '#f87171'}
                                />
                            </div>
                        ) : (
                            <div className="p-4 rounded-xl border border-slate-700 bg-slate-800/50 flex flex-col items-center justify-center">
                                <div className="text-sm font-bold opacity-50 mb-1">₿ BTC</div>
                                <div className="text-xl font-bold text-slate-500">Loading...</div>
                            </div>
                        )}
                    </div>


                </div>

                {/* Sidebar (4 Columns) */}
                <div className="lg:col-span-4 space-y-8">
                    {/* Market Breadth Gauge */}
                    <MarketBreadth breadth={breadth} />

                    {/* Economic Calendar */}
                    <EconomicCalendar events={calendar} />
                </div>

                {/* Section 3: Sector Rotation (Full Width Bottom) */}
                <div className="lg:col-span-12">
                    <h3 className="text-slate-400 text-sm font-bold uppercase tracking-wide mb-4">Sector Leaders</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* 1 Month */}
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                            <div className="bg-slate-900/50 p-3 border-b border-slate-700 font-bold text-center text-slate-300">
                                Top 1 Month
                            </div>
                            <div className="p-2 space-y-1">
                                {sorted1m.map((s, i) => (
                                    <div
                                        key={s.ticker}
                                        onClick={() => onTickerClick(SECTOR_ETFS[s.name] || s.ticker)}
                                        className="flex justify-between items-center p-2 rounded hover:bg-slate-700/50 cursor-pointer transition-all"
                                    >
                                        <span className="text-sm font-medium text-slate-200">
                                            <span className="text-slate-500 mr-2">#{i + 1}</span> {s.name}
                                        </span>
                                        <span className={`text-sm font-bold ${s['1m'] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {s['1m'] > 0 ? '+' : ''}{s['1m']}%
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* 2 Month */}
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                            <div className="bg-slate-900/50 p-3 border-b border-slate-700 font-bold text-center text-slate-300">
                                Top 2 Months
                            </div>
                            <div className="p-2 space-y-1">
                                {sorted2m.map((s, i) => (
                                    <div key={s.ticker} className="flex justify-between items-center p-2 rounded hover:bg-slate-700/50">
                                        <span className="text-sm font-medium text-slate-200">
                                            <span className="text-slate-500 mr-2">#{i + 1}</span> {s.name}
                                        </span>
                                        <span className={`text-sm font-bold ${s['2m'] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {s['2m'] > 0 ? '+' : ''}{s['2m']}%
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* 3 Month */}
                        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                            <div className="bg-slate-900/50 p-3 border-b border-slate-700 font-bold text-center text-slate-300">
                                Top 3 Months (Deep Dive)
                            </div>
                            <div className="p-2 space-y-2">
                                {sorted3m.map((s, i) => (
                                    <div key={s.ticker} className="bg-slate-700/30 rounded p-2 border border-slate-700/50">
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="text-sm font-medium text-slate-200">
                                                <span className="text-slate-500 mr-2">#{i + 1}</span> {s.name}
                                            </span>
                                            <span className={`text-sm font-bold ${s['3m'] > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {s['3m'] > 0 ? '+' : ''}{s['3m']}%
                                            </span>
                                        </div>

                                        {/* Deep Dive Info */}
                                        {s.deep_dive && (
                                            <div className="grid grid-cols-2 gap-2 text-[10px] bg-slate-800/50 p-1.5 rounded">
                                                <div onClick={(e) => { e.stopPropagation(); onTickerClick(s.deep_dive.leader.ticker); }} className="hover:text-green-400 cursor-pointer transition">
                                                    <div className="text-green-400 font-bold mb-0.5">🏆 Leader</div>
                                                    <div className="font-mono">{s.deep_dive.leader.ticker} <span className="text-green-300">+{s.deep_dive.leader.perf.toFixed(1)}%</span></div>
                                                </div>
                                                <div onClick={(e) => { e.stopPropagation(); onTickerClick(s.deep_dive.laggard.ticker); }} className="text-right hover:text-orange-400 cursor-pointer transition">
                                                    <div className="text-orange-400 font-bold mb-0.5">🐢 Laggard</div>
                                                    <div className="font-mono">{s.deep_dive.laggard.ticker} <span className="text-orange-300">{s.deep_dive.laggard.perf > 0 ? '+' : ''}{s.deep_dive.laggard.perf.toFixed(1)}%</span></div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

// Settings Component for Backups
function Settings() {
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'dark');
    const [density, setDensity] = useState(localStorage.getItem('density') || 'comfortable');
    const [alertSettings, setAlertSettings] = useState({
        enabled: false,
        telegram_chat_id: '',
        notify_sl: true,
        notify_tp: true
    });
    const [loading, setLoading] = useState(true);
    const [feedback, setFeedback] = useState('');
    const [feedbackSent, setFeedbackSent] = useState(false);

    useEffect(() => {
        // Load alert settings from backend
        axios.get(`${API_BASE}/alerts/settings`)
            .then(res => {
                setAlertSettings(res.data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const handleThemeChange = (newTheme) => {
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        // Apply theme immediately
        document.body.classList.remove('theme-dark', 'theme-light', 'theme-cyber');
        document.body.classList.add(`theme-${newTheme}`);
        if (newTheme === 'light') {
            document.body.style.backgroundColor = '#f5f5f5';
            document.body.style.color = '#1a1a1a';
        } else if (newTheme === 'cyber') {
            document.body.style.backgroundColor = '#0d0221';
            document.body.style.color = '#00ff88';
        } else {
            document.body.style.backgroundColor = '#0a0a0a';
            document.body.style.color = '#ffffff';
        }
    };

    const handleDensityChange = (e) => {
        const newDensity = e.target.value;
        setDensity(newDensity);
        localStorage.setItem('density', newDensity);
        // Apply density immediately - just save for now as requires CSS
        document.body.classList.remove('density-comfortable', 'density-compact');
        document.body.classList.add(`density-${newDensity}`);
    };

    const handleAlertToggle = (field) => {
        const updated = { ...alertSettings, [field]: !alertSettings[field] };
        setAlertSettings(updated);
        axios.post(`${API_BASE}/alerts/settings`, updated).catch(console.error);
    };

    const handleChatIdSave = () => {
        axios.post(`${API_BASE}/alerts/settings`, alertSettings)
            .then(() => alert('Telegram Chat ID saved!'))
            .catch(() => alert('Error saving settings'));
    };

    const handleTestAlert = () => {
        axios.post(`${API_BASE}/alerts/test`)
            .then(() => alert('Test alert sent! Check your Telegram.'))
            .catch(e => alert('Error: ' + (e.response?.data?.detail || e.message)));
    };

    const handleFeedbackSubmit = () => {
        if (!feedback.trim()) return;
        // Send feedback via mailto or backend
        window.location.href = `mailto:javier.s.gomez@gmail.com?subject=Momentum Trader Feedback&body=${encodeURIComponent(feedback)}`;
        setFeedbackSent(true);
        setFeedback('');
    };

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="flex items-center gap-4 mb-8">
                <div className="p-3 bg-blue-600/20 rounded-xl">
                    <span className="text-3xl">⚙️</span>
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-white">Platform Settings</h2>
                    <p className="text-slate-400">Customize your trading experience</p>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Appearance */}
                <div className="bg-[#151515] border border-[#2a2a2a] rounded-xl p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <span>🎨</span> Appearance
                    </h3>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">Theme</label>
                            <div className="grid grid-cols-3 gap-2">
                                <button onClick={() => handleThemeChange('dark')} className={`px-3 py-2 text-xs font-bold rounded-lg border-2 transition ${theme === 'dark' ? 'bg-blue-600 text-white border-blue-400' : 'bg-[#2a2a2a] text-slate-400 border-[#3a3a3a] hover:border-blue-500'}`}>Dark</button>
                                <button onClick={() => handleThemeChange('light')} className={`px-3 py-2 text-xs font-bold rounded-lg border-2 transition ${theme === 'light' ? 'bg-blue-600 text-white border-blue-400' : 'bg-[#2a2a2a] text-slate-400 border-[#3a3a3a] hover:border-blue-500'}`}>Light</button>
                                <button onClick={() => handleThemeChange('cyber')} className={`px-3 py-2 text-xs font-bold rounded-lg border-2 transition ${theme === 'cyber' ? 'bg-blue-600 text-white border-blue-400' : 'bg-[#2a2a2a] text-slate-400 border-[#3a3a3a] hover:border-blue-500'}`}>Cyber</button>
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">Density</label>
                            <select value={density} onChange={handleDensityChange} className="w-full bg-[#0a0a0a] border border-[#3a3a3a] text-white text-sm rounded-lg p-2.5 focus:border-blue-500 focus:outline-none">
                                <option value="comfortable">Comfortable</option>
                                <option value="compact">Compact</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Telegram Alerts */}
                <div className="bg-[#151515] border border-[#2a2a2a] rounded-xl p-6">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <span>📱</span> Telegram Alerts
                    </h3>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-slate-400 mb-2">Chat ID</label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={alertSettings.telegram_chat_id || ''}
                                    onChange={(e) => setAlertSettings({ ...alertSettings, telegram_chat_id: e.target.value })}
                                    placeholder="Your Telegram Chat ID"
                                    className="flex-1 bg-[#0a0a0a] border border-[#3a3a3a] text-white text-sm rounded-lg p-2.5 focus:border-blue-500 focus:outline-none"
                                />
                                <button onClick={handleChatIdSave} className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg">Save</button>
                            </div>
                        </div>
                        <div className="flex items-center justify-between p-3 bg-[#0a0a0a] rounded-lg border border-[#2a2a2a]">
                            <span className="text-sm text-slate-300">Enable Alerts</span>
                            <button onClick={() => handleAlertToggle('enabled')} className={`w-10 h-5 rounded-full relative transition ${alertSettings.enabled ? 'bg-green-600' : 'bg-slate-700'}`}>
                                <div className={`absolute top-1 w-3 h-3 bg-white rounded-full transition-all ${alertSettings.enabled ? 'right-1' : 'left-1'}`}></div>
                            </button>
                        </div>
                        <button onClick={handleTestAlert} className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold rounded-lg border border-slate-700 transition">
                            🔔 Send Test Alert
                        </button>
                    </div>
                </div>

                {/* Feedback */}
                <div className="bg-[#151515] border border-[#2a2a2a] rounded-xl p-6 md:col-span-2">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                        <span>💬</span> Send Feedback
                    </h3>
                    {feedbackSent ? (
                        <div className="text-green-400 text-center py-4">✅ Thanks for your feedback!</div>
                    ) : (
                        <div className="space-y-4">
                            <textarea
                                value={feedback}
                                onChange={(e) => setFeedback(e.target.value)}
                                placeholder="Tell us what you think, report bugs, or suggest features..."
                                className="w-full bg-[#0a0a0a] border border-[#3a3a3a] text-white text-sm rounded-lg p-3 focus:border-blue-500 focus:outline-none h-24 resize-none"
                            />
                            <button onClick={handleFeedbackSubmit} className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition">
                                Send Feedback
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer Branding */}
            <div className="mt-12 pt-6 border-t border-[#2a2a2a] text-center">
                <p className="text-xs text-slate-600 font-mono mb-1">Momentum Trader v3.2.0</p>
                <p className="text-[10px] text-slate-700 italic">by Javier Gómez</p>
            </div>
        </div>
    );
}

// Connect Modal for Remote Access
function ConnectModal({ onClose }) {
    const [networkInfo, setNetworkInfo] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        axios.get(`${API_BASE}/system/network`)
            .then(res => setNetworkInfo(res.data))
            .catch(e => console.error(e))
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[100] backdrop-blur-sm" onClick={onClose}>
            <div className="bg-slate-900 border border-slate-700 rounded-2xl p-8 max-w-sm w-full shadow-2xl transform scale-100 transition-all" onClick={e => e.stopPropagation()}>
                <div className="text-center">
                    <div className="mx-auto bg-blue-500/10 w-16 h-16 rounded-full flex items-center justify-center mb-4">
                        <span className="text-3xl">📱</span>
                    </div>
                    <h3 className="text-2xl font-bold text-white mb-2">Remote Access</h3>
                    <p className="text-slate-400 text-sm mb-6">Scan to control from your phone</p>

                    {loading ? (
                        <div className="w-48 h-48 mx-auto bg-slate-800 rounded-xl animate-pulse flex items-center justify-center text-slate-500">
                            Detecting Network...
                        </div>
                    ) : (
                        <div className="bg-white p-4 rounded-xl mx-auto w-fit mb-4 shadow-inner">
                            {/* Using public QR API */}
                            <img
                                src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(networkInfo?.url || '')}&bgcolor=ffffff`}
                                alt="QR Code"
                                className="w-48 h-48 mix-blend-multiply"
                            />
                        </div>
                    )}

                    <div className="bg-slate-800/50 rounded-lg p-3 mb-6 border border-slate-700/50">
                        <div className="text-xs text-slate-500 uppercase tracking-widest mb-1">Direct Link</div>
                        <code className="text-blue-400 font-mono text-sm select-all">
                            {networkInfo?.url || '...'}
                        </code>
                    </div>

                    <button
                        onClick={onClose}
                        className="w-full bg-slate-800 hover:bg-slate-700 text-white font-medium py-3 rounded-lg transition border border-slate-700"
                    >
                        Close
                    </button>
                    <p className="text-[10px] text-slate-600 mt-4">
                        Note: Devices must be on the same Wi-Fi network.
                    </p>
                </div>
            </div>
        </div>
    );
}

// Argentina Journal Component - Full-featured journal mirroring USA
function ArgentinaPanel() {
    // State management
    const [trades, setTrades] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [rates, setRates] = useState({ ccl: 0, mep: 0, oficial: 0 });
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('active'); // 'active', 'history'
    const [activeSubTab, setActiveSubTab] = useState('log'); // 'log', 'analytics', 'options'
    const [displayCurrency, setDisplayCurrency] = useState('ars'); // 'ars', 'usd_ccl', 'usd_mep', 'usd_oficial'
    const [showAddForm, setShowAddForm] = useState(false);

    // UI State for Table
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [expandedGroups, setExpandedGroups] = useState({});
    const [liveData, setLiveData] = useState({});
    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

    // Analytics state
    const [equityData, setEquityData] = useState(null);
    const [calendarData, setCalendarData] = useState(null);
    const [openAnalytics, setOpenAnalytics] = useState(null);
    const [performanceData, setPerformanceData] = useState(null);
    const [snapshotData, setSnapshotData] = useState([]);

    // Options Analyzer state
    const [optionForm, setOptionForm] = useState({
        underlying: '', strike: '', expiry: '', market_price: '', option_type: 'call'
    });
    const [optionResult, setOptionResult] = useState(null);
    const [analyzingOption, setAnalyzingOption] = useState(false);

    // Partial Sell Modal State
    const [showSellModal, setShowSellModal] = useState(false);
    const [sellData, setSellData] = useState({
        positionId: null,
        ticker: '',
        currentShares: 0,
        currentPrice: 0
    });

    // AI Portfolio Analysis
    const [aiInsight, setAiInsight] = useState(null);
    const [aiAnalyzing, setAiAnalyzing] = useState(false);

    const handleAnalyzePortfolio = async () => {
        setAiAnalyzing(true);
        try {
            const res = await axios.get(`${API_BASE}/argentina/ai/portfolio-insight`);
            setAiInsight(res.data?.insight || res.data);
        } catch (err) {
            console.error('AI Analysis failed:', err);
            setAiInsight('Error analyzing portfolio. Please try again.');
        }
        setAiAnalyzing(false);
    };

    // Add Position form
    const [formData, setFormData] = useState({
        ticker: '', asset_type: 'stock', entry_date: new Date().toISOString().split('T')[0],
        entry_price: '', shares: '', stop_loss: '', target: '', target2: '', target3: '', strategy: '', notes: ''
    });

    const fileInputRef = React.useRef(null);

    const handleDownloadTemplate = () => {
        window.location.href = `${API_BASE}/argentina/template`;
    };

    const handleImportClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
    };

    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        setLoading(true);
        try {
            const res = await axios.post(`${API_BASE}/argentina/upload_csv`, formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });

            if (res.data.status === 'success') {
                alert(`Import successful! ${res.data.imported} trades imported.`);
                fetchData();
            } else {
                alert("Import failed? " + JSON.stringify(res.data));
            }
        } catch (e) {
            console.error(e);
            alert("Import failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    // Helper for coloring EMAs
    const getEmaColor = (price, ema) => {
        if (!ema) return "text-slate-600";
        return price > ema ? "text-green-400 font-medium" : "text-red-400 font-medium";
    };

    // STAGE 1: Fast essential data (trades list + metrics + rates from DB)
    const fetchEssentialData = async () => {
        setLoading(true);
        try {
            const [tradesRes, metricsRes, ratesRes] = await Promise.all([
                axios.get(`${API_BASE}/argentina/trades/list`),
                axios.get(`${API_BASE}/argentina/trades/metrics`),
                axios.get(`${API_BASE}/argentina/rates`)
            ]);

            if (tradesRes.data) {
                setTrades(tradesRes.data.trades || tradesRes.data || []);
            }
            if (metricsRes.data) setMetrics(metricsRes.data);
            if (ratesRes.data) setRates(ratesRes.data);
        } catch (err) {
            console.error('Error fetching Argentina essential data:', err);
        } finally {
            setLoading(false);
        }
    };

    // STAGE 2: Heavy analytics data (deferred - loads after UI shows)
    const fetchHeavyData = async () => {
        try {
            const [equityRes, calendarRes, analyticsRes, perfRes, snapRes] = await Promise.all([
                axios.get(`${API_BASE}/argentina/trades/equity-curve`).catch(() => ({ data: [] })),
                axios.get(`${API_BASE}/argentina/trades/calendar`).catch(() => ({ data: {} })),
                axios.get(`${API_BASE}/argentina/trades/analytics/open`).catch(() => ({ data: {} })),
                axios.get(`${API_BASE}/argentina/trades/analytics/performance`).catch(() => ({ data: {} })),
                axios.get(`${API_BASE}/argentina/trades/snapshots`).catch(() => ({ data: [] }))
            ]);

            if (equityRes.data && Array.isArray(equityRes.data)) {
                const rawEquity = equityRes.data;
                const transformedEquity = {
                    dates: rawEquity.map(item => item.date),
                    equity: rawEquity.map(item => item.value)
                };
                setEquityData(transformedEquity);
            }
            if (calendarRes.data) {
                const calData = calendarRes.data;
                setCalendarData(Array.isArray(calData) ? calData : []);
            }
            if (analyticsRes.data) setOpenAnalytics(analyticsRes.data);
            if (perfRes.data) setPerformanceData(perfRes.data);
            if (snapRes.data) setSnapshotData(snapRes.data);
        } catch (err) {
            console.error('Error fetching Argentina heavy data:', err);
        }
    };

    // Legacy fetchData for manual refresh (loads everything)
    const fetchData = async () => {
        await fetchEssentialData();
        await fetchHeavyData();
        fetchLivePrices();
    };

    const fetchLivePrices = async (forceRefresh = false) => {
        setRefreshing(true);
        try {
            // If force refresh, clear the backend cache first
            if (forceRefresh) {
                await authFetch(`${API_BASE}/prices/refresh`, { method: 'POST' }).catch(() => { });
            }
            const res = await axios.get(`${API_BASE}/argentina/prices`);
            if (res.data) {
                setLiveData(res.data);
                setLastUpdated(new Date());
            }
        } catch (e) {
            console.error("Failed to fetch live prices", e);
        } finally {
            setRefreshing(false);
        }
    };

    useEffect(() => {
        // STAGE 1: Load essential data immediately
        fetchEssentialData();

        // STAGE 2: Load heavy data after a small delay (UI renders first)
        const heavyTimer = setTimeout(() => {
            fetchHeavyData();
            fetchLivePrices();
        }, 100);

        // Auto-Refresh Live Prices every 60s
        const interval = setInterval(fetchLivePrices, 60000);

        return () => {
            clearTimeout(heavyTimer);
            clearInterval(interval);
        };
    }, []);

    // Currency conversion helpers
    const convertToDisplay = (arsValue) => {
        if (displayCurrency === 'ars') return arsValue;
        if (displayCurrency === 'usd_ccl') return rates.ccl > 0 ? arsValue / rates.ccl : 0;
        if (displayCurrency === 'usd_mep') return rates.mep > 0 ? arsValue / rates.mep : 0;
        if (displayCurrency === 'usd_oficial') return rates.oficial > 0 ? arsValue / rates.oficial : 0;
        return arsValue;
    };

    const currencySymbol = displayCurrency === 'ars' ? 'ARS ' : 'US$';
    const currencyLabel = displayCurrency === 'ars' ? 'ARS' : displayCurrency.replace('usd_', '').toUpperCase();

    // Grouping Logic
    const groupedTrades = useMemo(() => {
        return trades.reduce((groups, trade) => {
            const ticker = trade.ticker;
            if (!groups[ticker]) groups[ticker] = [];
            groups[ticker].push(trade);
            return groups;
        }, {});
    }, [trades]);

    const activeGroups = useMemo(() => {
        const active = {};
        Object.keys(groupedTrades).forEach(ticker => {
            const openTrades = groupedTrades[ticker].filter(t => t.status === 'OPEN');
            if (openTrades.length > 0) {
                active[ticker] = openTrades; // Show ONLY open trades in Active tab
            }
        });
        return active;
    }, [groupedTrades]);

    const historyGroups = useMemo(() => {
        const history = {};
        Object.keys(groupedTrades).forEach(ticker => {
            const closedTrades = groupedTrades[ticker].filter(t => t.status !== 'OPEN');
            if (closedTrades.length > 0) {
                history[ticker] = closedTrades; // Show ONLY closed trades in History tab
            }
        });
        return history;
    }, [groupedTrades]);

    const currentGroups = activeTab === 'active' ? activeGroups : historyGroups;

    const toggleGroup = (ticker) => {
        setExpandedGroups(prev => ({ ...prev, [ticker]: !prev[ticker] }));
    };

    // Calculate Row Stats for Sorting and Display
    const rowStats = useMemo(() => {
        return Object.entries(currentGroups).map(([ticker, groupTrades]) => {
            const live = liveData[ticker] || {};

            let openShares = 0;
            let openCost = 0;
            let totalHistoryShares = 0;
            let totalHistoryCost = 0;
            let totalExitValue = 0;
            let minEntryDate = null;
            let maxExitDate = null;
            let totalPnl = 0;

            groupTrades.forEach(t => {
                const entryPrice = t.entry_price || 0;
                totalHistoryShares += t.shares;
                totalHistoryCost += entryPrice * t.shares;

                if (!minEntryDate || new Date(t.entry_date) < new Date(minEntryDate)) {
                    minEntryDate = t.entry_date;
                }

                if (t.status === 'OPEN') {
                    openShares += t.shares;
                    openCost += entryPrice * t.shares;

                    const currentPrice = live.price || entryPrice;
                    const upnl = (currentPrice - entryPrice) * t.shares;
                    totalPnl += upnl;
                } else {
                    const exitPrice = t.exit_price || 0;
                    const realizedPnl = (exitPrice - entryPrice) * t.shares;
                    totalPnl += realizedPnl;
                    totalExitValue += exitPrice * t.shares;

                    if (t.exit_date) {
                        if (!maxExitDate || new Date(t.exit_date) > new Date(maxExitDate)) {
                            maxExitDate = t.exit_date;
                        }
                    }
                }
            });

            const isHistory = activeTab === 'history';
            const displayShares = isHistory ? totalHistoryShares : openShares;
            const displayCost = isHistory ? totalHistoryCost : openCost;

            const avgPpc = isHistory
                ? (totalHistoryShares > 0 ? totalHistoryCost / totalHistoryShares : 0)
                : (openShares > 0 ? openCost / openShares : 0);

            const avgExitPrice = (isHistory && totalHistoryShares > 0) ? totalExitValue / totalHistoryShares : 0;

            let daysHeld = 0;
            if (minEntryDate) {
                const endDate = isHistory && maxExitDate ? new Date(maxExitDate) : new Date();
                daysHeld = getTradingDaysBetween(minEntryDate, endDate);
            }

            const returnBasis = isHistory ? totalHistoryCost : openCost;
            const totalPnlPct = returnBasis > 0 ? (totalPnl / returnBasis) * 100 : 0;

            const currentPrice = live.price || 0;
            const dayChange = live.change_pct || 0;

            const displayPrice = isHistory ? avgExitPrice : currentPrice;

            return {
                ticker,
                groupTrades,
                live,
                avgPpc,
                displayShares,
                displayCost,
                totalPnl,
                displayPrice,
                dayChange,
                totalPnlPct,
                daysHeld,
                emas: {
                    ema_8: live.ema_8,
                    ema_21: live.ema_21,
                    ema_35: live.ema_35,
                    ema_200: live.ema_200
                },
                currentPrice
            };
        });
    }, [currentGroups, liveData, activeTab]);

    const sortedRows = useMemo(() => {
        let sortableItems = [...rowStats];
        if (sortConfig.key !== null) {
            sortableItems.sort((a, b) => {
                let aValue = a[sortConfig.key];
                let bValue = b[sortConfig.key];
                if (typeof aValue === 'string') aValue = aValue.toLowerCase();
                if (typeof bValue === 'string') bValue = bValue.toLowerCase();
                if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
                if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
                return 0;
            });
        }
        return sortableItems;
    }, [rowStats, sortConfig]);

    const requestSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') direction = 'desc';
        setSortConfig({ key, direction });
    };

    const getSortIcon = (key) => {
        if (sortConfig.key !== key) return '↕';
        return sortConfig.direction === 'asc' ? '↑' : '↓';
    };

    // Handlers
    const handleUpdateGroup = async (tradesToUpdate, field, value) => {
        try {
            await Promise.all(tradesToUpdate.map(t => axios.put(`${API_BASE}/argentina/trades/${t.id}?field=${field}&value=${value}`)));
            fetchData();
        } catch (e) {
            console.error(e);
            alert("Failed to update trade");
        }
    };

    const handleDelete = async (id) => {
        if (!confirm('¿Eliminar esta posición?')) return;
        try {
            await axios.delete(`${API_BASE}/argentina/positions/${id}`);
            fetchData();
        } catch (err) {
            console.error('Error deleting:', err);
        }
    };

    const handleAddPosition = async (e) => {
        e.preventDefault();
        try {
            // Convert form data to proper types
            const payload = {
                ticker: formData.ticker.toUpperCase(),
                asset_type: formData.asset_type,
                entry_date: formData.entry_date,
                entry_price: parseFloat(formData.entry_price) || 0,
                shares: parseFloat(formData.shares) || 0,
                stop_loss: formData.stop_loss ? parseFloat(formData.stop_loss) : null,
                target: formData.target ? parseFloat(formData.target) : null,
                target2: formData.target2 ? parseFloat(formData.target2) : null,
                target3: formData.target3 ? parseFloat(formData.target3) : null,
                strategy: formData.strategy || null,
                notes: formData.notes || null
            };
            const res = await axios.post(`${API_BASE}/argentina/positions`, payload);
            if (res.data) {
                setShowAddForm(false);
                setFormData({ ticker: '', asset_type: 'stock', entry_date: new Date().toISOString().split('T')[0], entry_price: '', shares: '', stop_loss: '', target: '', target2: '', target3: '', strategy: '', notes: '' });
                fetchData();
            }
        } catch (err) {
            console.error('Error adding position:', err);
            alert('Error adding position: ' + (err.response?.data?.detail || err.message));
        }
    };

    // Close position not needed here as we use group logic, but keeping for compatibility if single row approach needed?
    // Actually we removed single row logic.

    // Analyze option
    const handleAnalyzeOption = async () => {
        setAnalyzingOption(true);
        try {
            const params = new URLSearchParams({
                underlying: optionForm.underlying,
                strike: optionForm.strike,
                expiry: optionForm.expiry,
                market_price: optionForm.market_price,
                option_type: optionForm.option_type
            });
            const res = await axios.get(`${API_BASE}/argentina/options/analyze?${params}`);
            if (res.data) setOptionResult(res.data);
        } catch (err) {
            console.error('Error analyzing option:', err);
        }
        setAnalyzingOption(false);
    };

    // Total Invested Calc
    const totalInvested = activeTab === 'active'
        ? Object.values(activeGroups).flat().reduce((sum, t) => sum + (t.entry_price * t.shares), 0)
        : 0;

    const totalOpenPnl = Object.values(activeGroups).flat().reduce((sum, t) => {
        const current = (liveData[t.ticker]?.price || t.entry_price);
        return sum + ((current - t.entry_price) * t.shares);
    }, 0);

    // Avg Days Open (matching USA Journal)
    const openPositions = Object.values(activeGroups).flat();
    const avgDaysOpen = openPositions.length > 0
        ? openPositions.reduce((sum, t) => {
            const start = new Date(t.entry_date);
            const end = new Date();
            const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24));
            return sum + days;
        }, 0) / openPositions.length
        : 0;

    // Open R.O.I. (matching USA Journal)
    const openRoi = totalInvested > 0 ? (totalOpenPnl / totalInvested) * 100 : 0;

    return (
        <div className="p-4 container mx-auto max-w-[1600px]">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        🇦🇷 Journal Argentina
                        <button onClick={() => fetchLivePrices(true)} disabled={refreshing} className="text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2 py-1 rounded transition text-slate-400 ml-4">
                            {refreshing ? '↻ Syncing...' : `↻ Refresh Prices ${lastUpdated ? `(${lastUpdated.toLocaleTimeString()})` : ''}`}
                        </button>
                    </h2>
                </div>
                <div className="flex gap-2">
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        style={{ display: 'none' }}
                        accept=".csv"
                    />
                    <button onClick={handleDownloadTemplate} className="bg-slate-800 hover:bg-slate-700 text-slate-400 px-3 py-2 rounded-lg font-medium transition text-sm border border-slate-700" title="Download Template">
                        ⬇️ CSV
                    </button>
                    <button onClick={handleImportClick} className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-slate-600">
                        Import CSV
                    </button>
                    <button onClick={() => setShowAddForm(!showAddForm)} className="bg-sky-600 hover:bg-sky-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm">
                        {showAddForm ? 'Cancelar' : '➕ Nueva Posición'}
                    </button>
                    <button onClick={() => setActiveSubTab('options')} className="bg-purple-900/50 hover:bg-purple-800 text-purple-200 px-4 py-2 rounded-lg font-medium transition text-sm border border-purple-800">
                        📊 Options Analyzer
                    </button>
                    <button
                        onClick={handleAnalyzePortfolio}
                        disabled={aiAnalyzing}
                        className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm shadow-lg"
                    >
                        {aiAnalyzing ? '🔄 Analyzing...' : '🤖 AI Insights'}
                    </button>
                </div>
            </div>

            {/* Rates Bar */}
            <div className="bg-slate-800/50 rounded-lg p-3 mb-6 flex items-center gap-6 text-sm border border-slate-700">
                <span className="text-slate-400">Cotizaciones:</span>
                <span className="text-green-400 font-mono">CCL: ${rates.ccl?.toLocaleString()}</span>
                <span className="text-blue-400 font-mono">MEP: ${rates.mep?.toLocaleString()}</span>
                <span className="text-purple-400 font-mono">Oficial: ${rates.oficial?.toLocaleString()}</span>
                <div className="ml-auto flex gap-1">
                    <span className="text-xs text-slate-500 mr-2">Ver en:</span>
                    {['ars', 'usd_ccl', 'usd_mep', 'usd_oficial'].map(c => (
                        <button key={c} onClick={() => setDisplayCurrency(c)}
                            className={`px-2 py-1 rounded text-[10px] font-bold transition ${displayCurrency === c ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white bg-slate-700'}`}>
                            {c === 'ars' ? 'ARS' : c.replace('usd_', '').toUpperCase()}
                        </button>
                    ))}
                </div>
            </div>

            {/* AI Insight Display */}
            {aiInsight && (
                <div className="mb-6 bg-gradient-to-r from-purple-900/30 to-blue-900/30 border border-purple-500/30 rounded-xl p-4">
                    <div className="flex justify-between items-start mb-3">
                        <h3 className="text-purple-400 font-bold flex items-center gap-2">
                            🤖 AI Portfolio Analysis (Argentina)
                        </h3>
                        <button onClick={() => setAiInsight(null)} className="text-slate-500 hover:text-white text-sm">✕ Close</button>
                    </div>
                    {(() => {
                        const text = aiInsight;
                        const sentimentMatch = text.match(/\*\*Sentiment:\*\*\s*(\d+)\/100\s*\(([^)]+)\)/);
                        const analysisMatch = text.match(/\*\*Analysis:\*\*\s*([\s\S]*?)(?=\*\*Actionable|$)/);
                        const actionMatch = text.match(/\*\*Actionable Insight:\*\*\s*([\s\S]*?)$/);

                        if (sentimentMatch) {
                            const score = parseInt(sentimentMatch[1]);
                            const mood = sentimentMatch[2];
                            const analysis = analysisMatch ? analysisMatch[1].trim() : '';
                            const action = actionMatch ? actionMatch[1].trim() : '';

                            const moodColor = score >= 60 ? 'text-green-400' : score >= 40 ? 'text-yellow-400' : 'text-red-400';
                            const barColor = score >= 60 ? 'bg-green-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500';

                            return (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-4">
                                        <div className="flex-1">
                                            <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                                                <div className={`${barColor} h-full rounded-full transition-all duration-500`} style={{ width: `${score}%` }}></div>
                                            </div>
                                        </div>
                                        <span className={`text-lg font-bold ${moodColor}`}>{score}/100 {mood}</span>
                                    </div>
                                    {analysis && <p className="text-slate-300 text-sm">{analysis}</p>}
                                    {action && (
                                        <div className="bg-blue-900/40 rounded-lg p-3 border border-blue-500/30">
                                            <span className="text-blue-400 font-bold text-xs">🎯 ACTION:</span>
                                            <p className="text-white text-sm mt-1">{action}</p>
                                        </div>
                                    )}
                                </div>
                            );
                        }
                        return <p className="text-slate-300 text-sm whitespace-pre-wrap">{text.replace(/\*\*/g, '')}</p>;
                    })()}
                </div>
            )}

            {/* Sell Modal */}
            {showSellModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm animate-fade-in">
                    <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            💸 Venta Parcial: {sellData.ticker}
                        </h3>

                        <div className="space-y-4">
                            <div>
                                <label className="text-slate-400 text-xs uppercase font-bold block mb-1">Cantidad a Vender (Max: {sellData.currentShares})</label>
                                <input
                                    type="number"
                                    value={sellData.sharesToSell || ''}
                                    onChange={(e) => setSellData({ ...sellData, sharesToSell: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white font-mono text-lg focus:ring-2 focus:ring-blue-500 outline-none"
                                    placeholder="Todo"
                                />
                                <div className="flex justify-end mt-1">
                                    <button
                                        onClick={() => setSellData({ ...sellData, sharesToSell: sellData.currentShares })}
                                        className="text-xs text-blue-400 hover:text-blue-300"
                                    >
                                        Vender Todo ({sellData.currentShares})
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="text-slate-400 text-xs uppercase font-bold block mb-1">Precio de Salida</label>
                                <input
                                    type="number"
                                    value={sellData.exitPrice || ''}
                                    onChange={(e) => setSellData({ ...sellData, exitPrice: e.target.value })}
                                    className="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white font-mono text-lg focus:ring-2 focus:ring-green-500 outline-none"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 mt-6">
                            <button
                                onClick={() => setShowSellModal(false)}
                                className="bg-slate-700 hover:bg-slate-600 text-white py-3 rounded-lg font-bold transition"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={async () => {
                                    if (!sellData.exitPrice) return alert("Ingresa precio de salida");

                                    try {
                                        await axios.post(`${API_BASE}/argentina/positions/${sellData.positionId}/close`, null, {
                                            params: {
                                                exit_price: parseFloat(sellData.exitPrice),
                                                shares: sellData.sharesToSell ? parseFloat(sellData.sharesToSell) : null
                                            }
                                        });
                                        setShowSellModal(false);
                                        fetchEssentialData();
                                    } catch (err) {
                                        alert("Error cerrando posición: " + (err.response?.data?.detail || err.message));
                                    }
                                }}
                                className="bg-red-600 hover:bg-red-500 text-white py-3 rounded-lg font-bold transition shadow-lg shadow-red-900/20"
                            >
                                📉 VENDER
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Add Position Form - UPDATED with targets */}
            {showAddForm && (
                <div className="bg-slate-800/70 rounded-xl p-4 mb-6 border border-slate-700">
                    <h3 className="text-lg font-bold text-white mb-4">Nueva Posición Argentina</h3>
                    <form onSubmit={handleAddPosition} className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <input type="text" placeholder="Ticker" value={formData.ticker} onChange={e => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })} className="bg-slate-700 rounded p-2 text-white text-sm" required />
                        <select value={formData.asset_type} onChange={e => setFormData({ ...formData, asset_type: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm">
                            <option value="stock">Acción</option>
                            <option value="cedear">CEDEAR</option>
                            <option value="option">Opción</option>
                        </select>
                        <input type="date" value={formData.entry_date} onChange={e => setFormData({ ...formData, entry_date: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" />
                        <input type="number" placeholder="Precio Entrada (ARS)" value={formData.entry_price} onChange={e => setFormData({ ...formData, entry_price: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" required />
                        <input type="number" placeholder="Cantidad" value={formData.shares} onChange={e => setFormData({ ...formData, shares: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" required />
                        <input type="number" placeholder="Stop Loss" value={formData.stop_loss} onChange={e => setFormData({ ...formData, stop_loss: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" />
                        <input type="number" placeholder="Target 1" value={formData.target} onChange={e => setFormData({ ...formData, target: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" />
                        <input type="number" placeholder="Target 2" value={formData.target2} onChange={e => setFormData({ ...formData, target2: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" />
                        <input type="number" placeholder="Target 3" value={formData.target3} onChange={e => setFormData({ ...formData, target3: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" />
                        <input type="text" placeholder="Estrategia" value={formData.strategy} onChange={e => setFormData({ ...formData, strategy: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm" />
                        <div className="col-span-2 md:col-span-4 flex gap-2">
                            <textarea placeholder="Notas / Hipótesis" value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} className="bg-slate-700 rounded p-2 text-white text-sm flex-1" rows={2} />
                            <button type="submit" className="bg-green-600 hover:bg-green-500 text-white px-6 rounded font-bold">Agregar</button>
                            <button type="button" onClick={() => setShowAddForm(false)} className="bg-slate-600 hover:bg-slate-500 text-white px-4 rounded">Cancelar</button>
                        </div>
                    </form>
                </div>
            )}

            {/* Metrics Cards - Same as USA Journal */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <MetricCard label="Total Invested" value={`${currencySymbol}${convertToDisplay(totalInvested).toLocaleString('en-US', { maximumFractionDigits: 0 })}`} subtext={`${openPositions.length} open trades`} color="text-sky-400" />
                <MetricCard label="Open P&L $" value={`${totalOpenPnl >= 0 ? '+' : ''}${currencySymbol}${convertToDisplay(totalOpenPnl).toLocaleString('en-US', { maximumFractionDigits: 2 })}`} color={totalOpenPnl >= 0 ? "text-green-400" : "text-red-400"} />
                <MetricCard label="Avg Days (Open)" value={avgDaysOpen.toFixed(0)} subtext="Average Holding" color="text-yellow-400" />
                <MetricCard label="Open R.O.I." value={`${openRoi >= 0 ? '+' : ''}${openRoi.toFixed(2)}%`} color={openRoi >= 0 ? "text-green-400" : "text-red-400"} />
            </div>

            {/* Sub Tabs */}
            <div className="flex gap-4 border-b border-slate-800 mb-6">
                <button onClick={() => setActiveSubTab('log')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'log' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    📝 Journal
                </button>
                <button onClick={() => setActiveSubTab('analytics')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'analytics' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    ⚖️ Portfolio Analytics
                </button>
                <button onClick={() => setActiveSubTab('options')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'options' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    📊 Options Check
                </button>
            </div>

            {/* CONTENT AREA */}
            {activeSubTab === 'log' && (
                <div className="space-y-6">
                    <div className="flex gap-6 border-b border-slate-800 mb-6">
                        <button onClick={() => setActiveTab('active')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'active' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                            🚀 Active Positions
                        </button>
                        <button onClick={() => setActiveTab('history')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'history' ? 'border-sky-500 text-sky-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                            📜 History
                        </button>
                    </div>

                    <div className="bg-slate-900 border border-slate-700 overflow-x-auto overflow-y-auto max-h-[80vh] rounded-lg shadow-xl">
                        <table className="w-full text-left text-[11px] whitespace-nowrap">
                            <thead className="bg-[#0f172a] text-slate-400 uppercase font-bold border-b border-slate-600 select-none">
                                <tr>
                                    <th onClick={() => requestSort('ticker')} className="p-2 border-r border-slate-800 sticky left-0 bg-[#0f172a] z-10 cursor-pointer hover:text-white transition">
                                        Ticker <span className="text-[9px] ml-1">{getSortIcon('ticker')}</span>
                                    </th>
                                    <th className="p-2 border-r border-slate-800">Fecha</th>
                                    <th onClick={() => requestSort('avgPpc')} className="p-2 text-right border-r border-slate-800 text-yellow-300 cursor-pointer hover:text-white transition">
                                        PPC <span className="text-[9px] ml-1">{getSortIcon('avgPpc')}</span>
                                    </th>
                                    <th onClick={() => requestSort('displayShares')} className="p-2 text-right border-r border-slate-800 cursor-pointer hover:text-white transition">
                                        Qty <span className="text-[9px] ml-1">{getSortIcon('displayShares')}</span>
                                    </th>
                                    <th onClick={() => requestSort('displayCost')} className="p-2 text-right border-r border-slate-800 cursor-pointer hover:text-white transition">
                                        Cost <span className="text-[9px] ml-1">{getSortIcon('displayCost')}</span>
                                    </th>
                                    <th onClick={() => requestSort('totalPnl')} className="p-2 text-right border-r border-slate-800 text-blue-300 font-bold cursor-pointer hover:text-white transition">
                                        P/L $ <span className="text-[9px] ml-1">{getSortIcon('totalPnl')}</span>
                                    </th>
                                    <th onClick={() => requestSort('displayPrice')} className="p-2 text-right border-r border-slate-800 text-blue-300 font-bold cursor-pointer hover:text-white transition">
                                        {activeTab === 'history' ? 'Avg Exit' : '$ Last'} <span className="text-[9px] ml-1">{getSortIcon('displayPrice')}</span>
                                    </th>
                                    <th onClick={() => requestSort('dayChange')} className="p-2 text-right border-r border-slate-800 cursor-pointer hover:text-white transition">
                                        % Hoy <span className="text-[9px] ml-1">{getSortIcon('dayChange')}</span>
                                    </th>
                                    <th onClick={() => requestSort('totalPnlPct')} className="p-2 border-r border-slate-800 text-right font-bold text-white cursor-pointer hover:text-blue-400 transition">
                                        % Trade <span className="text-[9px] ml-1">{getSortIcon('totalPnlPct')}</span>
                                    </th>
                                    <th className="p-2 border-r border-slate-800 text-center text-red-400">SL</th>
                                    <th className="p-2 border-r border-slate-800 text-center text-green-400">TP1</th>
                                    <th className="p-2 border-r border-slate-800 text-center text-green-400">TP2</th>
                                    <th className="p-2 border-r border-slate-800 text-center text-green-400">TP3</th>
                                    <th onClick={() => requestSort('daysHeld')} className="p-2 border-r border-slate-800 text-center cursor-pointer hover:text-white transition">
                                        Days <span className="text-[9px] ml-1">{getSortIcon('daysHeld')}</span>
                                    </th>
                                    <th className="p-2 border-r border-slate-800">Strategy</th>
                                    <th className="p-2 text-center border-r border-slate-800">EMA 8</th>
                                    <th className="p-2 text-center border-r border-slate-800">Actions</th>
                                    <th className="p-2 text-center border-r border-slate-800">EMA 21</th>
                                    <th className="p-2 text-center border-r border-slate-800">EMA 35</th>
                                    <th className="p-2 text-center">EMA 200</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                                {sortedRows.map((row) => {
                                    const {
                                        ticker, groupTrades, avgPpc, displayShares, displayCost,
                                        totalPnl, displayPrice, totalPnlPct, daysHeld, emas, currentPrice, dayChange
                                    } = row;

                                    const isExpanded = expandedGroups[ticker];

                                    // SL/TP logic for first trade (closest approximation for group)
                                    const slVal = parseFloat(groupTrades[0]?.stop_loss);
                                    const tp1Val = parseFloat(groupTrades[0]?.target);
                                    const tp2Val = parseFloat(groupTrades[0]?.target2);
                                    const tp3Val = parseFloat(groupTrades[0]?.target3);

                                    return (
                                        <Fragment key={ticker}>
                                            <tr className="bg-slate-900 hover:bg-slate-800 transition border-b border-slate-800 cursor-pointer" onClick={() => toggleGroup(ticker)}>
                                                <td className="p-2 border-r border-slate-800 font-bold text-sky-400 sticky left-0 bg-slate-900 z-10 flex items-center gap-2">
                                                    <span className="text-slate-500 text-[10px] w-4">{isExpanded ? '▼' : '▶'}</span>
                                                    {ticker}
                                                    <span className="text-slate-600 font-normal ml-1 text-[9px]">{groupTrades.length}</span>
                                                </td>
                                                <td className="p-2 border-r border-slate-800 text-slate-500 italic text-[10px]">{groupTrades[0].entry_date}</td>
                                                <td className="p-2 text-right border-r border-slate-800 text-yellow-200 font-mono font-bold">{currencySymbol}{convertToDisplay(avgPpc).toFixed(2)}</td>
                                                <td className="p-2 text-right border-r border-slate-800 text-slate-300 font-bold">{displayShares}</td>
                                                <td className="p-2 text-right border-r border-slate-800 text-slate-500">{currencySymbol}{convertToDisplay(displayCost).toFixed(0)}</td>
                                                <td className={`p-2 text-right border-r border-slate-800 font-bold font-mono ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {currencySymbol}{convertToDisplay(totalPnl).toFixed(0)}
                                                </td>
                                                <td className="p-2 text-right border-r border-slate-800 text-blue-200 font-mono font-bold">
                                                    {displayPrice ? `${currencySymbol}${convertToDisplay(displayPrice).toFixed(2)}` : '-'}
                                                </td>
                                                <td className={`p-2 text-right border-r border-slate-800 font-bold ${dayChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {dayChange ? `${dayChange.toFixed(2)}%` : '-'}
                                                </td>
                                                <td className={`p-2 text-right border-r border-slate-800 font-bold ${totalPnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {totalPnlPct.toFixed(2)}%
                                                </td>
                                                {/* Editable SL/TPs */}
                                                <td className="p-2 border-r border-slate-800 text-center">
                                                    <EditableCell value={slVal} onSave={(val) => handleUpdateGroup(groupTrades, 'stop_loss', val)} width="w-12" className="text-red-400" prefix={currencySymbol} />
                                                </td>
                                                <td className="p-2 border-r border-slate-800 text-center">
                                                    <EditableCell value={tp1Val} onSave={(val) => handleUpdateGroup(groupTrades, 'target', val)} width="w-12" className="text-green-400" prefix={currencySymbol} />
                                                </td>
                                                <td className="p-2 border-r border-slate-800 text-center">
                                                    <EditableCell value={tp2Val} onSave={(val) => handleUpdateGroup(groupTrades, 'target2', val)} width="w-12" className="text-green-400" prefix={currencySymbol} />
                                                </td>
                                                <td className="p-2 border-r border-slate-800 text-center">
                                                    <EditableCell value={tp3Val} onSave={(val) => handleUpdateGroup(groupTrades, 'target3', val)} width="w-12" className="text-green-400" prefix={currencySymbol} />
                                                </td>
                                                <td className="p-2 border-r border-slate-800 text-center font-bold text-slate-300">{daysHeld}</td>
                                                <td className="p-2 border-r border-slate-800 text-slate-500 italic text-[10px]">
                                                    <EditableCell value={groupTrades[0]?.strategy} onSave={(val) => handleUpdateGroup(groupTrades, 'strategy', val)} width="w-24" />
                                                </td>
                                                <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_8)}`}>
                                                    {emas.ema_8 ? <span>${emas.ema_8.toFixed(2)}</span> : '-'}
                                                </td>
                                                <td className="p-2 border-r border-slate-800 flex gap-1 justify-center">
                                                    <button
                                                        onClick={(e) => { e.stopPropagation(); setFormData({ ...formData, ticker }); setShowAddForm(true); }}
                                                        className="bg-green-600/20 hover:bg-green-600 text-green-400 hover:text-white px-2 py-0.5 rounded text-[10px] transition border border-green-600/30"
                                                        title="Comprar más"
                                                    >
                                                        +
                                                    </button>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            const tradeToClose = groupTrades.find(t => t.status === 'OPEN');
                                                            if (tradeToClose) {
                                                                setSellData({
                                                                    positionId: tradeToClose.id,
                                                                    ticker: ticker,
                                                                    currentShares: tradeToClose.shares,
                                                                    currentPrice: currentPrice || tradeToClose.entry_price,
                                                                    exitPrice: currentPrice || tradeToClose.entry_price,
                                                                    sharesToSell: '' // Default to empty (implies all if not set, or user types)
                                                                });
                                                                setShowSellModal(true);
                                                            } else {
                                                                alert("No hay posiciones abiertas para cerrar.");
                                                            }
                                                        }}
                                                        className="bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white px-2 py-0.5 rounded text-[10px] transition border border-red-600/30"
                                                        title="Vender / Cerrar Posición"
                                                    >
                                                        x
                                                    </button>
                                                </td>
                                                <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_21)}`}>
                                                    {emas.ema_21 ? <span>${emas.ema_21.toFixed(2)}</span> : '-'}
                                                </td>
                                                <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_35)}`}>
                                                    {emas.ema_35 ? <span>${emas.ema_35.toFixed(2)}</span> : '-'}
                                                </td>
                                                <td className={`p-2 text-center ${getEmaColor(currentPrice || 0, emas.ema_200)}`}>
                                                    {emas.ema_200 ? <span>${emas.ema_200.toFixed(2)}</span> : '-'}
                                                </td>
                                            </tr>

                                            {/* Detail Rows */}
                                            {isExpanded && groupTrades.map(t => (
                                                <tr key={t.id} className="bg-slate-900/50 hover:bg-slate-800/50 border-b border-slate-800 text-[10px]">
                                                    <td className="p-2 border-r border-slate-800 pl-8 text-slate-400 flex items-center gap-2">
                                                        <span>↳</span> {t.ticker}
                                                        <button onClick={() => handleDelete(t.id)} className="ml-2 text-red-500 hover:text-red-400 opacity-50 hover:opacity-100">🗑️</button>
                                                    </td>
                                                    <td className="p-2 border-r border-slate-800 text-slate-500">{t.entry_date}</td>
                                                    <td className="p-2 text-right border-r border-slate-800 text-yellow-500/70">{currencySymbol}{convertToDisplay(t.entry_price).toFixed(2)}</td>
                                                    <td className="p-2 text-right border-r border-slate-800 text-slate-500">{t.shares}</td>
                                                    <td colSpan="11" className="p-2 text-slate-600 italic">
                                                        {t.notes || 'No notes'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </Fragment>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* Trade History Summary (matching USA Journal) */}
                    {activeTab === 'history' && Object.keys(historyGroups).length > 0 && (() => {
                        const closedTrades = Object.values(historyGroups).flat();
                        const totalClosedPL = closedTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
                        const avgTradePercent = closedTrades.length > 0
                            ? closedTrades.reduce((sum, t) => sum + ((t.pnl / (t.entry_price * t.shares)) * 100 || 0), 0) / closedTrades.length
                            : 0;
                        const avgDays = closedTrades.length > 0
                            ? closedTrades.reduce((sum, t) => {
                                if (t.exit_date && t.entry_date) {
                                    const days = Math.floor((new Date(t.exit_date) - new Date(t.entry_date)) / (1000 * 60 * 60 * 24));
                                    return sum + days;
                                }
                                return sum;
                            }, 0) / closedTrades.length
                            : 0;
                        return (
                            <div className="mt-6 p-4 bg-slate-800/50 rounded-xl border border-slate-700">
                                <h3 className="text-sm font-bold text-slate-300 mb-3">📊 Trade History Summary</h3>
                                <div className="grid grid-cols-3 gap-4">
                                    <div className="text-center">
                                        <div className="text-[10px] text-slate-500 uppercase">Total Closed P&L</div>
                                        <div className={`text-lg font-bold ${totalClosedPL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {totalClosedPL >= 0 ? '+' : ''}{currencySymbol}{convertToDisplay(totalClosedPL).toFixed(2)}
                                        </div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-[10px] text-slate-500 uppercase">Avg % per Trade</div>
                                        <div className={`text-lg font-bold ${avgTradePercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {avgTradePercent >= 0 ? '+' : ''}{avgTradePercent.toFixed(2)}%
                                        </div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-[10px] text-slate-500 uppercase">Avg Days Held</div>
                                        <div className="text-lg font-bold text-white">
                                            {Math.round(avgDays)} days
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })()}
                </div>
            )}

            {activeSubTab === 'analytics' && (
                <PerformanceDashboard
                    data={openAnalytics}
                    performanceData={performanceData}
                    snapshotData={snapshotData}
                />
            )}

            {activeSubTab === 'options' && (
                /* Options Content (Preserved) */
                <div className="space-y-6">
                    <div className="bg-slate-800/50 rounded-xl p-6 border border-slate-700">
                        <h3 className="text-xl font-bold text-white mb-4">🔮 Analizador de Opciones (Black-Scholes)</h3>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
                            <input type="text" placeholder="Subyacente (ej: GGAL)" value={optionForm.underlying} onChange={e => setOptionForm({ ...optionForm, underlying: e.target.value.toUpperCase() })} className="bg-slate-700 rounded p-2 text-white" />
                            <input type="number" placeholder="Strike" value={optionForm.strike} onChange={e => setOptionForm({ ...optionForm, strike: e.target.value })} className="bg-slate-700 rounded p-2 text-white" />
                            <input type="date" value={optionForm.expiry} onChange={e => setOptionForm({ ...optionForm, expiry: e.target.value })} className="bg-slate-700 rounded p-2 text-white" />
                            <input type="number" placeholder="Precio Mercado" value={optionForm.market_price} onChange={e => setOptionForm({ ...optionForm, market_price: e.target.value })} className="bg-slate-700 rounded p-2 text-white" />
                            <select value={optionForm.option_type} onChange={e => setOptionForm({ ...optionForm, option_type: e.target.value })} className="bg-slate-700 rounded p-2 text-white">
                                <option value="call">Call</option>
                                <option value="put">Put</option>
                            </select>
                        </div>
                        <button onClick={handleAnalyzeOption} disabled={analyzingOption} className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-3 rounded-lg transition">
                            {analyzingOption ? 'Analizando...' : 'Calcular Probabilidades'}
                        </button>
                    </div>

                    {optionResult && (
                        <div className="space-y-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            {/* Header Summary */}
                            <div className="bg-slate-800 border border-slate-600 rounded-xl p-4 flex justify-between items-start">
                                <div>
                                    <h4 className="text-2xl font-bold text-white flex items-center gap-2">
                                        📈 {optionResult.ticker} <span className="text-sm font-normal text-slate-400">| Spot: ${optionResult.spot_price}</span>
                                    </h4>
                                    <div className="text-slate-400 text-sm mt-1">
                                        Strike: <span className="text-white font-mono">{optionResult.strike}</span> | Vencimiento: <span className="text-white">{optionResult.days_to_expiry} días</span> ({optionResult.expiry})
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-xs text-slate-500">Precio Justo BS</div>
                                    <div className="text-xl font-bold text-sky-400 font-mono">${optionResult.theoretical_price?.toFixed(2)}</div>
                                    <div className={`text-xs ${optionResult.fair_value_diff_pct < 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {optionResult.fair_value_diff_pct}% vs Mercado (${optionResult.market_price})
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {/* Volatility & Technicals */}
                                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                                    <h5 className="text-slate-400 font-bold text-xs uppercase mb-3">🛠️ Análisis Técnico & Volatilidad</h5>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Volatilidad Histórica (HV):</span>
                                            <span className="text-white font-mono">{optionResult.volatility.hv}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">Volatilidad Implícita (IV):</span>
                                            <span className={`font-mono ${parseFloat(optionResult.volatility.value) < parseFloat(optionResult.volatility.hv) + 5 ? 'text-green-400' : 'text-red-400'}`}>
                                                {optionResult.volatility.value}
                                            </span>
                                        </div>
                                        <div className="h-px bg-slate-800 my-2"></div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">RSI (14):</span>
                                            <span className={`font-mono ${optionResult.technicals?.rsi > 50 ? 'text-green-400' : 'text-red-400'}`}>
                                                {optionResult.technicals?.rsi}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-slate-500">SMA 20:</span>
                                            <span className="text-white font-mono">${optionResult.technicals?.sma_20}</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Greeks */}
                                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                                    <h5 className="text-slate-400 font-bold text-xs uppercase mb-3">📐 Letras Griegas</h5>
                                    <div className="grid grid-cols-2 gap-2 text-sm">
                                        <div className="bg-slate-800 p-2 rounded">
                                            <div className="text-slate-500 text-[10px]">Delta</div>
                                            <div className="text-white font-mono">{optionResult.greeks.delta}</div>
                                        </div>
                                        <div className="bg-slate-800 p-2 rounded">
                                            <div className="text-slate-500 text-[10px]">Gamma</div>
                                            <div className="text-white font-mono">{optionResult.greeks.gamma}</div>
                                        </div>
                                        <div className="bg-slate-800 p-2 rounded">
                                            <div className="text-slate-500 text-[10px]">Theta</div>
                                            <div className="text-red-400 font-mono">{optionResult.greeks.theta}</div>
                                        </div>
                                        <div className="bg-slate-800 p-2 rounded">
                                            <div className="text-slate-500 text-[10px]">Vega</div>
                                            <div className="text-white font-mono">{optionResult.greeks.vega}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Signal Component */}
                            <div className={`rounded-xl p-4 border-l-4 shadow-lg flex items-center gap-4 ${optionResult.analysis?.comp_signal.includes('NO OPERAR') ? 'bg-red-900/20 border-red-500' :
                                optionResult.analysis?.comp_signal.includes('RIESGO') ? 'bg-orange-900/20 border-orange-500' :
                                    'bg-green-900/20 border-green-500'
                                }`}>
                                <div className={`text-3xl ${optionResult.analysis?.comp_signal.includes('NO OPERAR') ? 'text-red-500' :
                                    optionResult.analysis?.comp_signal.includes('RIESGO') ? 'text-orange-500' :
                                        'text-green-500'
                                    }`}>
                                    {optionResult.analysis?.comp_signal.includes('NO OPERAR') ? '⛔' : optionResult.analysis?.comp_signal.includes('RIESGO') ? '⚠️' : '🚀'}
                                </div>
                                <div>
                                    <div className="text-xs font-bold uppercase tracking-wider opacity-70">Señal Compuesta</div>
                                    <h3 className="text-2xl font-bold text-white">{optionResult.analysis?.comp_signal}</h3>
                                    <div className="text-sm opacity-80 mt-1">
                                        Estrategia sugerida: <span className="font-bold">{optionResult.analysis?.strategies?.join(", ")}</span>
                                    </div>
                                </div>
                            </div>

                            {/* Detailed Checklist */}
                            <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-700">
                                <h5 className="text-slate-400 font-bold text-sm mb-3 border-b border-slate-700 pb-2">📋 Evaluación Detallada</h5>
                                <div className="space-y-2">
                                    {optionResult.analysis?.checks?.map((check, idx) => (
                                        <div key={idx} className="flex items-center gap-3 text-sm">
                                            <span className={check.pass ? 'text-green-400 text-lg' : 'text-red-400 text-lg'}>
                                                {check.pass ? '✅' : '❌'}
                                            </span>
                                            <div className="flex-1">
                                                <span className={check.pass ? 'text-slate-200' : 'text-slate-400'}>{check.label}</span>
                                                <span className="text-slate-600 ml-2 text-xs">({check.detail})</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {optionResult.analysis?.reasons?.length > 0 && (
                                    <div className="mt-4 bg-red-900/10 p-3 rounded border border-red-900/30">
                                        <div className="text-red-400 text-xs font-bold mb-1">MOTIVOS DEL NO OPERAR:</div>
                                        <ul className="list-disc list-inside text-xs text-red-300 space-y-1">
                                            {optionResult.analysis.reasons.map((r, i) => <li key={i}>{r}</li>)}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}



// Add Argentina Position Modal
function AddArgentinaModal({ onClose, onAdd }) {
    const [formData, setFormData] = useState({
        ticker: '', asset_type: 'stock', entry_date: new Date().toISOString().split('T')[0],
        entry_price: '', shares: '', strategy: '', hypothesis: '', notes: '',
        option_strike: '', option_expiry: '', option_type: 'call'
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await authFetch(`${API_BASE}/argentina/positions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            onAdd();
            onClose();
        } catch (e) {
            console.error(e);
            alert("Failed to add position");
        }
    };

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-lg">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-xl font-bold text-white">🇦🇷 Nueva Posición Argentina</h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-white">✕</button>
                </div>
                <form onSubmit={handleSubmit} className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                        <div>
                            <label className="text-xs text-slate-400 block mb-1">Ticker</label>
                            <input className="w-full bg-black/50 border border-slate-700 rounded p-2 text-white uppercase"
                                value={formData.ticker} onChange={e => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })} required autoFocus />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 block mb-1">Tipo de Activo</label>
                            <select className="w-full bg-black/50 border border-slate-700 rounded p-2 text-white"
                                value={formData.asset_type} onChange={e => setFormData({ ...formData, asset_type: e.target.value })}>
                                <option value="stock">Acción Local</option>
                                <option value="cedear">CEDEAR</option>
                                <option value="option">Opción</option>
                                <option value="bond">Bono</option>
                            </select>
                        </div>
                    </div>

                    {formData.asset_type === 'option' && (
                        <div className="bg-purple-900/20 p-3 rounded border border-purple-900/50 grid grid-cols-3 gap-2">
                            <div>
                                <label className="text-[10px] text-purple-300 block">Strike</label>
                                <input type="number" className="w-full bg-black/50 border border-purple-800 rounded p-1 text-white text-sm"
                                    value={formData.option_strike} onChange={e => setFormData({ ...formData, option_strike: parseFloat(e.target.value) })} />
                            </div>
                            <div>
                                <label className="text-[10px] text-purple-300 block">Vencimiento</label>
                                <input type="date" className="w-full bg-black/50 border border-purple-800 rounded p-1 text-white text-sm"
                                    value={formData.option_expiry} onChange={e => setFormData({ ...formData, option_expiry: e.target.value })} />
                            </div>
                            <div>
                                <label className="text-[10px] text-purple-300 block">Tipo</label>
                                <select className="w-full bg-black/50 border border-purple-800 rounded p-1 text-white text-sm"
                                    value={formData.option_type} onChange={e => setFormData({ ...formData, option_type: e.target.value })}>
                                    <option value="call">Call</option>
                                    <option value="put">Put</option>
                                </select>
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-3 gap-3">
                        <div>
                            <label className="text-xs text-slate-400 block mb-1">Cantidad</label>
                            <input type="number" step="any" className="w-full bg-black/50 border border-slate-700 rounded p-2 text-white"
                                value={formData.shares} onChange={e => setFormData({ ...formData, shares: parseFloat(e.target.value) })} required />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 block mb-1">Precio Entrada</label>
                            <input type="number" step="any" className="w-full bg-black/50 border border-slate-700 rounded p-2 text-white"
                                value={formData.entry_price} onChange={e => setFormData({ ...formData, entry_price: parseFloat(e.target.value) })} required />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 block mb-1">Fecha</label>
                            <input type="date" className="w-full bg-black/50 border border-slate-700 rounded p-2 text-white"
                                value={formData.entry_date} onChange={e => setFormData({ ...formData, entry_date: e.target.value })} required />
                        </div>
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 block mb-1">Estrategia / Hipotesis</label>
                        <textarea className="w-full bg-black/50 border border-slate-700 rounded p-2 text-white h-16 text-sm"
                            value={formData.hypothesis} onChange={e => setFormData({ ...formData, hypothesis: e.target.value })} placeholder="Ej: Rebote en soporte..." />
                    </div>

                    <div className="flex justify-end gap-2 pt-2">
                        <button type="button" onClick={onClose} className="px-4 py-2 text-slate-400 hover:text-white">Cancelar</button>
                        <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-bold">Guardar</button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// Argentina Journal Component
function ArgentinaJournal() {
    const [portfolio, setPortfolio] = useState({ holdings: [], total_ars: 0, total_mep: 0, total_ccl: 0 });
    const [showAddModal, setShowAddModal] = useState(false);
    const [loading, setLoading] = useState(false);

    const fetchPortfolio = async () => {
        setLoading(true);
        try {
            const res = await authFetch(`${API_BASE}/argentina/portfolio`);
            const data = await res.json();
            setPortfolio(data);
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    useEffect(() => {
        fetchPortfolio();
        const interval = setInterval(fetchPortfolio, 60000);
        return () => clearInterval(interval);
    }, []);

    const handleDelete = async (id) => {
        if (!confirm("Borrar posicion?")) return;
        await authFetch(`${API_BASE}/argentina/positions/${id}`, { method: 'DELETE' });
        fetchPortfolio();
    };

    return (
        <div className="p-4 container mx-auto max-w-[1600px]">
            {showAddModal && <AddArgentinaModal onClose={() => setShowAddModal(false)} onAdd={fetchPortfolio} />}

            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                        🇦🇷 Argentina Journal
                        <span className="text-xs bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">MERVAL</span>
                    </h2>
                    <div className="flex gap-4 mt-2 text-sm font-mono">
                        <span className="text-slate-400">ARS: <span className="text-white font-bold">${portfolio.total_ars?.toLocaleString()}</span></span>
                        <span className="text-slate-400">MEP: <span className="text-green-400 font-bold">${portfolio.total_mep?.toLocaleString()}</span></span>
                        <span className="text-slate-400">CCL: <span className="text-blue-400 font-bold">${portfolio.total_ccl?.toLocaleString()}</span></span>
                    </div>
                </div>
                <div>
                    <button onClick={() => setShowAddModal(true)} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-bold shadow-lg flex items-center gap-2">
                        <span>➕</span> Nueva Posición
                    </button>
                </div>
            </div>

            <div className="bg-[#0f0f0f] rounded-xl border border-[#2a2a2a] overflow-hidden">
                <table className="w-full text-sm text-left">
                    <thead className="bg-[#151515] text-slate-400 uppercase text-xs">
                        <tr>
                            <th className="px-6 py-4">Ticker</th>
                            <th className="px-6 py-4 text-right">Cantidad</th>
                            <th className="px-6 py-4 text-right">Entrada</th>
                            <th className="px-6 py-4 text-right">Actual</th>
                            <th className="px-6 py-4 text-right">Valor ARS</th>
                            <th className="px-6 py-4 text-right">P&L</th>
                            <th className="px-6 py-4 text-center">Tipo</th>
                            <th className="px-6 py-4 text-right">Acciones</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1a1a1a]">
                        {portfolio.holdings.length === 0 ? (
                            <tr><td colSpan="8" className="p-8 text-center text-slate-500">No hay posiciones activas.</td></tr>
                        ) : portfolio.holdings.map(pos => (
                            <tr key={pos.id} className="hover:bg-[#1a1a1a]">
                                <td className="px-6 py-4 font-bold text-white">{pos.ticker}</td>
                                <td className="px-6 py-4 text-right">{pos.shares}</td>
                                <td className="px-6 py-4 text-right text-slate-400">${pos.entry_price?.toLocaleString()}</td>
                                <td className="px-6 py-4 text-right text-white">
                                    {['option', 'OPCION', 'call', 'put'].includes((pos.asset_type || '').toLowerCase()) ? (
                                        <>
                                            <EditableCell
                                                value={pos.manual_price || pos.current_price}
                                                onSave={(val) => {
                                                    authFetch(`${API_BASE}/argentina/positions/${pos.id}/price`, {
                                                        method: 'PUT',
                                                        body: JSON.stringify({ price: parseFloat(val) })
                                                    })
                                                        .then(() => fetchPortfolio())
                                                        .catch(e => console.error(e));
                                                }}
                                                prefix="$" type="number" width="w-24"
                                                className={`text-right font-mono text-sm ${pos.manual_price ? 'text-yellow-400 font-bold' : 'text-slate-300'}`}
                                            />
                                            {pos.manual_price && <div className="text-[9px] text-yellow-500/60">MANUAL</div>}
                                        </>
                                    ) : (
                                        <span>${pos.current_price?.toLocaleString()}</span>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-right font-bold text-slate-200">${pos.value_ars?.toLocaleString()}</td>
                                <td className={`px-6 py-4 text-right font-bold ${pos.pnl_ars >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    ${pos.pnl_ars?.toLocaleString()} ({pos.pnl_pct}%)
                                </td>
                                <td className="px-6 py-4 text-center">
                                    <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${pos.asset_type === 'stock' ? 'bg-blue-900/30 text-blue-300' : pos.asset_type === 'cedear' ? 'bg-orange-900/30 text-orange-300' : 'bg-purple-900/30 text-purple-300'}`}>
                                        {pos.asset_type}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-right">
                                    <button onClick={() => handleDelete(pos.id)} className="text-slate-600 hover:text-red-400">🗑️</button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// Add Crypto Position Modal (Full Parity)
function AddCryptoModal({ onClose, onAdd }) {
    const [formData, setFormData] = useState({
        ticker: '', amount: '', entry_price: '',
        entry_date: new Date().toISOString().split('T')[0],
        strategy: '', stop_loss: '', target: '', notes: ''
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const res = await authFetch('/api/crypto/positions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: formData.ticker,
                    amount: parseFloat(formData.amount),
                    entry_price: parseFloat(formData.entry_price),
                    entry_date: formData.entry_date,
                    strategy: formData.strategy,
                    stop_loss: formData.stop_loss ? parseFloat(formData.stop_loss) : null,
                    target: formData.target ? parseFloat(formData.target) : null,
                    notes: formData.notes,
                    source: 'MANUAL'
                })
            });
            if (res.ok) {
                onAdd();
                onClose();
            } else {
                alert('Error adding position');
            }
        } catch (err) {
            console.error(err);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#1a1a1a] rounded-xl border border-[#2a2a2a] w-full max-w-2xl p-6 shadow-2xl">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                        <span>🪙</span> Add Crypto Position
                    </h3>
                    <button onClick={onClose} className="text-slate-500 hover:text-white">✕</button>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <label className="text-xs text-slate-400 font-bold uppercase">Ticker</label>
                            <input className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white uppercase font-mono tracking-wider focus:border-orange-500 outline-none"
                                value={formData.ticker} onChange={e => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })} required placeholder="BTC" autoFocus />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 font-bold uppercase">Date</label>
                            <input type="date" className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white focus:border-orange-500 outline-none"
                                value={formData.entry_date} onChange={e => setFormData({ ...formData, entry_date: e.target.value })} required />
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 font-bold uppercase">Strategy</label>
                            <input className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white focus:border-orange-500 outline-none"
                                value={formData.strategy} onChange={e => setFormData({ ...formData, strategy: e.target.value })} placeholder="e.g. Breakout" />
                        </div>
                    </div>

                    <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800">
                        <h4 className="text-xs text-slate-500 font-bold uppercase mb-3 border-b border-slate-800 pb-1">Trade Details</h4>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs text-slate-400 font-bold uppercase">Amount (Coins)</label>
                                <input type="number" step="any" className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white font-mono focus:border-orange-500 outline-none"
                                    value={formData.amount} onChange={e => setFormData({ ...formData, amount: e.target.value })} required placeholder="e.g. 0.5" />
                            </div>
                            <div>
                                <label className="text-xs text-slate-400 font-bold uppercase">Entry Price ($)</label>
                                <input type="number" step="any" className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white font-mono focus:border-orange-500 outline-none"
                                    value={formData.entry_price} onChange={e => setFormData({ ...formData, entry_price: e.target.value })} required placeholder="e.g. 50000" />
                            </div>
                        </div>
                    </div>

                    <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-800">
                        <h4 className="text-xs text-slate-500 font-bold uppercase mb-3 border-b border-slate-800 pb-1">Risk Management</h4>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="text-xs text-slate-400 font-bold uppercase">Stop Loss ($)</label>
                                <input type="number" step="any" className="w-full bg-[#0a0a0a] border border-red-900/50 rounded p-2 text-red-200 font-mono focus:border-red-500 outline-none"
                                    value={formData.stop_loss} onChange={e => setFormData({ ...formData, stop_loss: e.target.value })} placeholder="Optional" />
                            </div>
                            <div>
                                <label className="text-xs text-slate-400 font-bold uppercase">Target / TP ($)</label>
                                <input type="number" step="any" className="w-full bg-[#0a0a0a] border border-green-900/50 rounded p-2 text-green-200 font-mono focus:border-green-500 outline-none"
                                    value={formData.target} onChange={e => setFormData({ ...formData, target: e.target.value })} placeholder="Optional" />
                            </div>
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-slate-400 font-bold uppercase">Notes</label>
                        <textarea className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white h-20 outline-none focus:border-orange-500"
                            value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} placeholder="Analysis, thesis, etc." />
                    </div>

                    <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-800">
                        <button type="button" onClick={onClose} className="px-6 py-2 text-slate-400 hover:text-white transition">Cancel</button>
                        <button type="submit" className="px-8 py-2 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500 text-white rounded shadow-lg shadow-orange-900/20 font-bold transition transform hover:scale-105">
                            Add Position
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// Close Crypto Position Modal
// Close Crypto Position Modal
function CloseCryptoModal({ position, onClose, onSave }) {
    const [formData, setFormData] = useState({
        exit_price: position.current_price || '',
        amount: position.amount, // Default to full amount
        exit_date: new Date().toISOString().split('T')[0],
        notes: ''
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await authFetch(`/api/crypto/positions/${position.id}/close`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    exit_price: parseFloat(formData.exit_price),
                    amount: parseFloat(formData.amount),
                    exit_date: formData.exit_date,
                    notes: formData.notes
                })
            });
            onSave();
            onClose();
        } catch (err) {
            console.error(err);
            alert('Failed to close position: ' + (err.message || 'Unknown error'));
        }
    };

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4 animate-fade-in">
            <div className="bg-[#1a1a1a] rounded-xl border border-[#2a2a2a] w-full max-w-md p-6 shadow-2xl">
                <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <span>🏁</span> Close Position: <span className="text-orange-400">{position.ticker}</span>
                </h3>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-xs text-slate-400 font-bold uppercase">Amount to Sell</label>
                            <div className="relative">
                                <input type="number" step="any" className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white font-mono focus:border-blue-500 outline-none"
                                    value={formData.amount}
                                    onChange={e => setFormData({ ...formData, amount: e.target.value })}
                                    max={position.amount}
                                    required />
                                <span className="absolute right-2 top-2 text-xs text-slate-600">/ {position.amount}</span>
                            </div>
                        </div>
                        <div>
                            <label className="text-xs text-slate-400 font-bold uppercase">Exit Price ($)</label>
                            <input type="number" step="any" className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white font-mono focus:border-blue-500 outline-none"
                                value={formData.exit_price} onChange={e => setFormData({ ...formData, exit_price: e.target.value })} required />
                        </div>
                    </div>

                    <div>
                        <label className="text-xs text-slate-400 font-bold uppercase">Exit Date</label>
                        <input type="date" className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white focus:border-blue-500 outline-none"
                            value={formData.exit_date} onChange={e => setFormData({ ...formData, exit_date: e.target.value })} required />
                    </div>
                    <div>
                        <label className="text-xs text-slate-400 font-bold uppercase">Closing Notes</label>
                        <textarea className="w-full bg-[#0a0a0a] border border-[#2a2a2a] rounded p-2 text-white h-20 outline-none focus:border-blue-500"
                            value={formData.notes} onChange={e => setFormData({ ...formData, notes: e.target.value })} placeholder="Reason for exit..." />
                    </div>
                    <div className="flex justify-end gap-2 mt-6">
                        <button type="button" onClick={onClose} className="px-4 py-2 text-slate-400 hover:text-white transition">Cancel</button>
                        <button type="submit" className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-bold shadow-lg transition">Confirm Close</button>
                    </div>
                </form>
            </div>
        </div>
    );
}


// Crypto Journal Component (Full Parity)
function CryptoJournal() {
    const [positions, setPositions] = useState([]);
    const [history, setHistory] = useState([]);
    const [metrics, setMetrics] = useState({ total_invested: 0, total_value: 0, total_pnl: 0 });
    const [showAddModal, setShowAddModal] = useState(false);
    const [closeModalPos, setCloseModalPos] = useState(null);

    // Tab navigation
    const [activeTab, setActiveTab] = useState('active'); // 'active' | 'history'
    const [activeSubTab, setActiveSubTab] = useState('log'); // 'log' | 'analytics'

    // Analytics Data
    const [openAnalytics, setOpenAnalytics] = useState(null);
    const [performanceData, setPerformanceData] = useState(null);
    const [snapshotData, setSnapshotData] = useState([]);

    // AI
    const [aiInsight, setAiInsight] = useState(null);
    const [aiAnalyzing, setAiAnalyzing] = useState(false);

    // Sorting
    const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });

    const fetchData = async () => {
        try {
            // Fetch Open Positions
            const res = await authFetch('/api/crypto/positions');
            if (res.ok) {
                const data = await res.json();
                setPositions(data.positions || []);
                setMetrics(data.metrics || { total_invested: 0, total_value: 0, total_pnl: 0 });
            }

            // Fetch History if needed (lazy load or always load)
            const histRes = await authFetch('/api/crypto/trades/history');
            if (histRes.ok) {
                const histData = await histRes.json();
                setHistory(histData || []);
            }

        } catch (err) {
            console.error(err);
        }
    };

    const handleAnalyzePortfolio = async () => {
        setAiAnalyzing(true);
        try {
            const res = await authFetch('/api/crypto/ai/portfolio-insight');
            const data = await res.json();
            setAiInsight(data.insight);
        } catch (err) {
            setAiInsight('Error analyzing portfolio.');
        }
        setAiAnalyzing(false);
    };

    // Fetch analytics data
    const fetchHeavyData = async () => {
        try {
            const [anaRes, perfRes, snapRes] = await Promise.all([
                axios.get('/api/crypto/trades/analytics/open').catch(e => ({ data: null })),
                axios.get('/api/crypto/trades/analytics/performance').catch(e => ({ data: null })),
                axios.get('/api/crypto/trades/snapshots').catch(e => ({ data: [] }))
            ]);
            setOpenAnalytics(anaRes.data);
            setPerformanceData(perfRes.data);
            setSnapshotData(snapRes.data || []);
        } catch (err) {
            console.error('Error fetching crypto analytics:', err);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 60000);
        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        if (activeSubTab === 'analytics') fetchHeavyData();
    }, [activeSubTab]);

    const requestSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        setSortConfig({ key, direction });
    };

    const getSortedData = () => {
        let data = activeTab === 'active' ? [...positions] : [...history];
        if (sortConfig.key) {
            data.sort((a, b) => {
                if (a[sortConfig.key] < b[sortConfig.key]) return sortConfig.direction === 'asc' ? -1 : 1;
                if (a[sortConfig.key] > b[sortConfig.key]) return sortConfig.direction === 'asc' ? 1 : -1;
                return 0;
            });
        }
        return data;
    };

    const sortedRows = getSortedData();

    // Import/Export
    const fileInputRef = React.useRef(null);
    const [importLoading, setImportLoading] = useState(false);
    const handleFileChange = async (event) => {
        const file = event.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append("file", file);
        setImportLoading(true);
        try {
            const res = await axios.post(`${API_BASE}/crypto/upload_csv`, formData, { headers: { "Content-Type": "multipart/form-data" } });
            alert(res.data.status === 'success' ? `Imported ${res.data.imported} trades!` : "Import failed");
            fetchData();
        } catch (e) { alert("Import failed: " + e.message); }
        setImportLoading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleDelete = async (id) => {
        if (!confirm('Delete this position completely?')) return;
        try {
            await authFetch(`/api/crypto/positions/${id}`, { method: 'DELETE' });
            fetchData();
        } catch (e) { console.error(e); }
    };


    return (
        <div className="p-4 container mx-auto max-w-[1600px]">
            {showAddModal && <AddCryptoModal onClose={() => setShowAddModal(false)} onAdd={fetchData} />}
            {closeModalPos && <CloseCryptoModal position={closeModalPos} onClose={() => setCloseModalPos(null)} onSave={fetchData} />}

            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 mb-1">
                        <span>🪙</span> Crypto Journal
                        <span className="text-xs bg-orange-600/20 text-orange-400 px-2 py-0.5 rounded-full">Pro</span>
                    </h2>
                    <p className="text-slate-400 text-xs">Advanced Crypto Portfolio Tracker</p>
                </div>
                <div className="flex gap-2">
                    <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} accept=".csv" />
                    <button onClick={() => window.location.href = `${API_BASE}/crypto/template`} className="bg-slate-800 hover:bg-slate-700 text-slate-400 px-3 py-2 rounded-lg text-sm border border-slate-700">⬇️ CSV</button>
                    <button onClick={() => fileInputRef.current.click()} className="bg-slate-700 hover:bg-slate-600 text-slate-200 px-4 py-2 rounded-lg text-sm border border-slate-600">{importLoading ? '...' : 'Import'}</button>

                    <button onClick={() => setShowAddModal(true)} className="bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500 text-white px-4 py-2 rounded-lg font-bold text-sm shadow-lg flex items-center gap-2">
                        <span>➕</span> Log Trade
                    </button>
                    <button onClick={handleAnalyzePortfolio} disabled={aiAnalyzing} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-bold text-sm shadow-lg">
                        {aiAnalyzing ? 'Analyzing...' : '🤖 AI Insight'}
                    </button>
                </div>
            </div>

            {/* AI Insight */}
            {aiInsight && (
                <div className="mb-6 bg-blue-900/20 border border-blue-500/30 rounded-xl p-4 relative">
                    <button onClick={() => setAiInsight(null)} className="absolute top-2 right-2 text-slate-500 hover:text-white">✕</button>
                    <h3 className="text-blue-400 font-bold mb-2">🤖 Portfolio Insight</h3>
                    <p className="text-slate-300 text-sm whitespace-pre-wrap">{aiInsight}</p>
                </div>
            )}

            {/* Metric Cards (Summary) */}
            {activeSubTab === 'log' && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-[#0f0f0f] rounded-xl p-4 border border-[#2a2a2a] relative overflow-hidden group">
                        <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition text-6xl">💰</div>
                        <div className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Total Value</div>
                        <div className="text-2xl font-bold text-white">${metrics.total_value?.toLocaleString()}</div>
                    </div>
                    <div className="bg-[#0f0f0f] rounded-xl p-4 border border-[#2a2a2a] relative overflow-hidden group">
                        <div className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Invested</div>
                        <div className="text-2xl font-bold text-white">${metrics.total_invested?.toLocaleString()}</div>
                    </div>
                    <div className="bg-[#0f0f0f] rounded-xl p-4 border border-[#2a2a2a] relative overflow-hidden group">
                        <div className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">Unrealized P&L</div>
                        <div className={`text-2xl font-bold ${metrics.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {metrics.total_pnl >= 0 ? '+' : ''}${metrics.total_pnl?.toLocaleString()}
                        </div>
                    </div>
                    <div className="bg-[#0f0f0f] rounded-xl p-4 border border-[#2a2a2a] relative overflow-hidden group">
                        <div className="text-slate-500 text-xs font-bold uppercase tracking-wider mb-1">ROI</div>
                        <div className={`text-2xl font-bold ${metrics.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {metrics.total_invested > 0 ? ((metrics.total_pnl / metrics.total_invested) * 100).toFixed(2) : '0.00'}%
                        </div>
                    </div>
                </div>
            )}

            {/* Sub-Tab Navigation */}
            <div className="flex gap-4 border-b border-slate-800 mb-6">
                <button onClick={() => setActiveSubTab('log')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'log' ? 'border-orange-500 text-orange-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    📋 Positions
                </button>
                <button onClick={() => setActiveSubTab('analytics')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'analytics' ? 'border-orange-500 text-orange-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    📊 Analytics
                </button>
            </div>

            {/* CONTENT AREA */}
            {activeSubTab === 'analytics' ? (
                <PerformanceDashboard data={openAnalytics} performanceData={performanceData} snapshotData={snapshotData} />
            ) : (
                <div className="space-y-6">
                    <div className="flex gap-6 border-b border-slate-800 mb-6">
                        <button onClick={() => setActiveTab('active')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'active' ? 'border-white text-white' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                            🚀 Active Positions ({positions.length})
                        </button>
                        <button onClick={() => setActiveTab('history')} className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'history' ? 'border-white text-white' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                            📜 Trade History
                        </button>
                    </div>

                    <div className="bg-[#111] border border-[#222] overflow-x-auto rounded-xl shadow-xl">
                        <table className="w-full text-left text-xs whitespace-nowrap">
                            <thead className="bg-[#1a1a1a] text-slate-400 uppercase font-bold border-b border-[#333]">
                                <tr>
                                    <th onClick={() => requestSort('ticker')} className="p-3 cursor-pointer hover:text-white">Ticker {sortConfig.key === 'ticker' ? (sortConfig.direction === 'asc' ? '▲' : '▼') : ''}</th>
                                    <th className="p-3">Date</th>
                                    <th onClick={() => requestSort('amount')} className="p-3 text-right cursor-pointer hover:text-white">Amount</th>
                                    <th onClick={() => requestSort('entry_price')} className="p-3 text-right cursor-pointer hover:text-white">Entry $</th>
                                    <th className="p-3 text-right">Last $</th>
                                    <th onClick={() => requestSort('value')} className="p-3 text-right cursor-pointer hover:text-white">Value</th>
                                    <th onClick={() => requestSort('pnl')} className="p-3 text-right cursor-pointer hover:text-white">P&L $</th>
                                    <th onClick={() => requestSort('pnl_pct')} className="p-3 text-right cursor-pointer hover:text-white">P&L %</th>
                                    <th className="p-3 text-center">SL / TP</th>
                                    <th className="p-3">Strategy</th>
                                    <th className="p-3 text-center">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-[#222]">
                                {sortedRows.map(pos => {
                                    const isClosed = activeTab === 'history';
                                    const price = isClosed ? pos.exit_price : (pos.current_price || pos.entry_price);

                                    // SL/TP warnings
                                    const slHit = !isClosed && pos.stop_loss && price <= pos.stop_loss;
                                    const tpHit = !isClosed && pos.target && price >= pos.target;

                                    return (
                                        <tr key={pos.id} className={`hover:bg-[#1a1a1a] transition ${slHit ? 'bg-red-900/10' : tpHit ? 'bg-green-900/10' : ''}`}>
                                            <td className="p-3 font-bold text-white border-l-2 border-transparent hover:border-orange-500">
                                                {pos.ticker}
                                                {slHit && <span className="ml-2 text-[10px] bg-red-600 px-1 rounded text-white">SL HIT</span>}
                                                {tpHit && <span className="ml-2 text-[10px] bg-green-600 px-1 rounded text-white">TP HIT</span>}
                                            </td>
                                            <td className="p-3 text-slate-500 font-mono text-[10px]">
                                                {pos.entry_date}
                                                {isClosed && <div className="text-slate-600">➜ {pos.exit_date}</div>}
                                            </td>
                                            <td className="p-3 text-right text-slate-300 font-mono">{pos.shares || pos.amount}</td>
                                            <td className="p-3 text-right text-slate-400 font-mono">${pos.entry_price?.toLocaleString()}</td>
                                            <td className="p-3 text-right text-blue-300 font-bold font-mono">
                                                ${price?.toLocaleString()}
                                            </td>
                                            <td className="p-3 text-right text-slate-200 font-mono font-bold">
                                                ${(price * (pos.shares || pos.amount)).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                            </td>
                                            <td className={`p-3 text-right font-bold font-mono ${pos.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                ${pos.pnl?.toLocaleString()}
                                            </td>
                                            <td className={`p-3 text-right font-bold ${pos.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {pos.pnl_pct?.toFixed(2)}%
                                            </td>
                                            <td className="p-3 text-center">
                                                <div className="text-[10px] text-red-400">SL: {pos.stop_loss || '-'}</div>
                                                <div className="text-[10px] text-green-400">TP: {pos.target || '-'}</div>
                                            </td>
                                            <td className="p-3 text-slate-500 text-[10px] italic">{pos.strategy || '-'}</td>
                                            <td className="p-3 text-center flex justify-center gap-2">
                                                {!isClosed && (
                                                    <button onClick={() => setCloseModalPos(pos)} className="px-2 py-1 bg-blue-900/40 border border-blue-800 text-blue-300 text-[10px] rounded hover:bg-blue-800 transition">
                                                        Close
                                                    </button>
                                                )}
                                                <button onClick={() => handleDelete(pos.id)} className="text-slate-600 hover:text-red-400 text-sm" title="Delete record">🗑️</button>
                                            </td>
                                        </tr>
                                    );
                                })}
                                {sortedRows.length === 0 && (
                                    <tr>
                                        <td colSpan="11" className="p-10 text-center text-slate-500">
                                            {activeTab === 'active' ? 'No active crypto positions.' : 'No closed trades history.'}
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}


// Sharpe Portfolio View Component
function SharpePortfolioView() {
    const [portfolio, setPortfolio] = useState(null);
    const [scanResults, setScanResults] = useState(null);
    const [loading, setLoading] = useState(false); // Changed to false - no auto-scan
    const [error, setError] = useState(null);
    const [minSharpe, setMinSharpe] = useState(1.5);
    const [maxPE, setMaxPE] = useState(50);
    const [strategy, setStrategy] = useState('undervalued');

    const fetchPortfolio = async () => {
        setLoading(true);
        setError(null);
        try {
            // optimized: Single call gets both portfolio and scan results
            const response = await fetch(`${API_BASE}/fundamental/portfolio?min_sharpe=${minSharpe}&max_positions=10&strategy=${strategy}`);

            if (response.ok) {
                const data = await response.json();

                if (data.error) {
                    setError(data.error);
                } else {
                    // Start fresh
                    setPortfolio(null);
                    setScanResults(null);

                    // Backend now returns {portfolio: {...}, scan_results: {...} }
                    if (data.portfolio) {
                        setPortfolio(data.portfolio);
                    } else {
                        // Fallback for legacy response
                        setPortfolio(data);
                    }

                    if (data.scan_results) {
                        setScanResults(data.scan_results);
                    }
                }
            } else {
                const errText = await response.text();
                setError(`Server Error: ${response.status} ${errText}`);
            }
        } catch (err) {
            setError("Failed to fetch data. Ensure server is running.");
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadPDF = () => {
        if (!scanResults || !scanResults.results) return;

        try {
            if (!window.jspdf) {
                alert("PDF library not loaded yet. Please refresh the page.");
                return;
            }
            const { jsPDF } = window.jspdf;
            const doc = new jsPDF('l'); // Landscape for more columns

            const tableColumn = ["Ticker", "Sharpe", "Price", "P/E", "Sector", "Outlook (3-6mo)"];
            const tableRows = [];

            scanResults.results.forEach(ticket => {
                const ticketData = [
                    ticket.ticker,
                    ticket.sharpe?.toFixed(2),
                    `$${ticket.price?.toFixed(2)}`,
                    ticket.pe_ratio ? ticket.pe_ratio.toFixed(1) : 'N/A',
                    ticket.sector || 'Unknown',
                    ticket.outlook || 'N/A'
                ];
                tableRows.push(ticketData);
            });

            doc.setFontSize(18);
            doc.text("Sharpe Portfolio Analysis", 14, 15);
            doc.setFontSize(10);
            doc.text(`Generated on: ${new Date().toLocaleString()}`, 14, 22);
            doc.text(`Filter: Min Sharpe ${minSharpe} | Max P/E ${maxPE}`, 14, 27);

            doc.autoTable({
                head: [tableColumn],
                body: tableRows,
                startY: 35,
                styles: { fontSize: 8, cellPadding: 2, overflow: 'linebreak' },
                columnStyles: { 5: { cellWidth: 80 } }, // Make Outlook column wider
                headStyles: { fillColor: [102, 51, 153], textColor: 255 }, // Purple for Sharpe
                margin: { top: 35 }
            });

            doc.save(`sharpe_portfolio_${new Date().toISOString().slice(0, 10)}.pdf`);
        } catch (error) {
            console.error("PDF Error:", error);
            alert("PDF Generation Failed");
        }
    };

    const handleDownloadExcel = () => {
        if (!scanResults || !scanResults.results) return;

        try {
            if (!window.XLSX) {
                alert("Excel library not loaded yet. Please refresh the page.");
                return;
            }
            const XLSX = window.XLSX;
            const dataToExport = scanResults.results.map(ticket => ({
                "Ticker": ticket.ticker,
                "Sharpe Ratio": ticket.sharpe,
                "Price": ticket.price,
                "P/E Ratio": ticket.pe_ratio,
                "Market Cap": formatMarketCap(ticket.market_cap),
                "Sector": ticket.sector,
                "Outlook (3-6 Months)": ticket.outlook || "N/A"
            }));

            const ws = XLSX.utils.json_to_sheet(dataToExport);
            const wb = XLSX.utils.book_new();
            XLSX.utils.book_append_sheet(wb, ws, "Sharpe Portfolio");
            XLSX.writeFile(wb, `sharpe_portfolio_${new Date().toISOString().slice(0, 10)}.xlsx`);
        } catch (error) {
            console.error("Excel Error:", error);
            alert("Excel Generation Failed");
        }
    };

    // Removed auto-scan on mount - user must click "Scan Portfolio" button

    const formatMarketCap = (cap) => {
        if (!cap) return 'N/A';
        if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`;
        if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`;
        if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
        return `$${cap.toLocaleString()}`;
    };

    return (
        <div className="p-4 container mx-auto max-w-[1600px]">
            <div className="mb-6">
                <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2 mb-2">
                    📊 Sharpe Portfolio Builder
                    <span className="text-xs bg-purple-600/20 text-purple-400 px-2 py-1 rounded-full">Fundamental</span>
                </h2>
                <p className="text-slate-400 text-sm">Portfolio optimizado por Sharpe Ratio usando datos del cache del Weekly RSI Scanner.</p>
            </div>

            {/* Filters */}
            <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700 mb-6">
                <div className="flex flex-wrap gap-4 items-end">
                    <div>
                        <label className="block text-xs text-slate-400 mb-1">Min Sharpe</label>
                        <input
                            type="number"
                            value={minSharpe}
                            onChange={(e) => setMinSharpe(parseFloat(e.target.value))}
                            step="0.1"
                            className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white w-24"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-slate-400 mb-1">Max P/E</label>
                        <input
                            type="number"
                            value={maxPE}
                            onChange={(e) => setMaxPE(parseFloat(e.target.value))}
                            className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white w-24"
                        />
                    </div>
                    <button
                        onClick={fetchPortfolio}
                        disabled={loading}
                        className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg font-medium transition disabled:opacity-50"
                    >
                        {loading ? '⏳ Scanning...' : '🔍 Scan Portfolio'}
                    </button>
                    <div className="ml-auto">
                        <label className="block text-xs text-slate-400 mb-1">Strategy Priority</label>
                        <select
                            value={strategy}
                            onChange={(e) => setStrategy(e.target.value)}
                            className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white w-48 text-sm"
                        >
                            <option value="undervalued">💎 Undervalued (PE &lt; 20)</option>
                            <option value="sharpe">🚀 High Sharpe Only</option>
                            <option value="balanced">⚖️ Balanced (Score)</option>
                        </select>
                    </div>
                </div>
            </div>

            {error && (
                <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-4 mb-6 text-red-400">
                    ⚠️ {error}
                </div>
            )}

            {loading && (
                <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                </div>
            )}

            {!loading && portfolio && portfolio.positions && (
                <>
                    {/* Summary Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                            <p className="text-slate-500 text-xs uppercase mb-1">Positions</p>
                            <p className="text-2xl font-bold text-purple-400">{portfolio.total_positions || 0}</p>
                        </div>
                        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                            <p className="text-slate-500 text-xs uppercase mb-1">Weight Each</p>
                            <p className="text-2xl font-bold text-white">{portfolio.weight_per_position?.toFixed(1)}%</p>
                        </div>
                        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                            <p className="text-slate-500 text-xs uppercase mb-1">Total Scanned</p>
                            <p className="text-2xl font-bold text-blue-400">{scanResults?.scanned || 0}</p>
                        </div>
                        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700">
                            <p className="text-slate-500 text-xs uppercase mb-1">Strategy</p>
                            <p className="text-lg font-bold text-green-400">{portfolio.strategy || 'Equal Weight'}</p>
                        </div>
                    </div>

                    {/* Portfolio Positions */}
                    <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden mb-6">
                        <div className="bg-slate-900/50 px-4 py-3 border-b border-slate-700">
                            <h3 className="font-bold text-white">📊 Portfolio Positions ({portfolio.portfolio_date})</h3>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-slate-900/30 text-xs uppercase text-slate-400">
                                    <tr>
                                        <th className="px-4 py-3 text-left">Ticker</th>
                                        <th className="px-4 py-3 text-left">Name</th>
                                        <th className="px-4 py-3 text-right">Sharpe</th>
                                        <th className="px-4 py-3 text-right">Price</th>
                                        <th className="px-4 py-3 text-center">Weight</th>
                                        <th className="px-4 py-3 text-left">Sector</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {portfolio.positions.map((pos, idx) => (
                                        <tr key={pos.ticker} className={`border-b border-slate-700/50 hover:bg-slate-800/30 ${idx === 0 ? 'bg-gradient-to-r from-purple-900/20 to-transparent' : ''}`}>
                                            <td className="px-4 py-3 font-bold text-purple-400">{pos.ticker}</td>
                                            <td className="px-4 py-3 text-slate-300 text-sm">{pos.name}</td>
                                            <td className={`px-4 py-3 text-right font-bold ${pos.sharpe >= 2 ? 'text-green-400' : 'text-yellow-400'}`}>
                                                {pos.sharpe?.toFixed(2)}
                                            </td>
                                            <td className="px-4 py-3 text-right text-white">${pos.price?.toFixed(2)}</td>
                                            <td className="px-4 py-3 text-center">
                                                <span className="bg-purple-600/30 text-purple-300 px-2 py-1 rounded-full text-xs font-bold">
                                                    {pos.weight}%
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 text-slate-400 text-sm">{pos.sector}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {/* All Candidates Table */}
            {!loading && scanResults && scanResults.results && scanResults.results.length > 0 && (
                <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
                    <div className="bg-slate-900/50 px-4 py-3 border-b border-slate-700">
                        <h3 className="font-bold text-white">🔍 All Candidates (Sharpe &gt; {minSharpe})</h3>
                        <div className="flex gap-2">
                            <button onClick={handleDownloadExcel} className="bg-green-700/50 hover:bg-green-600 text-white px-3 py-1 rounded text-xs transition">
                                📗 Excel
                            </button>
                            <button onClick={handleDownloadPDF} className="bg-slate-700 hover:bg-slate-600 text-white px-3 py-1 rounded text-xs transition">
                                📄 PDF
                            </button>
                        </div>
                    </div>
                    <div className="overflow-x-auto max-h-96">
                        <table className="w-full">
                            <thead className="bg-slate-900/30 text-xs uppercase text-slate-400 sticky top-0">
                                <tr>
                                    <th className="px-4 py-2 text-left">#</th>
                                    <th className="px-4 py-2 text-left">Ticker</th>
                                    <th className="px-4 py-2 text-right">Sharpe</th>
                                    <th className="px-4 py-2 text-right">P/E</th>
                                    <th className="px-4 py-2 text-left w-64">Outlook (3-6 Months)</th>
                                    <th className="px-4 py-2 text-right">Market Cap</th>
                                    <th className="px-4 py-2 text-right">Price</th>
                                    <th className="px-4 py-2 text-left">Sector</th>
                                </tr>
                            </thead>
                            <tbody className="text-sm">
                                {scanResults.results.map((stock, idx) => (
                                    <tr key={stock.ticker} className="border-b border-slate-700/30 hover:bg-slate-800/30">
                                        <td className="px-4 py-2 text-slate-500">{idx + 1}</td>
                                        <td className="px-4 py-2 font-bold text-white">{stock.ticker}</td>
                                        <td className={`px-4 py-2 text-right font-bold ${stock.sharpe >= 2 ? 'text-green-400' : 'text-blue-300'}`}>{stock.sharpe?.toFixed(2)}</td>
                                        <td className="px-4 py-2 text-right font-mono text-slate-300">{stock.pe_ratio ? stock.pe_ratio.toFixed(1) : '-'}</td>
                                        <td className="px-4 py-2 text-left text-xs text-slate-400 italic break-words max-w-xs">{stock.outlook || 'Analyzing...'}</td>
                                        <td className="px-4 py-2 text-right text-slate-400 text-xs">{formatMarketCap(stock.market_cap)}</td>
                                        <td className="px-4 py-2 text-right text-white">${stock.price?.toFixed(2)}</td>
                                        <td className="px-4 py-2 text-slate-400">{stock.sector}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {!loading && (!scanResults || !scanResults.results || scanResults.results.length === 0) && !error && (
                <div className="bg-slate-800/30 rounded-xl border border-dashed border-slate-700 p-12 text-center">
                    <span className="text-6xl mb-4 block">📊</span>
                    <h3 className="text-lg font-bold text-white mb-2">No hay candidatos</h3>
                    <p className="text-slate-400 text-sm mb-4">Ejecuta el Weekly RSI Scanner primero para llenar el cache con datos de precios.</p>
                </div>
            )}
        </div>
    );
}

// Debug Component
function DebugStatusChecker() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        authFetch(`${API_BASE}/debug/portfolio-check`)
            .then(res => res.json())
            .then(d => { setData(d); setLoading(false); })
            .catch(err => { console.error(err); setLoading(false); });
    }, []);

    if (loading) return <span className="text-xs text-slate-500">Checking DB...</span>;
    if (!data) return <span className="text-xs text-red-500">Debug check failed</span>;

    return (
        <div className="text-xs font-mono text-slate-300 bg-black/50 p-2 rounded">
            <pre>{JSON.stringify(data, null, 2)}</pre>
        </div>
    );
}

// Portfolio Dashboard View Component (Unified Multi-Currency)
function PortfolioDashboardView() {
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [displayCurrency, setDisplayCurrency] = useState('usd_ccl');
    const [history, setHistory] = useState([]);
    const [distribution, setDistribution] = useState({});
    const [chartMode, setChartMode] = useState('line'); // 'line' or 'bar'
    const [chartMetric, setChartMetric] = useState('value'); // 'value' or 'pnl'
    const [chartTimeframe, setChartTimeframe] = useState('1M'); // '1D', '1W', '1M', 'YTD', '1Y', 'Max'
    const [benchmarkData, setBenchmarkData] = useState(null);

    const { ResponsiveContainer, AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Cell, PieChart, Pie, Legend } = Recharts;

    useEffect(() => {
        fetchAllData();
    }, []);

    const fetchAllData = async () => {
        setLoading(true);

        // 1. Fetch History (Fast, from DB)
        try {
            const historyRes = await authFetch(`${API_BASE}/portfolio/snapshots?days=365`);
            if (historyRes.ok) {
                const histData = await historyRes.json();
                setHistory(histData || []);
            }
        } catch (err) {
            console.error('Error fetching history:', err);
        }

        // 2. Fetch Distribution (Fast, from DB)
        try {
            const distRes = await authFetch(`${API_BASE}/portfolio/distribution`);
            if (distRes.ok) {
                const distData = await distRes.json();
                setDistribution(distData || {});
            }
        } catch (err) {
            console.error('Error fetching distribution:', err);
        }

        // 3. Fetch Benchmark Data (Portfolio vs SPY)
        try {
            const benchmarkRes = await authFetch(`${API_BASE}/portfolio/benchmark`);
            if (benchmarkRes.ok) {
                const benchData = await benchmarkRes.json();
                setBenchmarkData(benchData);
            }
        } catch (err) {
            console.error('Error fetching benchmark:', err);
        }

        // 4. Fetch Real-time Metrics (Slow, External API)
        try {
            const metricsRes = await authFetch(`${API_BASE}/trades/unified/metrics`);
            if (metricsRes.ok) {
                const data = await metricsRes.json();
                setMetrics(data);
            }
        } catch (err) {
            console.error('Error fetching metrics:', err);
        }

        setLoading(false);
    };

    // Take a manual snapshot (for testing)
    const takeSnapshot = async () => {
        try {
            const res = await fetch(`${API_BASE}/portfolio/snapshot/take`, { method: 'POST' });
            if (res.ok) {
                alert('Snapshot taken successfully!');
                fetchAllData();
            }
        } catch (err) {
            console.error('Error taking snapshot:', err);
        }
    };

    const totals = metrics?.total?.[displayCurrency] || { invested: 0, current: 0, pnl: 0 };
    const currencySymbol = displayCurrency === 'ars' ? 'ARS ' : 'US$';
    const rates = metrics?.rates || {};
    const roiPct = totals.invested > 0 ? ((totals.pnl / totals.invested) * 100).toFixed(2) : 0;

    // Prepare chart data - convert to ARS if needed
    const cclRate = rates?.ccl || 1;
    const chartMultiplier = displayCurrency === 'ars' ? cclRate : 1;

    // Filter data based on selected timeframe
    const filterDataByTimeframe = (data) => {
        if (!data || data.length === 0) return data;

        const now = new Date();
        let cutoffDate;

        switch (chartTimeframe) {
            case '1D':
                cutoffDate = new Date(now);
                cutoffDate.setDate(cutoffDate.getDate() - 1);
                break;
            case '1W':
                cutoffDate = new Date(now);
                cutoffDate.setDate(cutoffDate.getDate() - 7);
                break;
            case '1M':
                cutoffDate = new Date(now);
                cutoffDate.setMonth(cutoffDate.getMonth() - 1);
                break;
            case 'YTD':
                cutoffDate = new Date(now.getFullYear(), 0, 1); // Jan 1st of current year
                break;
            case '1Y':
                cutoffDate = new Date(now);
                cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
                break;
            case 'Max':
            default:
                return data; // Return all data
        }

        return data.filter(snap => {
            const snapDate = new Date(snap.date);
            return snapDate >= cutoffDate;
        });
    };

    const filteredHistory = filterDataByTimeframe(history);
    const chartData = filteredHistory.map(snap => ({
        date: snap.date,
        value: (snap.total_value_usd || 0) * chartMultiplier,
        pnl: (snap.total_pnl_usd || 0) * chartMultiplier
    }));

    // Calculate Y-axis domain based on selected metric
    const getYAxisDomain = () => {
        if (chartData.length === 0) return [0, 100];
        const dataKey = chartMetric; // 'value' or 'pnl'
        const values = chartData.map(d => d[dataKey]).filter(v => v !== null && v !== undefined && !isNaN(v));
        if (values.length === 0) return [0, 100];

        const min = Math.min(...values);
        const max = Math.max(...values);

        // Add 10% padding
        const padding = (max - min) * 0.1 || Math.abs(max) * 0.1 || 100;

        if (dataKey === 'pnl') {
            // For P&L, include 0 in the range
            return [Math.min(min - padding, 0), Math.max(max + padding, 0)];
        } else {
            // For value, start from slightly below min
            return [Math.max(0, min - padding), max + padding];
        }
    };
    const yAxisDomain = getYAxisDomain();

    // Geographic regions with colors
    const regionColors = {
        usa: { bg: 'bg-blue-500', text: 'text-blue-400', hex: '#3b82f6', name: '🇺🇸 USA' },
        brasil: { bg: 'bg-green-500', text: 'text-green-400', hex: '#22c55e', name: '🇧🇷 Brasil' },
        argentina: { bg: 'bg-cyan-500', text: 'text-cyan-400', hex: '#06b6d4', name: '🇦🇷 Argentina' },
        china: { bg: 'bg-red-500', text: 'text-red-400', hex: '#ef4444', name: '🇨🇳 China' },
        europa: { bg: 'bg-purple-500', text: 'text-purple-400', hex: '#a855f7', name: '🇪🇺 Europa' }
    };

    // Sector classification mapping
    const SECTOR_MAP = {
        // Technology
        'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'GOOG': 'Technology',
        'META': 'Technology', 'NVDA': 'Technology', 'AMD': 'Technology', 'INTC': 'Technology',
        'NFLX': 'Technology', 'AMZN': 'Technology', 'SHOP': 'Technology', 'DOCU': 'Technology',
        'ZM': 'Technology', 'SNAP': 'Technology', 'SPOT': 'Technology', 'RDDT': 'Technology',
        'IT': 'Technology', 'DXYZ': 'Technology', 'VSTS': 'Technology',
        // Automotive & EV
        'TSLA': 'EV & Auto', 'STLA': 'EV & Auto', 'NIO': 'EV & Auto', 'XPEV': 'EV & Auto', 'LI': 'EV & Auto',
        // Finance
        'JPM': 'Finance', 'GS': 'Finance', 'V': 'Finance', 'MA': 'Finance', 'PYPL': 'Finance',
        'SQ': 'Finance', 'COIN': 'Finance', 'KKR': 'Finance',
        // Healthcare & Biotech
        'PFE': 'Healthcare', 'JNJ': 'Healthcare', 'MRNA': 'Healthcare', 'ARCT': 'Healthcare',
        'VKTX': 'Healthcare', 'AGEN': 'Healthcare', 'INDP': 'Healthcare',
        // Energy
        'CVX': 'Energy', 'XOM': 'Energy', 'FCEL': 'Energy', 'CLSK': 'Energy', 'MARA': 'Energy',
        // Crypto-related
        'GBTC': 'Crypto ETF', 'ETHU': 'Crypto ETF', 'MSTU': 'Crypto ETF',
        // Consumer
        'KO': 'Consumer', 'PEP': 'Consumer', 'MCD': 'Consumer', 'NKE': 'Consumer', 'SBUX': 'Consumer',
        'DIS': 'Consumer', 'WMT': 'Consumer', 'HD': 'Consumer', 'CAKE': 'Consumer',
        // Telecom
        'T': 'Telecom', 'VZ': 'Telecom', 'VERI': 'Telecom',
        // Space & Defense
        'SPCE': 'Space', 'BA': 'Aerospace',
        // ETFs
        'SPY': 'ETF', 'QQQ': 'ETF', 'ARKK': 'ETF',
        // Other
        'UBER': 'Transport', 'ABNB': 'Travel', 'LAR': 'REIT', 'DOW': 'Materials',
        'SMC': 'Industrial', 'VOYG': 'Other', 'MIRA': 'Other', 'SNDK': 'Other',
        'QCLS': 'Other', 'BBBY': 'Other'
    };

    const sectorColors = {
        'Technology': '#3b82f6',
        'EV & Auto': '#ef4444',
        'Finance': '#22c55e',
        'Healthcare': '#06b6d4',
        'Energy': '#f59e0b',
        'Crypto ETF': '#f97316',
        'Consumer': '#8b5cf6',
        'Telecom': '#ec4899',
        'Space': '#14b8a6',
        'Aerospace': '#6366f1',
        'ETF': '#64748b',
        'Transport': '#84cc16',
        'Travel': '#0ea5e9',
        'REIT': '#a855f7',
        'Materials': '#78716c',
        'Industrial': '#737373',
        'Other': '#94a3b8'
    };

    // Prepare country pie data from distribution
    const countryPieData = Object.entries(distribution).map(([key, data]) => ({
        name: regionColors[key]?.name || key.toUpperCase(),
        value: data.value || 0,
        pct: data.pct || 0,
        fill: regionColors[key]?.hex || '#64748b'
    })).filter(d => d.value > 0);

    // Prepare sector pie data from metrics (if we have position details)
    const sectorPieData = (() => {
        const sectorTotals = {};
        // Use USA trades data if available in metrics
        if (metrics?.usa?.positions) {
            metrics.usa.positions.forEach(pos => {
                const sector = SECTOR_MAP[pos.ticker?.toUpperCase()] || 'Other';
                const value = (pos.entry_price || 0) * (pos.shares || 0);
                sectorTotals[sector] = (sectorTotals[sector] || 0) + value;
            });
        }
        // If no position data, calculate from distribution (rough estimate)
        if (Object.keys(sectorTotals).length === 0 && distribution.usa) {
            // Show a placeholder - we'd need the actual trades to classify
            sectorTotals['USA Trades'] = distribution.usa.value || 0;
        }
        return Object.entries(sectorTotals).map(([name, value]) => ({
            name,
            value: Math.round(value),
            fill: sectorColors[name] || '#64748b'
        })).filter(d => d.value > 0).sort((a, b) => b.value - a.value);
    })();

    // Calculate zero offset for gradient (for line chart that crosses zero)
    const pnlValues = chartData.map(d => d.pnl).filter(v => v !== undefined && v !== null);
    const pnlMin = Math.min(...pnlValues, 0);
    const pnlMax = Math.max(...pnlValues, 0);
    const pnlRange = pnlMax - pnlMin || 1;
    // Zero position as percentage from top (0 = top, 1 = bottom)
    const zeroOffset = pnlMax / pnlRange;

    return (
        <div className="p-4 container mx-auto max-w-[1600px]">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                    📈 Portfolio Dashboard
                </h2>
                <div className="flex gap-2">
                    <button onClick={takeSnapshot} className="text-xs bg-green-600/20 hover:bg-green-600/40 border border-green-700/50 px-3 py-1.5 rounded transition text-green-400">
                        📸 Snapshot
                    </button>
                    <button onClick={fetchAllData} className="text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 px-3 py-1.5 rounded transition text-slate-400">
                        ↻ Refresh
                    </button>
                </div>
            </div>

            {/* DEBUG ALERT: Show if data seems empty */}
            {metrics && metrics.usa && metrics.usa.invested_usd === 0 && (
                <div className="mb-6 p-4 bg-yellow-900/20 border border-yellow-700/50 rounded-lg">
                    <h3 className="text-yellow-400 font-bold flex items-center gap-2">⚠️ Debug Info: Zero Data Detected</h3>
                    <p className="text-slate-400 text-xs mb-2">Fetching DB status counts to diagnose...</p>
                    <DebugStatusChecker />
                </div>
            )}

            {/* Currency Selector */}
            <div className="flex items-center gap-4 mb-6">
                <span className="text-xs text-slate-500 uppercase">Ver en:</span>
                <div className="flex bg-[#1a1a1a] rounded-lg p-0.5 border border-[#2a2a2a]">
                    <button onClick={() => setDisplayCurrency('usd_ccl')} className={`px-4 py-2 rounded text-sm font-bold transition ${displayCurrency === 'usd_ccl' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}>💵 USD CCL</button>
                    <button onClick={() => setDisplayCurrency('ars')} className={`px-4 py-2 rounded text-sm font-bold transition ${displayCurrency === 'ars' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'}`}>🇦🇷 ARS</button>
                </div>
                <div className="ml-auto text-xs text-slate-500 font-mono">
                    Dólar CCL: ARS ${rates.ccl?.toLocaleString()}
                </div>
            </div>

            {/* Total Portfolio Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                <div className="bg-gradient-to-br from-blue-900/30 to-slate-900/50 rounded-xl p-4 border border-blue-700/30">
                    <p className="text-slate-400 text-xs uppercase mb-1">Total Invertido</p>
                    <p className="text-2xl font-bold text-blue-400">{currencySymbol}{totals.invested?.toLocaleString()}</p>
                    <p className="text-xs text-slate-500">{metrics?.total?.position_count || 0} posiciones</p>
                </div>
                <div className="bg-[#151515] rounded-xl p-4 border border-[#2a2a2a]">
                    <p className="text-slate-400 text-xs uppercase mb-1">Valor Actual</p>
                    <p className="text-2xl font-bold text-white">{currencySymbol}{totals.current?.toLocaleString()}</p>
                </div>
                <div className="bg-[#151515] rounded-xl p-4 border border-[#2a2a2a]">
                    <p className="text-slate-400 text-xs uppercase mb-1">P&L Total (Open + Closed)</p>
                    <p className={`text-2xl font-bold ${totals.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {totals.pnl >= 0 ? '+' : ''}{currencySymbol}{totals.pnl?.toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-500">Open + Realized</p>
                </div>
                <div className="bg-[#151515] rounded-xl p-4 border border-[#2a2a2a]">
                    <p className="text-slate-400 text-xs uppercase mb-1">ROI Total</p>
                    <p className={`text-2xl font-bold ${totals.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {roiPct}%
                    </p>
                </div>
            </div>

            {/* Portfolio Evolution Chart */}
            <div className="bg-[#0f0f0f] rounded-xl p-6 border border-[#1a1a1a] mb-8">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-lg font-bold text-white flex items-center gap-2">
                        📈 Portfolio Evolution
                    </h3>
                    <div className="flex gap-2">
                        {/* Metric Toggle */}
                        <div className="flex bg-[#1a1a1a] rounded-lg p-0.5 border border-[#2a2a2a]">
                            <button
                                onClick={() => setChartMetric('value')}
                                className={`px-3 py-1.5 rounded text-xs font-medium transition ${chartMetric === 'value' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
                            >
                                💰 VALUE
                            </button>
                            <button
                                onClick={() => setChartMetric('pnl')}
                                className={`px-3 py-1.5 rounded text-xs font-medium transition ${chartMetric === 'pnl' ? 'bg-green-600 text-white' : 'text-slate-400 hover:text-white'}`}
                            >
                                📊 P&L
                            </button>
                        </div>
                        {/* Chart Type Toggle */}
                        <div className="flex bg-[#1a1a1a] rounded-lg p-0.5 border border-[#2a2a2a]">
                            <button
                                onClick={() => setChartMode('line')}
                                className={`px-4 py-1.5 rounded text-sm font-medium transition ${chartMode === 'line' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
                            >
                                LINE
                            </button>
                            <button
                                onClick={() => setChartMode('bar')}
                                className={`px-4 py-1.5 rounded text-sm font-medium transition ${chartMode === 'bar' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`}
                            >
                                BAR
                            </button>
                        </div>
                    </div>
                </div>

                {/* Timeframe Toggle Row */}
                <div className="flex justify-center gap-1 mb-4">
                    {['1D', '1W', '1M', 'YTD', '1Y', 'Max'].map(tf => (
                        <button
                            key={tf}
                            onClick={() => setChartTimeframe(tf)}
                            className={`px-3 py-1 rounded text-xs font-medium transition ${chartTimeframe === tf
                                ? 'bg-blue-600 text-white'
                                : 'bg-[#1a1a1a] text-slate-400 hover:text-white border border-[#2a2a2a]'
                                }`}
                        >
                            {tf}
                        </button>
                    ))}
                </div>

                {chartData.length > 0 ? (
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            {chartMode === 'line' ? (
                                <AreaChart data={chartData}>
                                    <defs>
                                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                        </linearGradient>
                                        {/* Split gradient: green above zero, red below zero */}
                                        <linearGradient id="colorPnlSplit" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="0%" stopColor="#22c55e" stopOpacity={0.4} />
                                            <stop offset={`${(zeroOffset * 100).toFixed(1)}%`} stopColor="#22c55e" stopOpacity={0.1} />
                                            <stop offset={`${(zeroOffset * 100).toFixed(1)}%`} stopColor="#ef4444" stopOpacity={0.1} />
                                            <stop offset="100%" stopColor="#ef4444" stopOpacity={0.4} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                                    <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(d) => d.substring(5)} />
                                    <YAxis
                                        tick={{ fill: '#64748b', fontSize: 10 }}
                                        domain={yAxisDomain}
                                        allowDataOverflow={false}
                                        tickFormatter={(v) => {
                                            const sign = chartMetric === 'pnl' && v >= 0 ? '+' : '';
                                            const prefix = displayCurrency === 'ars' ? 'ARS ' : '$';
                                            // Dynamic formatting based on value magnitude
                                            if (displayCurrency === 'ars') {
                                                if (Math.abs(v) >= 1000000) {
                                                    return `${sign}${prefix}${(v / 1000000).toFixed(1)}M`;
                                                } else if (Math.abs(v) >= 1000) {
                                                    return `${sign}${prefix}${(v / 1000).toFixed(0)}k`;
                                                }
                                                return `${sign}${prefix}${v.toFixed(0)}`;
                                            } else {
                                                if (Math.abs(v) >= 1000000) {
                                                    return `${sign}${prefix}${(v / 1000000).toFixed(1)}M`;
                                                } else if (Math.abs(v) >= 1000) {
                                                    return `${sign}${prefix}${(v / 1000).toFixed(1)}k`;
                                                }
                                                return `${sign}${prefix}${v.toFixed(0)}`;
                                            }
                                        }}
                                    />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '8px', color: '#fff' }}
                                        itemStyle={{ color: '#fff' }}
                                        labelStyle={{ color: '#94a3b8' }}
                                        formatter={(value) => {
                                            const sign = value >= 0 ? '+' : '';
                                            const prefix = displayCurrency === 'ars' ? 'ARS ' : '$';
                                            return [`${chartMetric === 'pnl' ? sign : ''}${prefix}${Math.round(value).toLocaleString()}`, chartMetric === 'pnl' ? 'P&L' : 'Value'];
                                        }}
                                    />
                                    {/* Reference line at zero for P&L mode */}
                                    {chartMetric === 'pnl' && <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" strokeWidth={1} />}
                                    {chartMetric === 'value' ? (
                                        <Area type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} fill="url(#colorValue)" />
                                    ) : (
                                        <Area
                                            type="monotone"
                                            dataKey="pnl"
                                            stroke="#64748b"
                                            strokeWidth={2}
                                            fill="url(#colorPnlSplit)"
                                        />
                                    )}
                                </AreaChart>
                            ) : (
                                <BarChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                                    <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(d) => d.substring(5)} />
                                    <YAxis
                                        tick={{ fill: '#64748b', fontSize: 10 }}
                                        domain={yAxisDomain}
                                        allowDataOverflow={false}
                                        tickFormatter={(v) => {
                                            const sign = chartMetric === 'pnl' && v >= 0 ? '+' : '';
                                            const prefix = displayCurrency === 'ars' ? 'ARS ' : '$';
                                            // Dynamic formatting based on value magnitude
                                            if (displayCurrency === 'ars') {
                                                if (Math.abs(v) >= 1000000) {
                                                    return `${sign}${prefix}${(v / 1000000).toFixed(1)}M`;
                                                } else if (Math.abs(v) >= 1000) {
                                                    return `${sign}${prefix}${(v / 1000).toFixed(0)}k`;
                                                }
                                                return `${sign}${prefix}${v.toFixed(0)}`;
                                            } else {
                                                if (Math.abs(v) >= 1000000) {
                                                    return `${sign}${prefix}${(v / 1000000).toFixed(1)}M`;
                                                } else if (Math.abs(v) >= 1000) {
                                                    return `${sign}${prefix}${(v / 1000).toFixed(1)}k`;
                                                }
                                                return `${sign}${prefix}${v.toFixed(0)}`;
                                            }
                                        }}
                                    />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '8px', color: '#fff' }}
                                        labelStyle={{ color: '#fff' }}
                                        itemStyle={{ color: '#fff' }}
                                        formatter={(value) => {
                                            const sign = value >= 0 ? '+' : '';
                                            const prefix = displayCurrency === 'ars' ? 'ARS ' : '$';
                                            return [`${chartMetric === 'pnl' ? sign : ''}${prefix}${Math.round(value).toLocaleString()}`, chartMetric === 'pnl' ? 'P&L' : 'Value'];
                                        }}
                                    />
                                    {/* Reference line at zero for P&L mode */}
                                    {chartMetric === 'pnl' && <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />}
                                    <Bar dataKey={chartMetric} radius={[4, 4, 0, 0]}>
                                        {/* Color each bar based on positive/negative value */}
                                        {chartData.map((entry, index) => (
                                            <Cell
                                                key={`cell-${index}`}
                                                fill={chartMetric === 'pnl'
                                                    ? (entry.pnl >= 0 ? '#22c55e' : '#ef4444')
                                                    : '#3b82f6'
                                                }
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            )}
                        </ResponsiveContainer>
                    </div>
                ) : (
                    <div className="h-64 flex items-center justify-center text-slate-500">
                        <div className="text-center">
                            <p className="text-4xl mb-2">📊</p>
                            <p>No hay datos históricos todavía.</p>
                            <p className="text-xs mt-1">Se toma un snapshot automático a las 19:00 ARG cada día.</p>
                            <button onClick={takeSnapshot} className="mt-3 text-xs bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded text-white">
                                Tomar Snapshot Ahora
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Market Breakdown + Pie Charts Side by Side */}
            <div className="grid lg:grid-cols-2 gap-6 mb-8">
                {/* Left Column: Market Breakdown */}
                <div>
                    <h3 className="text-lg font-bold text-white mb-4">📊 Breakdown por Mercado</h3>
                    <div className="grid gap-4">
                        {/* USA */}
                        <div className="bg-[#0f0f0f] rounded-xl p-4 border border-blue-700/30">
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-xl">🇺🇸</span>
                                <h4 className="font-bold text-white">USA</h4>
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Invested</span>
                                    <span className="text-blue-400">
                                        {displayCurrency === 'usd_ccl'
                                            ? `$${metrics?.usa?.invested_usd?.toLocaleString() || 0}`
                                            : `ARS ${Math.round((metrics?.usa?.invested_usd || 0) * (rates?.ccl || 0)).toLocaleString()}`
                                        }
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">P&L Total</span>
                                    <span className={(metrics?.usa?.pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                                        {displayCurrency === 'usd_ccl'
                                            ? `$${metrics?.usa?.pnl_usd?.toLocaleString() || 0}`
                                            : `ARS ${Math.round((metrics?.usa?.pnl_usd || 0) * (rates?.ccl || 0)).toLocaleString()}`
                                        }
                                    </span>
                                </div>
                                <div className="flex justify-between"><span className="text-slate-400">Posiciones</span><span className="text-white">{metrics?.usa?.position_count || 0}</span></div>
                            </div>
                        </div>
                        {/* Argentina */}
                        <div className="bg-[#0f0f0f] rounded-xl p-4 border border-cyan-700/30">
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-xl">🇦🇷</span>
                                <h4 className="font-bold text-white">Argentina</h4>
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Invested</span>
                                    <span className="text-cyan-400">
                                        {displayCurrency === 'usd_ccl'
                                            ? `$${metrics?.argentina?.invested_usd_ccl?.toLocaleString() || 0}`
                                            : `ARS ${metrics?.argentina?.invested_ars?.toLocaleString() || 0}`
                                        }
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">P&L</span>
                                    <span className={(metrics?.argentina?.pnl_ars || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                                        {displayCurrency === 'usd_ccl'
                                            ? `$${metrics?.argentina?.pnl_usd_ccl?.toLocaleString() || 0}`
                                            : `ARS ${metrics?.argentina?.pnl_ars?.toLocaleString() || 0}`
                                        }
                                    </span>
                                </div>
                                <div className="flex justify-between"><span className="text-slate-400">Posiciones</span><span className="text-white">{metrics?.argentina?.position_count || 0}</span></div>
                            </div>
                        </div>
                        {/* Crypto */}
                        <div className="bg-[#0f0f0f] rounded-xl p-4 border border-orange-700/30">
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-xl">₿</span>
                                <h4 className="font-bold text-white">Crypto</h4>
                                {metrics?.crypto?.has_api && <span className="text-xs bg-green-900/40 text-green-400 px-2 py-0.5 rounded-full border border-green-800">Connected</span>}
                            </div>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-slate-400">Invested</span>
                                    <span className="text-orange-400">
                                        {displayCurrency === 'usd_ccl'
                                            ? `$${metrics?.crypto?.invested_usd?.toLocaleString() || 0}`
                                            : `ARS ${((metrics?.crypto?.invested_usd || 0) * (rates?.ccl || 0)).toLocaleString().split('.')[0]}`
                                        }
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-slate-400">P&L</span>
                                    <span className={(metrics?.crypto?.pnl_usd || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                                        {displayCurrency === 'usd_ccl'
                                            ? `$${metrics?.crypto?.pnl_usd?.toLocaleString() || 0}`
                                            : `ARS ${((metrics?.crypto?.pnl_usd || 0) * (rates?.ccl || 0)).toLocaleString().split('.')[0]}`
                                        }
                                    </span>
                                </div>
                                <div className="flex justify-between"><span className="text-slate-400">Posiciones</span><span className="text-white">{metrics?.crypto?.position_count || 0}</span></div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column: Stacked Pie Charts */}
                <div className="space-y-6">
                    {/* Country Distribution */}
                    <div>
                        <h3 className="text-lg font-bold text-white mb-2">🌍 Por País</h3>
                        <div className="bg-[#0f0f0f] rounded-xl p-3 border border-[#1a1a1a]">
                            {countryPieData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={160}>
                                    <PieChart>
                                        <Pie
                                            data={countryPieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={40}
                                            outerRadius={65}
                                            dataKey="value"
                                            labelLine={false}
                                            label={({ name, pct }) => `${name} ${pct.toFixed(0)}%`}
                                        >
                                            {countryPieData.map((entry, index) => (
                                                <Cell key={`country-${index}`} fill={entry.fill} />
                                            ))}
                                        </Pie>
                                        <Tooltip
                                            formatter={(value) => {
                                                const prefix = displayCurrency === 'ars' ? 'ARS ' : '$';
                                                const displayValue = displayCurrency === 'ars' ? Math.round(value * cclRate) : value;
                                                return [`${prefix}${displayValue.toLocaleString()}`, 'Valor'];
                                            }}
                                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '8px', color: '#fff' }}
                                            itemStyle={{ color: '#fff' }}
                                            labelStyle={{ color: '#94a3b8' }}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[160px] flex items-center justify-center text-slate-500 text-sm">Sin datos</div>
                            )}
                            <div className="flex flex-wrap gap-2 justify-center text-xs">
                                {countryPieData.map((entry, index) => (
                                    <div key={`legend-country-${index}`} className="flex items-center gap-1">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.fill }}></div>
                                        <span className="text-slate-400">{entry.name} ({entry.pct.toFixed(0)}%)</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Sector Distribution */}
                    <div>
                        <h3 className="text-lg font-bold text-white mb-2">💼 Por Sector</h3>
                        <div className="bg-[#0f0f0f] rounded-xl p-3 border border-[#1a1a1a]">
                            {sectorPieData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={160}>
                                    <PieChart>
                                        <Pie
                                            data={sectorPieData}
                                            cx="50%"
                                            cy="50%"
                                            innerRadius={40}
                                            outerRadius={65}
                                            dataKey="value"
                                            labelLine={false}
                                            label={({ name }) => name}
                                        >
                                            {sectorPieData.map((entry, index) => (
                                                <Cell key={`sector-${index}`} fill={entry.fill} />
                                            ))}
                                        </Pie>
                                        <Tooltip
                                            formatter={(value) => {
                                                const prefix = displayCurrency === 'ars' ? 'ARS ' : '$';
                                                const displayValue = displayCurrency === 'ars' ? Math.round(value * cclRate) : value;
                                                return [`${prefix}${displayValue.toLocaleString()}`, 'Valor'];
                                            }}
                                            contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '8px', color: '#fff' }}
                                            itemStyle={{ color: '#fff' }}
                                            labelStyle={{ color: '#94a3b8' }}
                                        />
                                    </PieChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-[160px] flex items-center justify-center text-slate-500 text-sm">Cargando...</div>
                            )}
                            <div className="flex flex-wrap gap-2 justify-center text-xs">
                                {sectorPieData.slice(0, 6).map((entry, index) => (
                                    <div key={`legend-sector-${index}`} className="flex items-center gap-1">
                                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.fill }}></div>
                                        <span className="text-slate-400">{entry.name}</span>
                                    </div>
                                ))}
                                {sectorPieData.length > 6 && <span className="text-slate-500 text-xs">+{sectorPieData.length - 6}</span>}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Performance vs Benchmark (P&L% vs SPY) */}
            {benchmarkData && benchmarkData.dates && benchmarkData.dates.length > 0 && (
                <div className="mb-8">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-bold text-white">📈 Performance vs S&P 500 (90 días)</h3>
                        <div className="flex items-center gap-4 text-sm">
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-0.5 bg-blue-500 rounded"></span>
                                <span className="text-slate-400">Portfolio</span>
                                <span className={benchmarkData.latest_portfolio_pct >= 0 ? 'text-green-400' : 'text-red-400'}>
                                    {benchmarkData.latest_portfolio_pct >= 0 ? '+' : ''}{benchmarkData.latest_portfolio_pct?.toFixed(2)}%
                                </span>
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="w-3 h-0.5 bg-pink-500 rounded"></span>
                                <span className="text-slate-400">S&P 500</span>
                                <span className={benchmarkData.latest_spy_pct >= 0 ? 'text-green-400' : 'text-red-400'}>
                                    {benchmarkData.latest_spy_pct >= 0 ? '+' : ''}{benchmarkData.latest_spy_pct?.toFixed(2)}%
                                </span>
                            </span>
                        </div>
                    </div>
                    <div className="bg-[#0f0f0f] rounded-xl p-4 border border-[#1a1a1a]">
                        <ResponsiveContainer width="100%" height={200}>
                            <AreaChart data={benchmarkData.dates.map((date, i) => ({
                                date,
                                portfolio: benchmarkData.portfolio_pct[i] || 0,
                                spy: benchmarkData.spy_pct[i] || 0
                            }))}>
                                <defs>
                                    <linearGradient id="colorPortfolio" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
                                <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(d) => d.substring(5)} />
                                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: '8px', color: '#fff' }}
                                    itemStyle={{ color: '#fff' }}
                                    labelStyle={{ color: '#94a3b8' }}
                                    formatter={(value, name) => [`${value >= 0 ? '+' : ''}${value.toFixed(2)}%`, name === 'portfolio' ? 'Portfolio' : 'S&P 500']}
                                    labelFormatter={(label) => `Fecha: ${label}`}
                                />
                                <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
                                <Area type="monotone" dataKey="portfolio" stroke="#3b82f6" strokeWidth={2} fill="url(#colorPortfolio)" />
                                <Area type="monotone" dataKey="spy" stroke="#ec4899" strokeWidth={2} fill="none" strokeDasharray="5 5" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            )}

            {/* Quick Comparison Table */}
            <h3 className="text-lg font-bold text-white mb-4">💱 Total Portfolio (USD CCL vs ARS)</h3>
            <div className="bg-[#0f0f0f] rounded-xl overflow-hidden border border-[#1a1a1a]">
                <table className="w-full text-sm">
                    <thead className="bg-[#0a0a0a] text-slate-400 uppercase text-xs">
                        <tr>
                            <th className="p-3 text-left">Concepto</th>
                            <th className="p-3 text-right text-green-400">💵 USD CCL</th>
                            <th className="p-3 text-right text-sky-400">🇦🇷 ARS</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="border-t border-[#1a1a1a]">
                            <td className="p-3 text-slate-300 font-medium">Total Invertido</td>
                            <td className="p-3 text-right text-green-400 font-bold text-lg">${metrics?.total?.usd_ccl?.invested?.toLocaleString() || 0}</td>
                            <td className="p-3 text-right text-sky-400 font-bold text-lg">${metrics?.total?.ars?.invested?.toLocaleString() || 0}</td>
                        </tr>
                        <tr className="border-t border-[#1a1a1a] bg-[#0a0a0a]/50">
                            <td className="p-3 text-slate-300 font-medium">Valor Actual</td>
                            <td className="p-3 text-right text-green-400">${metrics?.total?.usd_ccl?.current?.toLocaleString() || 0}</td>
                            <td className="p-3 text-right text-sky-400">${metrics?.total?.ars?.current?.toLocaleString() || 0}</td>
                        </tr>
                        <tr className="border-t border-[#1a1a1a]">
                            <td className="p-3 text-slate-300 font-medium">Total P&L (Open + Closed)</td>
                            <td className={`p-3 text-right font-bold ${(metrics?.total?.usd_ccl?.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>${metrics?.total?.usd_ccl?.pnl?.toLocaleString() || 0}</td>
                            <td className={`p-3 text-right font-bold ${(metrics?.total?.ars?.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>${metrics?.total?.ars?.pnl?.toLocaleString() || 0}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    );
}






// Watchlist Panel Component
function WatchlistPanel() {
    const [watchlist, setWatchlist] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAddForm, setShowAddForm] = useState(false);
    const [formData, setFormData] = useState({
        ticker: '',
        entry_price: '',
        alert_price: '',
        stop_alert: '',
        strategy: '',
        notes: ''
    });

    const loadWatchlist = async () => {
        try {
            const response = await authFetch('/api/watchlist');
            const data = await response.json();
            setWatchlist(Array.isArray(data) ? data : []);
        } catch (error) {
            console.error('Error loading watchlist:', error);
            setWatchlist([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadWatchlist();
        // Refresh prices every 30 seconds
        const interval = setInterval(loadWatchlist, 30000);
        return () => clearInterval(interval);
    }, []);

    const handleAdd = async (e) => {
        e.preventDefault();
        try {
            const response = await fetch('/api/watchlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...formData,
                    entry_price: formData.entry_price ? parseFloat(formData.entry_price) : null,
                    alert_price: formData.alert_price ? parseFloat(formData.alert_price) : null,
                    stop_alert: formData.stop_alert ? parseFloat(formData.stop_alert) : null
                })
            });
            if (response.ok) {
                setFormData({ ticker: '', entry_price: '', alert_price: '', stop_alert: '', strategy: '', notes: '' });
                setShowAddForm(false);
                loadWatchlist();
            }
        } catch (error) {
            console.error('Error adding to watchlist:', error);
        }
    };

    const handleUpdate = async (ticker, field, value) => {
        try {
            const item = watchlist.find(i => i.ticker === ticker);
            if (!item) return;

            const updatedItem = {
                ...item,
                [field]: field === 'strategy' || field === 'notes' ? value : parseFloat(value)
            };

            const response = await fetch(`/api/watchlist/${ticker}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedItem)
            });

            if (response.ok) {
                loadWatchlist();
            }
        } catch (error) {
            console.error('Error updating watchlist item:', error);
        }
    };

    const handleDelete = async (ticker) => {
        if (!confirm(`Remove ${ticker} from watchlist?`)) return;
        try {
            await fetch(`/api/watchlist/${ticker}`, { method: 'DELETE' });
            loadWatchlist();
        } catch (error) {
            console.error('Error removing from watchlist:', error);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="text-white">Loading watchlist...</div>
            </div>
        );
    }

    return (
        <div className="p-8">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-white">Watchlist & Alerts</h2>
                <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition"
                >
                    {showAddForm ? 'Cancel' : '+ Add Symbol'}
                </button>
            </div>

            {showAddForm && (
                <form onSubmit={handleAdd} className="bg-slate-800 p-6 rounded-xl mb-6 border border-slate-700">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                        <input
                            type="text"
                            placeholder="Ticker"
                            required
                            value={formData.ticker}
                            onChange={(e) => setFormData({ ...formData, ticker: e.target.value.toUpperCase() })}
                            className="bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none"
                        />
                        <input
                            type="number"
                            step="0.01"
                            placeholder="Added Price (optional)"
                            value={formData.entry_price}
                            onChange={(e) => setFormData({ ...formData, entry_price: e.target.value })}
                            className="bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none"
                        />
                        <input
                            type="number"
                            step="0.01"
                            placeholder="Buy Alert Price"
                            value={formData.alert_price}
                            onChange={(e) => setFormData({ ...formData, alert_price: e.target.value })}
                            className="bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none"
                        />
                        <input
                            type="number"
                            step="0.01"
                            placeholder="SL (Watchlist)"
                            value={formData.stop_alert}
                            onChange={(e) => setFormData({ ...formData, stop_alert: e.target.value })}
                            className="bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none"
                        />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <input
                            type="text"
                            placeholder="Strategy (e.g. Weekly RSI)"
                            value={formData.strategy}
                            onChange={(e) => setFormData({ ...formData, strategy: e.target.value })}
                            className="bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none"
                        />
                        <input
                            type="text"
                            placeholder="Notes (optional)"
                            value={formData.notes}
                            onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                            className="bg-slate-900 text-white px-4 py-2 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none"
                        />
                    </div>
                    <button type="submit" className="mt-4 bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg font-medium transition">
                        Add to Watchlist
                    </button>
                </form>
            )}

            <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-slate-900">
                            <tr>
                                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Ticker</th>
                                <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">Fecha</th>
                                <th className="px-6 py-4 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">Agregado</th>
                                <th className="px-6 py-4 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">Actual</th>
                                <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">SL (Watchlist)</th>
                                <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">Alerta Buy</th>
                                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Estrategia</th>
                                <th className="px-6 py-4 text-center text-xs font-semibold text-slate-400 uppercase tracking-wider">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700">
                            {watchlist.length === 0 ? (
                                <tr>
                                    <td colSpan="8" className="px-6 py-8 text-center text-slate-500">
                                        No symbols in watchlist. Click "+ Add Symbol" to get started.
                                    </td>
                                </tr>
                            ) : (
                                watchlist.map((item) => (
                                    <tr key={item.ticker} className={`hover:bg-slate-700/50 transition ${item.is_triggered ? 'opacity-40 grayscale-[0.5]' : ''}`}>
                                        <td className="px-6 py-4">
                                            <div className="flex flex-col">
                                                <span className={`text-white font-bold ${item.is_triggered ? 'line-through' : ''}`}>{item.ticker}</span>
                                                <span className={`text-[10px] font-bold ${(item.change_pct || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                                    {(item.change_pct || 0) >= 0 ? '+' : ''}{(item.change_pct || 0).toFixed(2)}%
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-center text-slate-400 text-sm">
                                            {item.added_date ? new Date(item.added_date).toLocaleDateString() : '-'}
                                        </td>
                                        <td className="px-6 py-4 text-right font-mono text-slate-400">
                                            ${(item.entry_price || 0).toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 text-right font-mono text-white font-bold">
                                            ${(item.current_price || 0).toFixed(2)}
                                        </td>
                                        <td className="px-6 py-4 text-center font-mono">
                                            <EditableCell
                                                value={item.stop_alert || 0}
                                                onSave={(val) => handleUpdate(item.ticker, 'stop_alert', val)}
                                                prefix="$"
                                                type="number"
                                                className="text-rose-500 font-bold"
                                            />
                                        </td>
                                        <td className="px-6 py-4 text-center font-mono">
                                            <EditableCell
                                                value={item.alert_price || 0}
                                                onSave={(val) => handleUpdate(item.ticker, 'alert_price', val)}
                                                prefix="$"
                                                type="number"
                                                className="text-amber-500 font-bold"
                                            />
                                        </td>
                                        <td className="px-6 py-4">
                                            <EditableCell
                                                value={item.strategy || 'N/A'}
                                                onSave={(val) => handleUpdate(item.ticker, 'strategy', val)}
                                                width="w-32"
                                                className="text-slate-300 italic text-sm"
                                            />
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <button
                                                onClick={() => handleDelete(item.ticker)}
                                                className="text-red-500 hover:text-red-400 transition"
                                                title="Remove from watchlist"
                                            >
                                                🗑️
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* News for Watchlist Tickers */}
            {watchlist.length > 0 && (
                <div className="mt-6">
                    <PortfolioNewsWidget tickers={watchlist.map(w => w.ticker)} />
                </div>
            )}
        </div>
    );
}

// TradingView Embedded Widget Component
function TradingViewWidget({ ticker }) {
    const containerRef = useRef(null);

    useEffect(() => {
        if (!containerRef.current) return;

        // Clear previous widget
        containerRef.current.innerHTML = '';

        // Create TradingView widget script
        const script = document.createElement('script');
        script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
        script.type = 'text/javascript';
        script.async = true;
        script.innerHTML = JSON.stringify({
            "autosize": true,
            "symbol": ticker,
            "interval": "D",
            "timezone": "America/New_York",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "hide_top_toolbar": false,
            "hide_legend": false,
            "save_image": true,
            "calendar": false,
            "hide_volume": false,
            "support_host": "https://www.tradingview.com",
            "studies": [
                "MAExp@tv-basicstudies",
                "RSI@tv-basicstudies"
            ]
        });

        containerRef.current.appendChild(script);
    }, [ticker]);

    return (
        <div className="tradingview-widget-container h-full" ref={containerRef}>
            <div className="tradingview-widget-container__widget h-full"></div>
        </div>
    );
}

// Charts Panel Component
function ChartsPanel() {
    const [selectedTicker, setSelectedTicker] = useState('NVDA');
    const [searchQuery, setSearchQuery] = useState('');
    const [analysisData, setAnalysisData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [chartMode, setChartMode] = useState('custom'); // 'custom' or 'tradingview'
    const [fetchError, setFetchError] = useState(null);
    const abortControllerRef = useRef(null);

    const handleSearch = async (ticker) => {
        if (!ticker) return;

        // Abort any previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        setLoading(true);
        setFetchError(null);
        setSelectedTicker(ticker.toUpperCase());

        // Only fetch if in custom mode
        if (chartMode === 'tradingview') {
            setLoading(false);
            return;
        }

        // Create new AbortController with 12s timeout
        abortControllerRef.current = new AbortController();
        const timeoutId = setTimeout(() => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        }, 12000);

        try {
            const response = await fetch(`/api/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: ticker.toUpperCase() }),
                signal: abortControllerRef.current.signal
            });
            clearTimeout(timeoutId);
            const data = await response.json();
            console.log('Charts API Response:', data);
            setAnalysisData(data);
            setFetchError(null);
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                console.warn('Chart fetch timed out, falling back to TradingView');
                setFetchError('timeout');
                // Auto-switch to TradingView on timeout
                setChartMode('tradingview');
            } else {
                console.error('Error fetching chart data:', error);
                setFetchError('error');
            }
            setAnalysisData(null);
        } finally {
            setLoading(false);
        }
    };

    // Re-fetch when mode changes to custom
    useEffect(() => {
        if (chartMode === 'custom' && selectedTicker) {
            handleSearch(selectedTicker);
        }
    }, [chartMode]);

    useEffect(() => {
        handleSearch(selectedTicker);
    }, []);

    return (
        <div className="p-8">
            <div className="mb-6">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-2xl font-bold text-white">Advanced Charts</h2>

                    {/* Chart Mode Toggle */}
                    <div className="flex items-center gap-2 bg-slate-800 p-1 rounded-lg border border-slate-700">
                        <button
                            onClick={() => setChartMode('custom')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition ${chartMode === 'custom' ? 'bg-indigo-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}
                        >
                            📊 Custom
                        </button>
                        <button
                            onClick={() => setChartMode('tradingview')}
                            className={`px-4 py-2 rounded-md text-sm font-medium transition ${chartMode === 'tradingview' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-white'}`}
                        >
                            📈 TradingView
                        </button>
                    </div>
                </div>

                <div className="flex gap-4">
                    <div className="flex-1 relative">
                        <input
                            type="text"
                            placeholder="Search ticker (e.g. AAPL, TSLA, NVDA)..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value.toUpperCase())}
                            onKeyPress={(e) => {
                                if (e.key === 'Enter' && searchQuery) {
                                    handleSearch(searchQuery);
                                }
                            }}
                            className="w-full bg-slate-800 text-white px-4 py-3 rounded-lg border border-slate-700 focus:border-indigo-500 outline-none pl-12"
                        />
                        <span className="absolute left-4 top-3.5 text-slate-500 text-xl">🔍</span>
                    </div>
                    <button
                        onClick={() => handleSearch(searchQuery)}
                        disabled={!searchQuery}
                        className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-lg font-medium transition"
                    >
                        Search
                    </button>
                </div>

                {/* Timeout Warning Banner */}
                {fetchError === 'timeout' && (
                    <div className="mt-4 p-3 bg-amber-500/20 border border-amber-500/50 rounded-lg flex items-center justify-between">
                        <span className="text-amber-400 text-sm">⚠️ Data provider slow. Switched to TradingView mode.</span>
                        <button
                            onClick={() => { setChartMode('custom'); setFetchError(null); }}
                            className="text-xs bg-amber-600 hover:bg-amber-700 text-white px-3 py-1 rounded"
                        >
                            Retry Custom
                        </button>
                    </div>
                )}
            </div>


            {/* TradingView Mode */}
            {chartMode === 'tradingview' ? (
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-0 h-[600px] overflow-hidden">
                    <TradingViewWidget ticker={selectedTicker} />
                </div>
            ) : loading ? (
                <div className="flex flex-col items-center justify-center h-96 bg-slate-800 rounded-xl border border-slate-700">
                    <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full mb-4"></div>
                    <div className="text-white">Loading chart for {selectedTicker}...</div>
                    <div className="text-slate-500 text-xs mt-2">Timeout in 12s → auto-switch to TradingView</div>
                </div>
            ) : analysisData && analysisData.chart_data && analysisData.chart_data.length > 0 ? (
                <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 h-[600px]">
                    <TradingViewChart
                        ticker={selectedTicker}
                        chartData={analysisData.chart_data}
                        metrics={analysisData.metrics || {}}
                        tradeHistory={[]}
                        elliottWave={analysisData.elliott_wave || null}
                    />
                </div>
            ) : (
                <div className="flex items-center justify-center h-96 bg-slate-800 rounded-xl border border-slate-700">
                    <div className="text-slate-500">
                        {analysisData ? 'No data available for this ticker' : 'Enter a ticker and press Search to view charts'}
                    </div>
                </div>
            )}
        </div>
    );
}

// --- Chatbot Copilot Component ---
function ChatCopilot() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([
        { role: 'assistant', content: "Hello! I'm your Portfolio Copilot. Ask me anything about your positions, risk, or market trends. 📈" }
    ]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        if (isOpen) {
            scrollToBottom();
            inputRef.current?.focus();
        }
    }, [isOpen, messages]);

    const handleSend = async (text = null) => {
        const query = text || inputValue.trim();
        if (!query) return;

        // Add user message
        const newMessages = [...messages, { role: 'user', content: query }];
        setMessages(newMessages);
        setInputValue('');
        setIsLoading(true);

        try {
            // Prepare history for API (exclude first welcome message if needed, or keep it)
            const history = newMessages.length > 0 ? newMessages.map(m => ({ role: m.role, content: m.content })) : [];

            const res = await fetch(`${API_BASE}/chat/query`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, history })
            });

            if (res.ok) {
                const data = await res.json();
                setMessages([...newMessages, { role: 'assistant', content: data.response }]);
            } else {
                setMessages([...newMessages, { role: 'assistant', content: "⚠️ Sorry, I couldn't process your request. Please try again." }]);
            }
        } catch (err) {
            console.error(err);
            setMessages([...newMessages, { role: 'assistant', content: "❌ Network error. Please check your connection." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const suggestions = [
        "How is my portfolio doing today?",
        "What is my biggest risk right now?",
        "Should I take profit on any winners?",
        "Summarize my sector exposure"
    ];

    return (
        <div className="fixed bottom-6 right-6 z-[100] flex flex-col items-end pointer-events-none">
            {/* Chat Window */}
            {isOpen && (
                <div className="bg-[#1e293b] w-[350px] h-[500px] rounded-2xl shadow-2xl border border-slate-700 flex flex-col overflow-hidden mb-4 pointer-events-auto animate-fade-in-up">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-purple-900 to-blue-900 p-4 flex justify-between items-center border-b border-white/10">
                        <div className="flex items-center gap-2">
                            <span className="text-xl">🤖</span>
                            <div>
                                <h3 className="font-bold text-white text-sm">Portfolio Copilot</h3>
                                <p className="text-[10px] text-blue-200">Powered by Gemini 2.0</p>
                            </div>
                        </div>
                        <button onClick={() => setIsOpen(false)} className="text-white/70 hover:text-white transition">✕</button>
                    </div>

                    {/* Messages Area */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0f172a]">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-xs sm:text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                                    ? 'bg-blue-600 text-white rounded-br-none'
                                    : 'bg-[#334155] text-slate-200 rounded-bl-none border border-slate-600'
                                    }`}>
                                    {msg.role === 'assistant' ? (
                                        <div className="markdown-body" dangerouslySetInnerHTML={{
                                            __html: msg.content.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br/>')
                                        }} />
                                    ) : (
                                        msg.content
                                    )}
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-[#334155] rounded-2xl rounded-bl-none px-4 py-3 border border-slate-600 flex gap-1.5 items-center">
                                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                    <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Suggestions (only if history is short) */}
                    {messages.length < 3 && (
                        <div className="px-4 pb-2 bg-[#0f172a] flex flex-wrap gap-2">
                            {suggestions.map((s, i) => (
                                <button
                                    key={i}
                                    onClick={() => handleSend(s)}
                                    className="text-[10px] bg-slate-800 text-slate-300 border border-slate-700 px-2 py-1 rounded-full hover:bg-slate-700 hover:text-white transition"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    )}

                    {/* Input Area */}
                    <div className="p-3 bg-[#1e293b] border-t border-slate-700">
                        <div className="flex gap-2">
                            <input
                                ref={inputRef}
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask about your portfolio..."
                                className="flex-1 bg-slate-900 text-white text-xs sm:text-sm rounded-lg px-3 py-2 border border-slate-700 focus:outline-none focus:border-blue-500 transition placeholder-slate-500"
                                disabled={isLoading}
                            />
                            <button
                                onClick={() => handleSend()}
                                disabled={isLoading || !inputValue.trim()}
                                className="bg-blue-600 hover:bg-blue-500 text-white rounded-lg px-3 py-2 transition disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                ➤
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Toggle Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-full shadow-lg transition-transform hover:scale-110 pointer-events-auto flex items-center justify-center relative group"
            >
                {isOpen ? <span className="text-xl font-bold">✕</span> : <span className="text-2xl">💬</span>}

                {/* Tooltip */}
                {!isOpen && (
                    <span className="absolute right-full mr-4 px-3 py-1.5 bg-blue-600 text-white text-xs font-bold rounded-xl opacity-0 group-hover:opacity-100 transition whitespace-nowrap shadow-xl">
                        AI Copilot
                    </span>
                )}
            </button>
        </div>
    );
}




// --- Component declarations are above ---


// -----------------------------------------------------------------------------
// MAIN APP COMPONENT
// -----------------------------------------------------------------------------

function App() {
    const [token, setToken] = useState(localStorage.getItem('token'));
    const [showRegister, setShowRegister] = useState(false);

    const [view, setView] = useState('dashboard');
    // Track visited views for lazy mounting (component only mounts on first visit, then stays mounted)
    const [visitedViews, setVisitedViews] = useState(new Set(['dashboard']));
    const [selectedTicker, setSelectedTicker] = useState(null);
    const [overrideMetrics, setOverrideMetrics] = useState(null);
    const [showConnectModal, setShowConnectModal] = useState(false);
    const [deferredPrompt, setDeferredPrompt] = useState(null);

    // Update visitedViews when view changes
    React.useEffect(() => {
        if (!visitedViews.has(view)) {
            setVisitedViews(prev => new Set([...prev, view]));
        }
    }, [view]);

    // Initial Load & Auth Setup
    useEffect(() => {
        if (token) {
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        } else {
            delete axios.defaults.headers.common['Authorization'];
        }

        const handleBeforeInstallPrompt = (e) => {
            e.preventDefault();
            setDeferredPrompt(e);
        };
        window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

        // Check URL params for direct chart opening (from new tab)
        const params = new URLSearchParams(window.location.search);
        const tickerParam = params.get('ticker');
        const viewParam = params.get('view');
        if (tickerParam) {
            setSelectedTicker(tickerParam);
            if (viewParam) {
                setView(viewParam);
            }
            // Clear URL params after parsing to keep URL clean
            window.history.replaceState({}, '', window.location.pathname);
        }

        return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    }, [token]);

    // Apply saved theme ONCE on initial page load
    useEffect(() => {
        const savedTheme = localStorage.getItem('theme') || 'dark';
        console.log('[Theme] Applying saved theme:', savedTheme);
        document.body.classList.remove('theme-dark', 'theme-light', 'theme-cyber');
        document.body.classList.add(`theme-${savedTheme}`);
        if (savedTheme === 'light') {
            document.body.style.backgroundColor = '#f5f5f5';
            document.body.style.color = '#1a1a1a';
        } else if (savedTheme === 'cyber') {
            document.body.style.backgroundColor = '#0d0221';
            document.body.style.color = '#00ff88';
        } else {
            document.body.style.backgroundColor = '#0a0a0a';
            document.body.style.color = '#ffffff';
        }
    }, []);

    const handleLoginSuccess = (newToken) => {
        localStorage.setItem('token', newToken);
        setToken(newToken);
        setView('dashboard');
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        setToken(null);
    };

    const handleInstallClick = () => {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
            setDeferredPrompt(null);
        });
    };

    const handleTickerClick = (ticker, metrics = null) => {
        // Open chart in new browser tab
        const url = `${window.location.origin}?ticker=${encodeURIComponent(ticker)}&view=charts`;
        window.open(url, '_blank');
    };

    const handleCloseDetail = () => {
        setSelectedTicker(null);
        setOverrideMetrics(null);
    };

    // --- AUTH GUARD ---
    if (!token) {
        return showRegister
            ? <Register onRegisterSuccess={() => setShowRegister(false)} onSwitch={() => setShowRegister(false)} />
            : <Login onLoginSuccess={handleLoginSuccess} onSwitch={() => setShowRegister(true)} />;
    }

    return (
        <div className="flex h-screen overflow-hidden selection:bg-blue-500/30 selection:text-white">
            {/* Sidebar Navigation */}
            <div className={`w-[70px] sm:w-[240px] flex-shrink-0 border-r border-[#1a1a1a] flex flex-col transition-all duration-300 z-50 ${selectedTicker ? 'hidden md:flex' : 'flex'}`}>
                {/* Logo Area */}
                <div className="h-16 flex items-center justify-center sm:justify-start sm:px-6 border-b border-[#1a1a1a]">
                    <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-900/20 shrink-0">
                        <span className="text-white font-black text-lg">M</span>
                    </div>
                    <span className="ml-3 font-bold text-white text-lg tracking-tight hidden sm:block">
                        Momentum
                    </span>
                </div>

                {/* Navigation Items */}
                <nav className="flex-1 overflow-y-auto p-2 space-y-0.5 custom-scrollbar">
                    <div className="text-[10px] uppercase font-bold text-slate-600 px-3 mb-1 mt-1 hidden sm:block">Platform</div>
                    <button onClick={() => setView('dashboard')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'dashboard' ? 'bg-blue-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'dashboard' ? 'text-blue-500' : 'text-slate-500 group-hover:text-blue-400'}`}>⚡</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Dashboard</span>
                    </button>
                    <button onClick={() => setView('portfolio')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'portfolio' ? 'bg-purple-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'portfolio' ? 'text-purple-500' : 'text-slate-500 group-hover:text-purple-400'}`}>🌍</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Global Portfolio</span>
                    </button>

                    <div className="my-1 border-t border-[#1a1a1a]"></div>
                    <div className="text-[10px] uppercase font-bold text-slate-600 px-3 mb-1 hidden sm:block">Scanners</div>

                    <button onClick={() => setView('scanner')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'scanner' ? 'bg-green-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'scanner' ? 'text-green-500' : 'text-slate-500 group-hover:text-green-400'}`}>📡</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Scanner</span>
                    </button>
                    <button onClick={() => setView('options')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'options' ? 'bg-yellow-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'options' ? 'text-yellow-500' : 'text-slate-500 group-hover:text-yellow-400'}`}>🌊</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Options Flow</span>
                    </button>
                    <button onClick={() => setView('sharpe')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'sharpe' ? 'bg-violet-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'sharpe' ? 'text-violet-500' : 'text-slate-500 group-hover:text-violet-400'}`}>🧠</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Fundamentals</span>
                    </button>

                    <div className="my-1 border-t border-[#1a1a1a]"></div>
                    <div className="text-[10px] uppercase font-bold text-slate-600 px-3 mb-1 hidden sm:block">Portfolios</div>

                    <button onClick={() => setView('journal')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'journal' ? 'bg-teal-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'journal' ? 'text-teal-500' : 'text-slate-500 group-hover:text-teal-400'}`}>🇺🇸</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Wall St.</span>
                    </button>
                    <button onClick={() => setView('argentina')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'argentina' ? 'bg-sky-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'argentina' ? 'text-sky-500' : 'text-slate-500 group-hover:text-sky-400'}`}>🇦🇷</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Merval</span>
                    </button>
                    <button onClick={() => setView('crypto')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'crypto' ? 'bg-orange-600/10 text-white' : 'hover:bg-[#151515] text-slate-400 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'crypto' ? 'text-orange-500' : 'text-slate-500 group-hover:text-orange-400'}`}>₿</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Crypto</span>
                    </button>

                    <div className="my-1 border-t border-[#1a1a1a]"></div>

                    <button onClick={() => setView('watchlist')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'watchlist' ? 'bg-amber-600/10 text-white' : 'hover:bg-[#151515] text-slate-500 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'watchlist' ? 'text-amber-500' : 'text-slate-500 group-hover:text-amber-400'}`}>⭐</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Watchlist</span>
                    </button>
                    <button onClick={() => setView('charts')} className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'charts' ? 'bg-cyan-600/10 text-white' : 'hover:bg-[#151515] text-slate-500 hover:text-white'}`}>
                        <span className={`text-lg ${view === 'charts' ? 'text-cyan-500' : 'text-slate-500 group-hover:text-cyan-400'}`}>🕯️</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Advanced Charts</span>
                    </button>
                </nav>

                {/* Settings at bottom */}
                <div className="p-2 border-t border-[#1a1a1a]">
                    <button
                        onClick={() => setView('settings')}
                        className={`group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 ${view === 'settings' ? 'bg-blue-600/10 text-white' : 'hover:bg-[#151515] text-slate-500 hover:text-white'}`}
                    >
                        <span className={`text-lg ${view === 'settings' ? 'text-blue-500' : 'text-slate-500 group-hover:text-blue-400'}`}>⚙️</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Settings</span>
                    </button>

                    <button
                        onClick={handleLogout}
                        className="group relative w-full flex items-center p-2 rounded-xl transition-all duration-200 hover:bg-red-900/20 text-slate-500 hover:text-red-400 mt-1"
                    >
                        <span className="text-lg">🚪</span>
                        <span className="ml-3 text-sm font-medium hidden sm:block">Sign Out</span>
                    </button>

                    <div className="text-[9px] text-slate-700 font-mono text-center mt-1 hidden sm:block">v3.1 Auth</div>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col h-full relative overflow-hidden">
                {!selectedTicker && (
                    <header className="sticky top-0 z-30 backdrop-blur-md border-b border-[#1a1a1a] px-6 py-4 flex justify-between items-center shrink-0">
                        <h1 className="text-xl font-bold text-white uppercase tracking-wider flex items-center gap-2">
                            {view === 'dashboard' && '⚡ Market Dashboard'}
                            {view === 'scanner' && '📡 Weekly RSI Scanner'}
                            {view === 'options' && '🌊 Options Flow'}
                            {view === 'journal' && '🇺🇸 Portfolio Wall St'}
                            {view === 'watchlist' && '⭐ Watchlist'}
                            {view === 'charts' && '🕯️ Advanced Charts'}
                            {view === 'argentina' && '🇦🇷 Portfolio Merval'}
                            {view === 'crypto' && '₿ Portfolio Crypto'}
                            {view === 'portfolio' && '🌍 Global Portfolio'}
                            {view === 'sharpe' && '📊 Fundamental Scanner'}
                            {view === 'settings' && '⚙️ Settings'}
                        </h1>
                        <div className="flex items-center gap-4">
                            {deferredPrompt && (
                                <button onClick={handleInstallClick} className="bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white px-3 py-1.5 rounded-lg font-bold text-xs shadow-lg animate-pulse flex items-center gap-1">
                                    <span>📲</span> Install App
                                </button>
                            )}
                            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
                            <span className="text-xs font-mono text-green-500 hidden sm:inline">
                                {token ? JSON.parse(atob(token.split('.')[1])).sub : 'User Connected'}
                            </span>

                            <MarketClock />

                            <button
                                onClick={() => setShowConnectModal(true)}
                                className="bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg font-medium text-xs border border-slate-700 transition flex items-center gap-2"
                            >
                                <span>🔗</span> <span className="hidden sm:inline">Connect Device</span>
                            </button>
                        </div>
                    </header>
                )}

                {showConnectModal && <ConnectModal onClose={() => setShowConnectModal(false)} />}

                <main className="flex-1 overflow-y-auto relative custom-scrollbar">
                    {!selectedTicker ? (
                        <div className="min-h-full">
                            {/* Lazy mount + stay mounted: components load on first visit, then cache in memory */}
                            <div style={{ display: view === 'dashboard' ? 'block' : 'none' }}>
                                {visitedViews.has('dashboard') && <MarketDashboard onTickerClick={handleTickerClick} />}
                            </div>
                            <div style={{ display: view === 'scanner' ? 'block' : 'none' }}>
                                {visitedViews.has('scanner') && <Scanner onTickerClick={handleTickerClick} />}
                            </div>
                            <div style={{ display: view === 'options' ? 'block' : 'none' }}>
                                {visitedViews.has('options') && <OptionsScanner />}
                            </div>
                            <div style={{ display: view === 'journal' ? 'block' : 'none' }}>
                                {visitedViews.has('journal') && <TradeJournal />}
                            </div>
                            <div style={{ display: view === 'watchlist' ? 'block' : 'none' }}>
                                {visitedViews.has('watchlist') && <WatchlistPanel />}
                            </div>
                            <div style={{ display: view === 'charts' ? 'block' : 'none' }}>
                                {visitedViews.has('charts') && <ChartsPanel />}
                            </div>
                            <div style={{ display: view === 'argentina' ? 'block' : 'none' }}>
                                {visitedViews.has('argentina') && <ArgentinaPanel />}
                            </div>
                            <div style={{ display: view === 'crypto' ? 'block' : 'none' }}>
                                {visitedViews.has('crypto') && <CryptoJournal />}
                            </div>
                            <div style={{ display: view === 'portfolio' ? 'block' : 'none' }}>
                                {visitedViews.has('portfolio') && <PortfolioDashboardView />}
                            </div>
                            <div style={{ display: view === 'sharpe' ? 'block' : 'none' }}>
                                {visitedViews.has('sharpe') && <SharpePortfolioView />}
                            </div>
                            <div style={{ display: view === 'settings' ? 'block' : 'none' }}>
                                {visitedViews.has('settings') && <Settings />}
                            </div>
                        </div>

                    ) : (
                        <DetailView
                            ticker={selectedTicker}
                            onClose={handleCloseDetail}
                            overrideMetrics={overrideMetrics}
                        />
                    )}
                </main>
                <ChatCopilot />
            </div>
        </div>
    );
}



const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);

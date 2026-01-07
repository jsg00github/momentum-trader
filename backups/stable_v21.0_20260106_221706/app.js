const { useState, useEffect, useMemo, useRef, Fragment } = React;
const API_BASE = "/api";

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
    const start = new Date(startDate);
    const end = new Date(endDate);

    if (isNaN(start.getTime()) || start >= end) return 0;

    let tradingDays = 0;
    const current = new Date(start);
    current.setHours(0, 0, 0, 0);
    end.setHours(0, 0, 0, 0);

    while (current <= end) {
        const dayOfWeek = current.getDay();
        const dateStr = current.toISOString().split('T')[0];

        // Skip weekends (0 = Sunday, 6 = Saturday)
        // Skip US market holidays
        if (dayOfWeek !== 0 && dayOfWeek !== 6 && !US_MARKET_HOLIDAYS.has(dateStr)) {
            tradingDays++;
        }

        current.setDate(current.getDate() + 1);
    }

    return tradingDays;
}

// --- Components ---


// Chart Component for Equity Curve
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
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid, Cell, PieChart, Pie } = Recharts;

    useEffect(() => {
        if (viewMode === 'bar' || !chartContainerRef.current || !performanceData || !performanceData.line_data) return;

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
        const pData = lineData.dates.map((date, i) => ({
            time: date,
            value: lineData.portfolio[i]
        }));
        const sData = lineData.dates.map((date, i) => ({
            time: date,
            value: lineData.spy[i]
        }));

        portfolioSeries.setData(pData);
        spySeries.setData(sData);

        // Add Floating Labels at the end of the lines
        if (pData.length > 0) {
            const lastP = pData[pData.length - 1];
            portfolioSeries.createPriceLine({
                price: lastP.value,
                color: '#3b82f6',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: `${lastP.value >= 0 ? '+' : ''}${lastP.value.toFixed(2)}%`,
            });
        }
        if (sData.length > 0) {
            const lastS = sData[sData.length - 1];
            spySeries.createPriceLine({
                price: lastS.value,
                color: '#d946ef',
                lineWidth: 1,
                lineStyle: 2,
                axisLabelVisible: true,
                title: `${lastS.value >= 0 ? '+' : ''}${lastS.value.toFixed(2)}%`,
            });
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
    }, [viewMode, performanceData]);

    return (
        <div className="bg-slate-800/40 p-6 rounded-2xl border border-slate-700 shadow-2xl backdrop-blur-sm">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-slate-400 text-xs font-bold uppercase tracking-widest flex items-center gap-2">
                    <span className="text-lg">📈</span> Performance vs Benchmark
                </h3>
                <div className="flex items-center gap-2 bg-slate-900/50 p-1 rounded-lg border border-slate-700">
                    <button
                        onClick={() => setViewMode('line')}
                        className={`px-3 py-1 rounded-md text-[10px] font-bold transition flex items-center gap-1.5 ${viewMode === 'line' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <span>📉</span> LINE
                    </button>
                    <button
                        onClick={() => setViewMode('bar')}
                        className={`px-3 py-1 rounded-md text-[10px] font-bold transition flex items-center gap-1.5 ${viewMode === 'bar' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/40' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <span>📊</span> MONTHLY BARS
                    </button>
                </div>
            </div>

            {viewMode === 'line' ? (
                <div ref={chartContainerRef} className="w-full" />
            ) : (
                <div className="w-full">
                    <div className="h-[350px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={performanceData?.monthly_data}>
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
                                    {performanceData?.monthly_data.map((m, idx) => (
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
                                    {performanceData?.monthly_data.map((m, idx) => (
                                        <td key={idx} className={`p-3 text-center font-mono border-b border-white/5 ${m.spy >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                            <span className="mr-1">{m.spy >= 0 ? '▲' : '▼'}</span>
                                            {Math.abs(m.spy).toFixed(2)}%
                                        </td>
                                    ))}
                                </tr>
                                {/* Portfolio Row */}
                                <tr>
                                    <td className="p-3 flex items-center gap-2 border-b border-white/5 whitespace-nowrap">
                                        <div className="w-2.5 h-2.5 rounded-sm bg-[#3b82f6]"></div>
                                        <span className="font-bold text-slate-300">My Portfolio</span>
                                    </td>
                                    {performanceData?.monthly_data.map((m, idx) => (
                                        <td key={idx} className={`p-3 text-center font-mono border-b border-white/5 ${m.portfolio >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                            <span className="mr-1">{m.portfolio >= 0 ? '▲' : '▼'}</span>
                                            {Math.abs(m.portfolio).toFixed(2)}%
                                        </td>
                                    ))}
                                </tr>
                            </tbody>
                        </table>
                    </div>
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

    const processed = data.map((d, i) => {
        const prev = i > 0 ? data[i - 1] : d;
        const dailyChange = d.total_equity - prev.total_equity;
        const dailyChangePct = prev.total_equity > 0 ? (dailyChange / prev.total_equity) * 100 : 0;
        return {
            ...d,
            dailyChange,
            dailyChangePct,
            displayDate: new Date(d.snapshot_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
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
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-slate-300 font-bold text-xs uppercase tracking-wider flex items-center gap-2">
                        <span>📊 Daily P&L</span>
                    </h3>
                    {/* Toggle Buttons */}
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

                    {/* Portfolio News */}
                    <PortfolioNewsWidget tickers={holdings?.map(h => h.ticker) || []} />
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
    const [calendarData, setCalendarData] = useState([]);
    const [lastUpdated, setLastUpdated] = useState(null); // Timestamp for live data
    const [premarket, setPremarket] = useState({}); // Pre-market data per ticker
    const [openAnalytics, setOpenAnalytics] = useState(null);
    const [snapshotData, setSnapshotData] = useState([]);
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
    const [performanceData, setPerformanceData] = useState(null);

    // Group trades by ticker
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
                preMktChange: (!isHistory && premarket[ticker]) ? (premarket[ticker].extended_change_pct || 0) : 0
            };
        });
    }, [currentGroups, liveData, activeTab, premarket]);

    const sortedRows = useMemo(() => {
        let sortableItems = [...rowStats];
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
    }, [rowStats, sortConfig]);

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


    const fetchData = async () => {
        setLoading(true);
        try {
            const endpoints = [
                { url: `${API_BASE}/trades/list`, setter: (data) => setTrades(data.trades || []) },
                { url: `${API_BASE}/trades/metrics`, setter: setMetrics },
                { url: `${API_BASE}/trades/equity-curve`, setter: setEquityData },
                { url: `${API_BASE}/trades/calendar`, setter: setCalendarData },
                { url: `${API_BASE}/trades/analytics/open`, setter: setOpenAnalytics },
                { url: `${API_BASE}/trades/snapshots`, setter: setSnapshotData },
                { url: `${API_BASE}/trades/analytics/performance`, setter: setPerformanceData }
            ];

            await Promise.all(endpoints.map(ep =>
                axios.get(ep.url)
                    .then(res => ep.setter(res.data))
                    .catch(err => {
                        console.error(`Failed to fetch ${ep.url}:`, err);
                        // Optional: notify user about partial failure
                    })
            ));

            // Initial price fetch
            fetchLivePrices();
        } catch (err) {
            console.error("Failed to fetch journal data", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchLivePrices = async () => {
        setRefreshing(true);
        try {
            const res = await axios.get(`${API_BASE}/trades/open-prices`);
            setLiveData(res.data);
            setLastUpdated(new Date());

            // Also fetch pre-market for all open tickers
            const openTickers = Object.keys(res.data);
            openTickers.forEach(async (ticker) => {
                try {
                    const pm = await axios.get(`${API_BASE}/premarket/${ticker}`);
                    setPremarket(prev => ({ ...prev, [ticker]: pm.data }));
                } catch (e) {
                    // Silently fail for individual tickers
                }
            });
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
        fetchData();
        loadAlertSettings();

        // Auto-Refresh Live Prices every 60s
        const interval = setInterval(() => {
            fetchLivePrices();
        }, 60000);

        return () => clearInterval(interval);
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
            const res = await axios.post(`${API_BASE}/trades/import`, formData, {
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

    if (loading) return <div className="p-12 text-center text-slate-500">Loading Journal...</div>;

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
                        Portfolio Tracker
                        <button onClick={fetchLivePrices} disabled={refreshing} className="text-sm bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2 py-1 rounded transition text-slate-400">
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
                    <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition text-sm">
                        {showForm ? 'Cancel' : '+ Log Trade'}
                    </button>
                </div>
            </div>

            {showForm && <TradeForm onSave={() => { setShowForm(false); fetchData(); }} onCancel={() => setShowForm(false)} />}

            {/* Alert Configuration Modal */}
            {showAlertModal && (
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
            )}

            {/* Split Adjustment Modal */}
            {showSplitModal && (
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
            )}

            {/* Metrics Grid */}
            {/* Open Position Metrics */}
            {(() => {
                // Inline Calculation for Open Stats
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
                        const isLong = t.direction !== 'SHORT'; // Default Long
                        const pnl = (currentPrice - t.entry_price) * t.shares * (isLong ? 1 : -1);
                        openPnl += pnl;

                        const start = new Date(t.entry_date);
                        const end = new Date();
                        const diff = Math.abs(end - start);
                        const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
                        totalDays += days;
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

            {/* CONTENT AREA */}
            {activeSubTab === 'analytics' ? (
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
                                                        href={`/?ticker=${ticker}&entry=${avgPpc}&stop=${groupTrades[0]?.stop_loss || ''}&target=${groupTrades[0]?.target || ''}`}
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
                                                        const pm = premarket[ticker];
                                                        const pmChange = pm?.extended_change_pct;
                                                        if (pmChange === null || pmChange === undefined) return <span className="text-slate-600 text-[10px]">-</span>;
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

                                                {/* Weekly RSI */}
                                                <td className="p-2 text-center border-r border-slate-800 font-bold font-mono">
                                                    {(() => {
                                                        const rsi = row.live?.rsi_weekly;
                                                        if (!rsi) return <span className="text-slate-600">-</span>;
                                                        const colorClass = rsi.bullish ? "text-green-400" : "text-red-400";
                                                        return (
                                                            <div className="flex flex-col items-center leading-none">
                                                                <span className={colorClass}>{rsi.val.toFixed(1)}</span>
                                                                <span className={`text-[9px] ${colorClass}`}>{rsi.bullish ? '▲' : '▼'}</span>
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
                                                <td className="p-2 bg-slate-900"></td>
                                            </tr>

                                            {/* DETAIL ROWS */}
                                            {isExpanded && groupTrades.map(trade => {
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
                                                const daysHeld = Math.ceil(Math.abs(end - start) / (1000 * 60 * 60 * 24));

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
                                            })}
                                        </Fragment>
                                    );
                                })}
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

                    {/* DEBUG PANEL */}
                    <div className="mt-8 p-4 bg-slate-800/50 rounded border border-yellow-500/30 text-xs font-mono text-yellow-500">
                        <h3 className="font-bold border-b border-yellow-500/30 mb-2">🔍 SYSTEM DIAGNOSTICS</h3>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p>Total Trades Loaded: {trades.length}</p>
                                <p>Active Groups: {Object.keys(activeGroups).length}</p>
                                <p>History Groups: {Object.keys(historyGroups).length}</p>
                                <p>Active Tab: {activeTab}</p>
                            </div>
                            <div>
                                <p>API Status: {loading ? 'Loading...' : 'Idle'}</p>
                                <p>First Trade: {trades.length > 0 ? JSON.stringify(trades[0].ticker) : 'None'}</p>
                                <p>Live Data Keys: {Object.keys(liveData).length}</p>
                            </div>
                        </div>
                    </div>
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
        axios.get(`${API_BASE}/watchlist`).then(res => setWatchlist(res.data)).catch(console.error);
        const interval = setInterval(() => {
            axios.get(`${API_BASE}/watchlist`).then(res => setWatchlist(res.data)).catch(console.error);
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

        // RSI Chart (Solid White for main RSI)
        if (chartData.some(d => d.rsi_weekly)) {
            const rsiSeries = rsiChart.addLineSeries({
                color: '#ffffff',
                lineWidth: 2,
                title: 'Weekly RSI',
            });
            const rsiData = chartData.filter(d => d.rsi_weekly).map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d.rsi_weekly,
            }));
            rsiSeries.setData(rsiData);

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

            const response = await fetch('/api/watchlist/', {
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

    useEffect(() => {
        let interval;
        if (scanning) {
            interval = setInterval(async () => {
                try {
                    const res = await axios.get(`${API_BASE}/scan/progress`);
                    setProgress(res.data);

                    // If scan finished while we were polling, capture results
                    if (res.data.is_running === false && res.data.results && Array.isArray(res.data.results) && res.data.results.length > 0 && results.length === 0) {
                        setResults(res.data.results);
                        setStats({
                            scanned: res.data.scanned || (res.data.total > 0 ? res.data.total : 0),
                            count: res.data.results.length,
                            spy_ret_3m: res.data.spy_ret_3m || 0
                        });
                        setScanning(false);
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
            const res = await axios.post(`${API_BASE}/scan`, { limit });
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

    const handleSort = (key) => {
        let direction = 'desc';
        if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = 'asc';
        }
        setSortConfig({ key, direction });
    };

    const sortedResults = useMemo(() => {
        let sortableItems = [...results];
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
    }, [results, sortConfig]);

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
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('macd_d')}>
                                MACD
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('ema60_d')}>
                                EMA60
                            </th>
                            <th className="p-2 text-center cursor-pointer hover:text-white transition" onClick={() => handleSort('di_plus')}>
                                DMI & Strength
                            </th>
                            <th className="p-2 text-right cursor-pointer hover:text-white transition" onClick={() => handleSort('vol_ratio')}>
                                Vol
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
                                <td className="p-2 text-right text-xs font-mono">
                                    <span className={row.macd_d > 0 ? 'text-green-400' : 'text-red-400'}>
                                        {row.macd_d?.toFixed(2)}
                                    </span>
                                </td>
                                <td className={`p-2 text-right font-mono text-xs ${row.price > row.ema60_d ? 'text-green-400 font-bold' : 'text-slate-500'}`}>
                                    {row.ema60_d?.toFixed(0)}
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
                    <button
                        onClick={runScan}
                        disabled={scanning}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-blue-900/20 transition flex items-center gap-2"
                    >
                        {scanning ? 'Analyzing w.rsi...' : 'Run w.rsi Scan'}
                    </button>
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
    const [nyTime, setNyTime] = useState(new Date().toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false }));
    const [status, setStatus] = useState({ label: 'CLOSED', color: 'text-slate-500' });

    useEffect(() => {
        const timer = setInterval(() => {
            const now = new Date();
            const ny = new Intl.DateTimeFormat('en-US', {
                timeZone: 'America/New_York',
                hour: 'numeric',
                minute: 'numeric',
                second: 'numeric',
                hour12: false
            }).format(now);
            setNyTime(ny);

            const [h, m] = ny.split(':').map(Number);
            const totalMin = h * 60 + m;

            if (totalMin >= 570 && totalMin < 960) {
                setStatus({ label: 'MARKET OPEN', color: 'text-green-400' });
            } else if (totalMin >= 240 && totalMin < 570) {
                setStatus({ label: 'PRE-MARKET', color: 'text-yellow-400' });
            } else if (totalMin >= 960 && totalMin < 1200) {
                setStatus({ label: 'POST-MARKET', color: 'text-blue-400' });
            } else {
                setStatus({ label: 'MARKET CLOSED', color: 'text-slate-500' });
            }
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="flex items-center gap-3 bg-slate-900 border border-slate-700 px-3 py-1.5 rounded-lg shadow-inner">
            <div className="flex flex-col">
                <span className="text-[9px] text-slate-500 uppercase font-black leading-none">New York Time</span>
                <span className="text-sm font-mono font-bold text-white leading-tight">{nyTime}</span>
            </div>
            <div className="h-6 w-px bg-slate-700"></div>
            <div className={`text-[10px] font-black px-2 py-0.5 rounded border ${status.color.replace('text-', 'border-')}/30 ${status.color.replace('text-', 'bg-')}/10 ${status.color}`}>
                {status.label}
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

// Market Dashboard Component
function MarketDashboard({ onTickerClick }) {
    const [marketData, setMarketData] = useState(null);
    const [loading, setLoading] = useState(true);

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
        axios.get(`${API_BASE}/market-status`)
            .then(res => {
                setMarketData(res.data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    if (loading) return <div className="p-8 text-center text-slate-500">Loading Market Intelligence...</div>;
    if (!marketData) return <div className="p-8 text-center text-red-400">Error loading data</div>;

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
            </div>
        );
    };



    const sorted1m = [...sectors].sort((a, b) => b['1m'] - a['1m']).slice(0, 5);
    const sorted2m = [...sectors].sort((a, b) => b['2m'] - a['2m']).slice(0, 5);
    const sorted3m = [...sectors].sort((a, b) => b['3m'] - a['3m']).slice(0, 5);

    return (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Main Content (9 Columns) */}
            <div className="lg:col-span-8 space-y-8">
                {/* Section 0: Expert Summary */}
                {expert_summary && (
                    <div className="bg-gradient-to-r from-blue-900/40 to-slate-900/40 border border-blue-700/30 rounded-xl p-6 relative overflow-hidden shadow-lg">
                        <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                            <svg className="w-32 h-32 text-blue-400" fill="currentColor" viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z" /></svg>
                        </div>
                        <div className="relative z-10">
                            <div className="flex items-center gap-3 mb-4">
                                <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                                    <span>🎙️</span> {expert_summary.mood.toUpperCase()} BRIEFING
                                </h2>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${expert_summary.mood.includes('Bullish') ? 'bg-green-500/20 text-green-400' : (expert_summary.mood.includes('Bearish') ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400')}`}>
                                    {expert_summary.mood}
                                </span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
                                <div className="bg-slate-900/30 p-3 rounded-lg border border-slate-700/30 transition hover:border-blue-500/20">
                                    <h4 className="text-slate-400 font-bold uppercase text-[10px] mb-2 tracking-wider">The Market Setup</h4>
                                    <p className="text-slate-300 leading-relaxed text-xs" dangerouslySetInnerHTML={{ __html: formatExpertText(expert_summary.setup) }}></p>
                                </div>
                                <div className="bg-slate-900/30 p-3 rounded-lg border border-slate-700/30 transition hover:border-blue-500/20">
                                    <h4 className="text-slate-400 font-bold uppercase text-[10px] mb-2 tracking-wider">Internals & Breadth</h4>
                                    <p className="text-slate-300 leading-relaxed text-xs" dangerouslySetInnerHTML={{ __html: formatExpertText(expert_summary.internals) }}></p>
                                </div>
                                <div className="bg-blue-900/10 p-3 rounded-lg border border-blue-500/20 transition hover:border-blue-500/40">
                                    <h4 className="text-blue-400 font-bold uppercase text-[10px] mb-2 tracking-wider">Tactical Action Plan</h4>
                                    <p className="text-slate-200 leading-relaxed italic border-l-2 border-blue-500/50 pl-3 py-1 text-xs">
                                        "{expert_summary.play}"
                                    </p>
                                </div>
                            </div>

                            {/* Headlines Section */}
                            {expert_summary.headlines && expert_summary.headlines.length > 0 && (
                                <div className="mt-4 pt-4 border-t border-slate-700/30">
                                    <h4 className="text-slate-400 font-bold uppercase text-[10px] mb-3 tracking-wider flex items-center gap-2">
                                        📰 Market Headlines
                                    </h4>
                                    <div className="space-y-2">
                                        {expert_summary.headlines.map((h, i) => (
                                            <div key={i} className="flex items-start gap-2 text-xs">
                                                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${h.sentiment === 'bullish' ? 'bg-green-500/20 text-green-400' : (h.sentiment === 'bearish' ? 'bg-red-500/20 text-red-400' : 'bg-slate-500/20 text-slate-400')}`}>
                                                    {h.ticker || '📈'}
                                                </span>
                                                <span className="text-slate-300 leading-tight flex-1">{h.headline}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
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
    );
}

// Settings Component for Backups
function Settings() {
    const [backups, setBackups] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadBackups();
    }, []);

    const loadBackups = async () => {
        setLoading(true);
        try {
            const res = await axios.get(`${API_BASE}/backups/list`);
            setBackups(res.data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateBackup = async () => {
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/backups/create`);
            await loadBackups();
            alert("Backup created successfully!");
        } catch (e) {
            alert("Failed to create backup");
        } finally {
            setLoading(false);
        }
    };

    const handleRestore = async (filename) => {
        if (!confirm(`Are you sure you want to restore from ${filename}? Current data will be overwritten.`)) return;
        setLoading(true);
        try {
            await axios.post(`${API_BASE}/backups/restore/${filename}`);
            alert("System restored! Please restart the backend server manually if needed.");
        } catch (e) {
            alert("Restore failed: " + e.response?.data?.detail || e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-6 container mx-auto max-w-4xl animate-fade-in text-white">
            <div className="flex justify-between items-center mb-8 border-b border-slate-700 pb-4">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">System Settings</h2>
                    <p className="text-slate-400 text-sm mt-1">Manage data backups and system configuration</p>
                </div>
                <button
                    onClick={handleCreateBackup}
                    disabled={loading}
                    className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-lg font-bold shadow-lg transition flex items-center gap-2"
                >
                    {loading ? 'Processing...' : '💾 Create New Backup'}
                </button>
            </div>

            <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-700 bg-slate-900/50 flex justify-between items-center">
                    <h3 className="font-bold flex items-center gap-2">
                        <span>📦 Available Backups</span>
                    </h3>
                    <button onClick={loadBackups} className="text-slate-400 hover:text-white text-sm">↻ Refresh</button>
                </div>

                {backups.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 italic">No backups found. Create one to get started.</div>
                ) : (
                    <div className="divide-y divide-slate-700">
                        {backups.map(b => (
                            <div key={b.filename} className="p-4 flex justify-between items-center hover:bg-slate-700/50 transition">
                                <div>
                                    <div className="font-mono text-blue-300 font-bold">{b.filename}</div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        Created: {b.created} • Size: {(b.size / 1024).toFixed(1)} KB
                                    </div>
                                </div>
                                <button
                                    onClick={() => handleRestore(b.filename)}
                                    className="bg-slate-700 hover:bg-red-900/40 hover:text-red-300 text-slate-300 px-4 py-2 rounded border border-slate-600 hover:border-red-500/30 text-xs font-bold transition"
                                >
                                    Restore
                                </button>
                            </div>
                        ))}
                    </div>
                )}
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

// Main App Component
function App() {
    const [view, setView] = useState('dashboard');
    const [selectedTicker, setSelectedTicker] = useState(() => {
        const params = new URLSearchParams(window.location.search);
        return params.get('ticker');
    });
    const [overrideMetrics, setOverrideMetrics] = useState(() => {
        const params = new URLSearchParams(window.location.search);
        const entry = parseFloat(params.get('entry') || 0);
        const stop = parseFloat(params.get('stop') || 0);
        const target = parseFloat(params.get('target') || 0);
        if (entry || stop || target) {
            return { entry, stop_loss: stop, target };
        }
        return {};
    });
    const [showConnectModal, setShowConnectModal] = useState(false);

    // PWA Install Logic (Global)
    const [deferredPrompt, setDeferredPrompt] = useState(null);

    useEffect(() => {
        const handler = (e) => {
            e.preventDefault();
            setDeferredPrompt(e);
        };
        window.addEventListener('beforeinstallprompt', handler);
        return () => window.removeEventListener('beforeinstallprompt', handler);
    }, []);

    const handleInstallClick = async () => {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        console.log(`User response to the install prompt: ${outcome}`);
        setDeferredPrompt(null);
    };

    const handleTickerClick = (ticker) => {
        // Open in new tab with ticker parameter
        window.open(`/?ticker=${ticker}`, '_blank');
        // Still set it locally in case the user prefers the current tab (optional, but keep it for robustness)
        setSelectedTicker(ticker);
        setOverrideMetrics({});
    };

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
                const response = await fetch('/api/watchlist');
                const data = await response.json();
                setWatchlist(data);
            } catch (error) {
                console.error('Error loading watchlist:', error);
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

    // Listen for custom tickerClick events (from dangerouslySetInnerHTML)
    useEffect(() => {
        const handler = (e) => handleTickerClick(e.detail);
        window.addEventListener('tickerClick', handler);
        return () => window.removeEventListener('tickerClick', handler);
    }, []);

    const handleCloseDetail = () => {
        setSelectedTicker(null);
        setOverrideMetrics({});
        // Clean URL without reloading
        const url = new URL(window.location);
        url.searchParams.delete('ticker');
        url.searchParams.delete('entry');
        url.searchParams.delete('stop');
        url.searchParams.delete('target');
        window.history.replaceState({}, '', url);
    };

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 font-sans selection:bg-purple-500 selection:text-white">
            <div className="flex h-screen overflow-hidden">
                {/* Sidebar Navigation - Hidden in Dedicated Chart View */}
                {!selectedTicker && (
                    <nav className="w-20 lg:w-64 bg-slate-950 border-r border-slate-800 flex flex-col justify-between flex-shrink-0 relative z-20">
                        <div>
                            <div className="p-6 flex items-center gap-3">
                                <div className="w-8 h-8 rounded bg-gradient-to-tr from-blue-500 to-purple-600 flex items-center justify-center font-black text-white text-lg shadow-lg shadow-purple-900/20">
                                    M
                                </div>
                                <span className="font-black tracking-tight text-xl hidden lg:block bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                                    MOMENTUM
                                </span>
                            </div>

                            <div className="px-3 space-y-1">
                                <button
                                    onClick={() => setView('dashboard')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'dashboard' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">📊</span>
                                    <span className="hidden lg:block">Dashboard</span>
                                </button>
                                <button
                                    onClick={() => setView('scanner')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'scanner' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">⚡</span>
                                    <span className="hidden lg:block">Scanner</span>
                                </button>
                                <button
                                    onClick={() => setView('options')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'options' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">🎯</span>
                                    <span className="hidden lg:block">Options Flow</span>
                                </button>
                                <button
                                    onClick={() => setView('journal')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'journal' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">📓</span>
                                    <span className="hidden lg:block">Journal</span>
                                </button>
                                <button
                                    onClick={() => setView('watchlist')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'watchlist' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">⭐</span>
                                    <span className="hidden lg:block">Watchlist</span>
                                </button>
                                <button
                                    onClick={() => setView('charts')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'charts' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">📈</span>
                                    <span className="hidden lg:block">Charts</span>
                                </button>
                                <button
                                    onClick={() => setView('settings')}
                                    className={`w-full text-left px-4 py-3 rounded-lg flex items-center gap-3 transition-all duration-200 group ${view === 'settings' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-900/20 font-bold' : 'hover:bg-slate-900 text-slate-400 hover:text-white'}`}
                                >
                                    <span className="text-xl">⚙️</span>
                                    <span className="hidden lg:block">Settings</span>
                                </button>
                            </div>
                        </div>

                        <div className="p-4 border-t border-slate-800">
                            <div className="text-xs text-slate-600 font-mono text-center">v2.1.0 • Stable</div>
                        </div>
                    </nav>
                )}

                {/* Main Content Area */}
                <main className="flex-1 overflow-y-auto bg-slate-900 relative">
                    {/* Top Bar / Header - Hidden in Dedicated Chart View */}
                    {!selectedTicker && (
                        <div className="sticky top-0 z-10 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-8 py-4 flex justify-between items-center">
                            <h1 className="text-xl font-bold text-white uppercase tracking-wider">
                                {view === 'dashboard' && 'Market Command Center'}
                                {view === 'scanner' && 'Algorithmic Scanner'}
                                {view === 'options' && 'Options Flow Intelligence'}
                                {view === 'journal' && 'Trade Journal & Performance'}
                                {view === 'watchlist' && 'Watchlist & Alerts'}
                                {view === 'charts' && 'Advanced Charts'}
                                {view === 'settings' && 'System Configuration'}
                            </h1>
                            <div className="flex items-center gap-4">
                                {deferredPrompt && (
                                    <button onClick={handleInstallClick} className="bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white px-3 py-1.5 rounded-lg font-bold text-xs shadow-lg animate-pulse flex items-center gap-1">
                                        <span>📲</span> Install App
                                    </button>
                                )}
                                <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse"></div>
                                <span className="text-xs font-mono text-green-500">SYSTEM ONLINE</span>
                                <span className="text-xs font-mono text-slate-500">|</span>

                                <MarketClock />

                                <button
                                    onClick={() => setShowConnectModal(true)}
                                    className="bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg font-medium text-xs border border-slate-700 transition flex items-center gap-2"
                                >
                                    <span>🔗</span> <span className="hidden sm:inline">Connect Device</span>
                                </button>
                            </div>
                        </div>
                    )}

                    {showConnectModal && <ConnectModal onClose={() => setShowConnectModal(false)} />}

                    {/* Views and Dedicated Analysis */}
                    {!selectedTicker ? (
                        <React.Fragment>
                            {view === 'dashboard' && <MarketDashboard onTickerClick={handleTickerClick} />}
                            {view === 'scanner' && <Scanner onTickerClick={handleTickerClick} />}
                            {view === 'options' && <OptionsScanner />}
                            {view === 'journal' && <TradeJournal />}
                            {view === 'watchlist' && <WatchlistPanel />}
                            {view === 'charts' && <ChartsPanel />}
                            {view === 'settings' && <Settings />}
                        </React.Fragment>
                    ) : (
                        <DetailView
                            ticker={selectedTicker}
                            onClose={handleCloseDetail}
                            overrideMetrics={overrideMetrics}
                        />
                    )}
                </main>
            </div>
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);

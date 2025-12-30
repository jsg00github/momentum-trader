const { useState, useEffect, useMemo, useRef, Fragment } = React;
const API_BASE = "/api";

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
// --- Open Positions Analytics Component ---
function OpenPositionsAnalytics({ data }) {
    if (!data) return <div className="p-8 text-center text-slate-500 italic">Loading Open Analytics...</div>;

    const { exposure, suggestions } = data;

    return (
        <div className="space-y-6 animate-fade-in mb-8">
            {/* 1. Portfolio Health Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                    label="Active Capital"
                    value={`$${(exposure?.total_invested ?? 0).toLocaleString()}`}
                    subtext={`${exposure?.active_count ?? 0} positions`}
                    icon="💰"
                />
                <MetricCard
                    label="Risk Exposure"
                    value={`$${(exposure?.total_risk_dollars ?? 0).toLocaleString()}`}
                    subtext="Total Open Risk"
                    icon="⚠️"
                    color={(exposure?.total_risk_dollars ?? 0) > 1000 ? "text-orange-400" : "text-white"}
                />
                <MetricCard
                    label="Unrealized PnL"
                    value={`$${(exposure?.unrealized_pnl ?? 0).toLocaleString()}`}
                    subtext="Paper Gains/Losses"
                    icon="chart_with_upwards_trend"
                    color={(exposure?.unrealized_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}
                />
                {/* Placeholder for future metric */}
                <div className="bg-slate-800 p-4 rounded-xl border border-slate-700 opacity-50 flex items-center justify-center text-slate-500 text-xs italic">
                    More metrics coming soon...
                </div>
            </div>

            {/* 2. Actionable Insights */}
            {suggestions?.length > 0 && (
                <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden shadow-lg">
                    <div className="bg-slate-900/50 p-4 border-b border-slate-700 flex justify-between items-center">
                        <h3 className="text-slate-300 font-bold text-sm uppercase tracking-wider flex items-center gap-2">
                            <span>🧠</span> Smart Suggestions
                        </h3>
                        <span className="text-[10px] text-slate-500 bg-slate-800 px-2 py-1 rounded">
                            Based on Vol & Trend
                        </span>
                    </div>
                    <table className="w-full text-left">
                        <thead className="bg-slate-900 text-slate-500 text-[10px] uppercase font-bold tracking-wider">
                            <tr>
                                <th className="p-3 pl-4">Ticker</th>
                                <th className="p-3 text-center">Action</th>
                                <th className="p-3">Technical Reasoning</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/50 text-xs text-slate-300">
                            {suggestions.map((s, i) => (
                                <tr key={i} className="hover:bg-slate-700/20 transition">
                                    <td className="p-3 pl-4 font-bold font-mono text-white">{s.ticker}</td>
                                    <td className="p-3 text-center">
                                        <span className={`px-2 py-1 rounded font-bold uppercase text-[10px] ${s.action === 'ADD' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
                                            {s.action}
                                        </span>
                                    </td>
                                    <td className="p-3 italic opacity-80">{s.reason}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
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
                totalHistoryCost += t.entry_price * t.shares;

                if (!minEntryDate || new Date(t.entry_date) < new Date(minEntryDate)) {
                    minEntryDate = t.entry_date;
                }

                if (t.status === 'OPEN') {
                    openShares += t.shares;
                    openCost += t.entry_price * t.shares;
                    const currentPrice = live.price || t.entry_price;
                    const upnl = (currentPrice - t.entry_price) * t.shares * (isLong ? 1 : -1);
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

            let daysHeld = 0;
            if (minEntryDate) {
                const start = new Date(minEntryDate);
                const end = isHistory && maxExitDate ? new Date(maxExitDate) : new Date();
                const diffTime = Math.abs(end - start);
                daysHeld = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
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
            const [tradesRes, metricsRes, equityRes, calRes, openAnRes] = await Promise.all([
                axios.get(`${API_BASE}/trades/list`),
                axios.get(`${API_BASE}/trades/metrics`),
                axios.get(`${API_BASE}/trades/equity-curve`),
                axios.get(`${API_BASE}/trades/calendar`),
                axios.get(`${API_BASE}/trades/analytics/open`)
            ]);
            setTrades(tradesRes.data.trades);
            setMetrics(metricsRes.data);
            setEquityData(equityRes.data);
            setCalendarData(calRes.data);
            setOpenAnalytics(openAnRes.data);

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
            console.log(`Updated group ${field} to ${value}`);
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
                    📝 Trade Log
                </button>
                <button
                    onClick={() => setActiveSubTab('analytics')}
                    className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 flex items-center gap-2 ${activeSubTab === 'analytics' ? 'border-purple-500 text-purple-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                >
                    📈 Analytics
                </button>
            </div>

            {activeSubTab === 'analytics' ? (
                <>
                    <OpenPositionsAnalytics data={openAnalytics} />
                    <JournalAnalytics equityData={equityData} calendarData={calendarData} />
                </>
            ) : (
                <>
                    {/* SPREADSHEET TABLE */}
                    <div className="flex gap-6 border-b border-slate-800 mb-6">
                        <button
                            onClick={() => setActiveTab('active')}
                            className={`pb-3 text-sm font-bold tracking-wide transition border-b-2 ${activeTab === 'active' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                        >
                            ACTIVE POSITIONS
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
                                    <th onClick={() => requestSort('avgPpc')} className="p-2 text-right border-r border-slate-800 cursor-pointer hover:text-white transition">
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
                                    <th className="p-2 text-center border-r border-slate-800 text-purple-300">PreMkt %</th>
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
                                                    {emas.ema_8 ? (
                                                        <span>
                                                            ${emas.ema_8.toFixed(2)}
                                                            {(() => {
                                                                const dateKey = groupTrades[0]?.entry_date;
                                                                const map = row.live.violations_map || {};
                                                                const count = map[dateKey]?.ema_8;
                                                                return typeof count === 'number' && (
                                                                    <sup className="text-[9px] text-white ml-0.5 font-bold">({count})</sup>
                                                                );
                                                            })()}
                                                        </span>
                                                    ) : '-'}
                                                </td>
                                                <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_21)}`}>
                                                    {emas.ema_21 ? (
                                                        <span>
                                                            ${emas.ema_21.toFixed(2)}
                                                            {(() => {
                                                                const dateKey = groupTrades[0]?.entry_date;
                                                                const map = row.live.violations_map || {};
                                                                const count = map[dateKey]?.ema_21;
                                                                return typeof count === 'number' && (
                                                                    <sup className="text-[9px] text-white ml-0.5 font-bold">({count})</sup>
                                                                );
                                                            })()}
                                                        </span>
                                                    ) : '-'}
                                                </td>
                                                <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_35)}`}>
                                                    {emas.ema_35 ? (
                                                        <span>
                                                            ${emas.ema_35.toFixed(2)}
                                                            {(() => {
                                                                const dateKey = groupTrades[0]?.entry_date;
                                                                const map = row.live.violations_map || {};
                                                                const count = map[dateKey]?.ema_35;
                                                                return typeof count === 'number' && (
                                                                    <sup className="text-[9px] text-white ml-0.5 font-bold">({count})</sup>
                                                                );
                                                            })()}
                                                        </span>
                                                    ) : '-'}
                                                </td>
                                                <td className={`p-2 text-center ${getEmaColor(currentPrice || 0, emas.ema_200)}`}>
                                                    {emas.ema_200 ? (
                                                        <span>
                                                            ${emas.ema_200.toFixed(2)}
                                                            {(() => {
                                                                const dateKey = groupTrades[0]?.entry_date;
                                                                const map = row.live.violations_map || {};
                                                                const count = map[dateKey]?.ema_200;
                                                                return typeof count === 'number' && (
                                                                    <sup className="text-[9px] text-white ml-0.5 font-bold">({count})</sup>
                                                                );
                                                            })()}
                                                        </span>
                                                    ) : '-'}
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
                </>
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
                <Line type="monotone" dataKey="ema_21" stroke="#22d3ee" strokeWidth={1} dot={false} strokeDasharray="5 5" name="EMA 21" />
                <Line type="monotone" dataKey="ema_200" stroke="#facc15" strokeWidth={1} dot={false} name="EMA 200" />

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

// TradingView Chart Component with separate RSI panel
function TradingViewChart({ chartData, elliottWave, metrics }) {
    const chartContainerRef = React.useRef(null);
    const rsiContainerRef = React.useRef(null);
    const chartRef = React.useRef(null);
    const rsiChartRef = React.useRef(null);

    React.useEffect(() => {
        if (!chartContainerRef.current || !rsiContainerRef.current || !chartData || chartData.length === 0) return;

        // Create main price chart (70% height)
        const chart = LightweightCharts.createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            layout: {
                background: { color: '#1e293b' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: '#334155' },
                horzLines: { color: '#334155' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#475569',
            },
            timeScale: {
                borderColor: '#475569',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        chartRef.current = chart;

        // Create RSI chart (30% height)
        const rsiChart = LightweightCharts.createChart(rsiContainerRef.current, {
            width: rsiContainerRef.current.clientWidth,
            height: rsiContainerRef.current.clientHeight,
            layout: {
                background: { color: '#1e293b' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: '#334155' },
                horzLines: { color: '#334155' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#475569',
            },
            timeScale: {
                borderColor: '#475569',
                timeVisible: true,
                secondsVisible: false,
                visible: false,
            },
        });

        rsiChartRef.current = rsiChart;

        // Sync time scales
        // Sync time scales
        const syncTimeScale = () => {
            const timeRange = chart.timeScale().getVisibleRange();
            // Ensure we have a valid range with non-null from/to
            if (timeRange && timeRange.from !== null && timeRange.to !== null) {
                try {
                    rsiChart.timeScale().setVisibleRange(timeRange);
                } catch (e) {
                    console.warn('Sync error ignored:', e);
                }
            }
        };

        chart.timeScale().subscribeVisibleTimeRangeChange(syncTimeScale);

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
        addEMA('#ef4444', 'ema_200', 'EMA 200', 3);

        // Add Volume
        const volumeSeries = chart.addHistogramSeries({
            color: '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: '',
            scaleMargins: { top: 0.7, bottom: 0 },
        });

        const volumeData = chartData.filter(d => d.volume).map(d => ({
            time: new Date(d.date).getTime() / 1000,
            value: d.volume,
            color: d.close >= d.open ? '#26a69a80' : '#ef535080',
        }));
        if (volumeData.length > 0) volumeSeries.setData(volumeData);

        // Elliott Wave markers
        if (elliottWave?.wave_labels && elliottWave.wave_labels.length > 0) {
            const colors = {
                '1': '#10b981', '2': '#ef4444', '3': '#8b5cf6', '4': '#f59e0b',
                '5': '#06b6d4', 'A': '#ec4899', 'B': '#6366f1', 'C': '#14b8a6'
            };
            const markers = elliottWave.wave_labels.map(wave => ({
                time: new Date(wave.date).getTime() / 1000,
                position: wave.type === 'peak' ? 'aboveBar' : 'belowBar',
                color: colors[wave.label] || '#a855f7',
                shape: 'circle',
                text: wave.label,
                size: 2,
            }));
            candlestickSeries.setMarkers(markers);
        }

        // Price lines
        candlestickSeries.createPriceLine({
            price: metrics.entry,
            color: '#3b82f6',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'ENTRY',
        });

        candlestickSeries.createPriceLine({
            price: metrics.target,
            color: '#22c55e',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'TARGET',
        });

        candlestickSeries.createPriceLine({
            price: metrics.stop_loss,
            color: '#ef4444',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: 'STOP',
        });

        chart.timeScale().fitContent();

        // RSI Chart
        if (chartData.some(d => d.rsi_weekly)) {
            const rsiSeries = rsiChart.addLineSeries({
                color: '#eab308',
                lineWidth: 2,
                title: 'Weekly RSI',
            });
            const rsiData = chartData.filter(d => d.rsi_weekly).map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d.rsi_weekly,
            }));
            rsiSeries.setData(rsiData);

            if (chartData.some(d => d.rsi_sma_3)) {
                const rsiSma3Series = rsiChart.addLineSeries({
                    color: '#f59e0b',
                    lineWidth: 1,
                    title: 'RSI SMA 3',
                });
                const rsiSma3Data = chartData.filter(d => d.rsi_sma_3).map(d => ({
                    time: new Date(d.date).getTime() / 1000,
                    value: d.rsi_sma_3,
                }));
                rsiSma3Series.setData(rsiSma3Data);
            }

            if (chartData.some(d => d.rsi_sma_14)) {
                const rsiSma14Series = rsiChart.addLineSeries({
                    color: '#ef4444',
                    lineWidth: 1,
                    title: 'RSI SMA 14',
                });
                const rsiSma14Data = chartData.filter(d => d.rsi_sma_14).map(d => ({
                    time: new Date(d.date).getTime() / 1000,
                    value: d.rsi_sma_14,
                }));
                rsiSma14Series.setData(rsiSma14Data);
            }

            rsiChart.timeScale().fitContent();
        }

        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight,
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
            if (rsiChartRef.current) rsiChartRef.current.remove();
        };
    }, [chartData, elliottWave, metrics]);

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div ref={chartContainerRef} style={{ width: '100%', height: '70%' }} />
            <div ref={rsiContainerRef} style={{ width: '100%', height: '30%' }} />
        </div>
    );
}

function MetricCard({ label, value, subtext, color = "text-white" }) {
    return (
        <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
            <div className="text-slate-400 text-sm uppercase tracking-wide">{label}</div>
            <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
            {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
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

    if (!metrics) {
        return (
            <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center backdrop-blur-sm">
                <div className="text-red-400 text-xl">No metrics data available for {ticker}</div>
            </div>
        );
    }

    // Only require metrics if no overrides provided
    if (!hasOverrides && (!metrics.entry || !metrics.target || !metrics.stop_loss)) {
        return (
            <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center backdrop-blur-sm">
                <div className="text-red-400 text-xl">Invalid metrics data for {ticker}</div>
            </div>
        );
    }

    // Calculate min/max for Y-axis scaling
    const prices = chart_data.map(d => d.low);
    const minPrice = Math.min(...prices, metrics.stop_loss) * 0.95;
    const maxPrice = Math.max(...chart_data.map(d => d.high), metrics.target) * 1.05;

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
                        {/* Only show Bull Flag badge if pattern is actually detected */}
                        {metrics.is_bull_flag && (
                            <span className="bg-blue-900/50 text-blue-200 px-3 py-1 rounded text-sm border border-blue-700">Bull Flag Pattern</span>
                        )}
                        <span className="text-slate-400 py-1 text-sm">Target: <span className="text-green-400">${metrics.target.toFixed(2)}</span></span>
                        {metrics.expected_days && (
                            <span className="bg-purple-900/30 text-purple-300 px-3 py-1 rounded text-sm border border-purple-700">
                                ⏱ Projected: ~{metrics.expected_days} dias ({(metrics.percent_move || 0).toFixed(1)}% move)
                            </span>
                        )}
                    </div>
                </div>
                <button onClick={onClose} className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg border border-slate-600 transition">
                    Close
                </button>
            </div>

            {/* Content Component Grid */}
            <div className="flex-1 grid grid-cols-12 gap-6 min-h-0">
                <div className="col-span-9 bg-slate-800 rounded-xl border border-slate-700 p-4 flex flex-col">
                    <div className="flex-1 w-full min-h-0">
                        <TradingViewChart
                            chartData={chart_data}
                            elliottWave={data.elliott_wave}
                            metrics={metrics}
                        />
                    </div>
                </div>

                {/* Metrics Sidebar */}
                <div className="col-span-3 flex flex-col gap-4 overflow-y-auto">
                    {/* Elliott Wave Analysis */}
                    {data.elliott_wave && (
                        <div className="bg-gradient-to-br from-purple-900/20 to-blue-900/20 p-4 rounded-lg border border-purple-700/30">
                            <div className="text-purple-300 text-sm font-semibold uppercase tracking-wide mb-2">🌊 Elliott Wave</div>
                            {/* Wave Colors Legend */}
                            {data.elliott_wave?.wave_labels && data.elliott_wave.wave_labels.length > 0 && (
                                <div className="mb-3 p-2 bg-slate-900/40 rounded border border-purple-700/20">
                                    <div className="text-purple-200 text-xs font-semibold mb-1.5">📍 Etiquetas de Ondas</div>
                                    <div className="flex flex-wrap gap-2">
                                        {data.elliott_wave.wave_labels.map((wave, idx) => {
                                            const waveColors = {
                                                '1': 'bg-green-500', '2': 'bg-red-500', '3': 'bg-purple-500', '4': 'bg-amber-500',
                                                '5': 'bg-cyan-500', 'A': 'bg-pink-500', 'B': 'bg-indigo-500', 'C': 'bg-teal-500'
                                            };
                                            const bgColor = waveColors[wave.label] || 'bg-purple-500';

                                            return (
                                                <div key={idx} className="flex items-center gap-1.5 bg-slate-800/60 px-2 py-1 rounded">
                                                    <div className={`w-5 h-5 ${bgColor} rounded font-bold flex items-center justify-center text-white text-xs`}>
                                                        {wave.label}
                                                    </div>
                                                    <div className="text-slate-300 text-xs">
                                                        ${wave.price.toFixed(2)}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* Pattern with Cycle Degree */}
                            <div className="flex items-center gap-2 mb-1">
                                <div className="text-white text-lg font-bold">
                                    {data.elliott_wave.elliott_wave?.pattern || 'Análisis en proceso'}
                                </div>
                                {data.elliott_wave.cycle_degree && (
                                    <div className="bg-purple-800/40 px-2 py-0.5 rounded text-purple-200 text-xs font-semibold">
                                        {data.elliott_wave.cycle_degree}
                                    </div>
                                )}
                            </div>

                            {data.elliott_wave.elliott_wave?.current_wave && (
                                <div className="text-purple-200 text-sm mb-2">
                                    {data.elliott_wave.elliott_wave.current_wave}
                                </div>
                            )}

                            {/* Duration/Amplitude */}
                            {data.elliott_wave.elliott_wave?.total_duration_days && (
                                <div className="text-xs text-slate-400 mb-2">
                                    {data.elliott_wave.elliott_wave.total_duration_days}d | {data.elliott_wave.elliott_wave.total_amplitude_pct}%
                                </div>
                            )}

                            {/* Wave Details */}
                            {data.elliott_wave.wave_details && (
                                <div className="mt-3 bg-slate-900/50 border border-slate-700 rounded p-2 max-h-60 overflow-y-auto">
                                    <div className="text-purple-300 text-xs font-semibold mb-2">📊 Detalle de Ondas</div>
                                    {Object.entries(data.elliott_wave.wave_details).map(([key, wave]) => (
                                        <div key={key} className="mb-2 pb-2 border-b border-slate-700/50 last:border-0">
                                            <div className="flex justify-between">
                                                <span className="text-purple-400 font-bold text-sm">W{key.split('_')[1]}</span>
                                                <span className={`text-xs px-1.5 py-0.5 rounded ${wave.wave_type === 'Impulse' ? 'bg-green-900/40 text-green-300' : 'bg-orange-900/40 text-orange-300'
                                                    }`}>{wave.wave_type}</span>
                                            </div>
                                            <div className="grid grid-cols-2 gap-1 text-xs mt-1">
                                                <div className="text-slate-400">{wave.start_date} → {wave.end_date}</div>
                                                <div className="text-slate-400 text-right">{wave.duration_days}d</div>
                                                <div className="text-slate-300">${wave.start_price} → ${wave.end_price}</div>
                                                <div className={`text-right font-semibold ${wave.amplitude_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {wave.amplitude_pct > 0 ? '+' : ''}{wave.amplitude_pct}%
                                                </div>
                                                <div className="text-slate-400 col-span-2">Vel: {wave.velocity_per_day}%/día</div>
                                                {wave.retracement_pct && (
                                                    <div className="text-yellow-400 col-span-2">Retroceso: {wave.retracement_pct}%</div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Parent Context & Next Move */}
                            {data.elliott_wave.parent_context?.detected && (
                                <div className="mt-3 bg-blue-900/20 border border-blue-700/30 rounded p-2">
                                    <div className="text-blue-300 text-xs font-semibold mb-1">🔍 Contexto Grado Mayor</div>
                                    <div className="text-blue-200 text-xs mb-1">
                                        {data.elliott_wave.parent_context.parent_pattern}
                                    </div>
                                    <div className="text-slate-300 text-xs">
                                        Contexto: {data.elliott_wave.parent_context.context}
                                    </div>
                                </div>
                            )}

                            {data.elliott_wave.next_move_prediction && (
                                <div className="mt-3 bg-cyan-900/20 border border-cyan-700/30 rounded p-2">
                                    <div className="text-cyan-300 text-xs font-semibold mb-1">🎯 Predicción Próximo Movimiento</div>
                                    <div className="text-cyan-100 text-xs leading-relaxed">
                                        {data.elliott_wave.next_move_prediction}
                                    </div>
                                </div>
                            )}

                            <div className="text-slate-300 text-xs mt-2 border-t border-purple-700/30 pt-2">
                                {data.elliott_wave.interpretation}
                            </div>

                            {/* Fibonacci Projections */}
                            {data.elliott_wave.fibonacci_projections && (
                                <div className="mt-3 bg-orange-900/20 border border-orange-700/30 rounded p-2">
                                    <div className="text-orange-300 text-xs font-semibold mb-1">📏 Fibonacci Wave 5 Targets</div>
                                    <div className="grid grid-cols-2 gap-1 text-xs">
                                        <div className="text-slate-400">1.618x: <span className="text-orange-400 font-semibold">${data.elliott_wave.fibonacci_projections.levels['1.618'].toFixed(2)}</span></div>
                                        <div className="text-slate-400">2.0x: <span className="text-orange-300">${data.elliott_wave.fibonacci_projections.levels['2.0'].toFixed(2)}</span></div>
                                    </div>
                                    <div className="text-xs text-orange-200 mt-1">Primary: ${data.elliott_wave.fibonacci_projections.primary_target.toFixed(2)}</div>
                                </div>
                            )}

                            {/* Elliott Wave Pattern Guide */}
                            <div className="mt-3 bg-slate-900/60 border border-slate-600/30 rounded p-2">
                                <div className="text-slate-300 text-xs font-semibold mb-2">📖 Guía de Patrones</div>
                                <div className="space-y-2 text-xs">
                                    {/* Expanded Flat */}
                                    <div className="bg-slate-800/50 p-1.5 rounded">
                                        <div className="text-blue-400 font-semibold">Wave A {'>'} Wave 5</div>
                                        <div className="text-slate-400 text-[10px]">Corrección Expansiva - patrón alcista fuerte</div>
                                    </div>

                                    {/* Truncated Fifth */}
                                    <div className="bg-slate-800/50 p-1.5 rounded">
                                        <div className="text-orange-400 font-semibold">Wave 5 {'<'} Wave 3</div>
                                        <div className="text-slate-400 text-[10px]">Quinta Truncada - debilidad, posible reversión</div>
                                    </div>

                                    {/* Extended Fifth */}
                                    <div className="bg-slate-800/50 p-1.5 rounded">
                                        <div className="text-green-400 font-semibold">Wave 5 {'>'}{'>'} Wave 3</div>
                                        <div className="text-slate-400 text-[10px]">Quinta Extendida - momentum alcista extremo</div>
                                    </div>

                                    {/* Wave 3 Rule */}
                                    <div className="bg-slate-800/50 p-1.5 rounded">
                                        <div className="text-purple-400 font-semibold">Wave 3 = Más Larga</div>
                                        <div className="text-slate-400 text-[10px]">Regla: Wave 3 nunca es la más corta (1,3,5)</div>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-2 text-xs text-purple-400">
                                Fase: {data.elliott_wave.phase}
                            </div>
                        </div>
                    )}

                    {/* Expert Trading Analysis */}
                    {data.elliott_wave?.expert_analysis && (
                        <div className="bg-gradient-to-br from-cyan-900/20 to-blue-900/20 border border-cyan-700/30 rounded-lg p-3">
                            <div className="text-cyan-300 text-sm font-semibold uppercase tracking-wide mb-2">
                                🎯 Expert Analysis
                            </div>

                            {/* Current Phase */}
                            <div className="mb-2">
                                <div className="text-xs text-slate-400">Current Phase</div>
                                <div className="text-cyan-100 font-semibold text-sm">
                                    {data.elliott_wave.expert_analysis.current_phase}
                                </div>
                                <div className="text-slate-300 text-xs">
                                    Position: Wave {data.elliott_wave.expert_analysis.wave_position} ({data.elliott_wave.expert_analysis.degree})
                                </div>
                            </div>

                            {/* Larger Trend */}
                            <div className="mb-2 text-xs">
                                <span className="text-slate-400">Larger Context: </span>
                                <span className="text-blue-300">{data.elliott_wave.expert_analysis.larger_trend}</span>
                            </div>

                            {/* Entry Signals */}
                            <div className="mb-2">
                                <div className="text-xs text-slate-400 mb-1">Entry Strategy</div>
                                <div className={`text-xs px-2 py-1 rounded mb-1 ${data.elliott_wave.expert_analysis.risk_level === 'Very High' ? 'bg-red-900/30 text-red-200' :
                                    data.elliott_wave.expert_analysis.risk_level === 'High' ? 'bg-orange-900/30 text-orange-200' :
                                        data.elliott_wave.expert_analysis.risk_level === 'Low-Medium' ? 'bg-green-900/30 text-green-200' :
                                            'bg-yellow-900/30 text-yellow-200'
                                    }`}>
                                    Risk: {data.elliott_wave.expert_analysis.risk_level}
                                </div>
                                <div className="space-y-0.5">
                                    {data.elliott_wave.expert_analysis.entry_signals.map((signal, idx) => (
                                        <div key={idx} className="text-xs text-slate-300 flex items-start">
                                            <span className="text-cyan-400 mr-1">•</span>
                                            <span>{signal}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Price Projections */}
                            {Object.keys(data.elliott_wave.expert_analysis.price_projections).length > 0 && (
                                <div className="mt-2 pt-2 border-t border-cyan-700/20">
                                    <div className="text-xs text-slate-400 mb-1">Price Projections</div>
                                    <div className="space-y-1 text-xs">
                                        {data.elliott_wave.expert_analysis.price_projections.correction_shallow && (
                                            <div>
                                                <span className="text-slate-400">Correction 38.2%: </span>
                                                <span className="text-orange-300 font-semibold">
                                                    ${data.elliott_wave.expert_analysis.price_projections.correction_shallow.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                        {data.elliott_wave.expert_analysis.price_projections.correction_typical && (
                                            <div>
                                                <span className="text-slate-400">Correction 50%: </span>
                                                <span className="text-orange-400 font-semibold">
                                                    ${data.elliott_wave.expert_analysis.price_projections.correction_typical.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                        {data.elliott_wave.expert_analysis.price_projections.correction_deep && (
                                            <div>
                                                <span className="text-slate-400">Correction 61.8%: </span>
                                                <span className="text-red-300 font-semibold">
                                                    ${data.elliott_wave.expert_analysis.price_projections.correction_deep.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                        {data.elliott_wave.expert_analysis.price_projections.next_impulse_target && (
                                            <div>
                                                <span className="text-slate-400">Next Impulse Target: </span>
                                                <span className="text-green-300 font-semibold">
                                                    ${data.elliott_wave.expert_analysis.price_projections.next_impulse_target.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                        {data.elliott_wave.expert_analysis.price_projections.next_wave_3_target && (
                                            <div>
                                                <span className="text-slate-400">Next Wave 3: </span>
                                                <span className="text-green-400 font-semibold">
                                                    ${data.elliott_wave.expert_analysis.price_projections.next_wave_3_target.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                        {data.elliott_wave.expert_analysis.price_projections.next_wave_5_target && (
                                            <div>
                                                <span className="text-slate-400">Next Wave 5: </span>
                                                <span className="text-green-500 font-semibold">
                                                    ${data.elliott_wave.expert_analysis.price_projections.next_wave_5_target.toFixed(2)}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    <MetricCard
                        label="Projected Timeframe"
                        value={`~${metrics.expected_days || 45} días`}
                        subtext={`Velocidad: ${(metrics.percent_move / metrics.expected_days).toFixed(2)}% /día`}
                        color="text-purple-400"
                    />
                    <MetricCard
                        label="Potential Gain"
                        value={`+${((metrics.target - metrics.entry) / metrics.entry * 100).toFixed(2)}%`}
                        subtext="Entry to Target"
                        color="text-green-400"
                    />
                    <MetricCard
                        label="Reward / Risk"
                        value={((metrics.target - metrics.entry) / (metrics.entry - metrics.stop_loss)).toFixed(2)}
                        subtext="Target Ratio"
                        color="text-yellow-400"
                    />
                    <MetricCard
                        label="Entry Price"
                        value={`$${metrics.entry.toFixed(2)}`}
                        color="text-blue-400"
                    />
                    <MetricCard
                        label="Stop Loss"
                        value={`$${metrics.stop_loss.toFixed(2)}`}
                        color="text-red-400"
                    />
                    <MetricCard
                        label="Target"
                        value={`$${metrics.target.toFixed(2)}`}
                        color="text-green-400"
                    />
                    <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
                        <h4 className="text-slate-400 text-sm uppercase mb-2">Structure Stats</h4>
                        <div className="space-y-2 text-sm">
                            {metrics.mast_height !== undefined && (
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Mast Height</span>
                                    <span className="text-slate-200">${metrics.mast_height.toFixed(2)}</span>
                                </div>
                            )}
                            {metrics.flag_depth !== undefined && (
                                <div className="flex justify-between">
                                    <span className="text-slate-500">Flag Depth</span>
                                    <span className="text-slate-200">${metrics.flag_depth.toFixed(2)}</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div >
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

    useEffect(() => {
        let interval;
        if (scanning) {
            interval = setInterval(async () => {
                try {
                    const res = await axios.get(`${API_BASE}/scan/progress`);
                    setProgress(res.data);
                } catch (e) {
                    console.error("Error fetching progress", e);
                }
            }, 1000);
        }
        return () => clearInterval(interval);
    }, [scanning]);

    const runScan = async () => {
        setScanning(true);
        setResults([]);
        setStats(null);
        setProgress({ total: 0, current: 0 });
        try {
            const res = await axios.post(`${API_BASE}/scan`, { limit });
            if (res.data.error) {
                alert("Scan Error: " + res.data.error);
            } else {
                setResults(res.data.results);
                setStats({
                    scanned: res.data.scanned,
                    count: res.data.results.length,
                    spy_ret_3m: res.data.spy_ret_3m
                });
            }
        } catch (e) {
            console.error(e);
            alert("Scan failed: " + (e.response?.data?.detail || e.message));
        } finally {
            setScanning(false);
            setProgress({ total: 0, current: 0 });
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
                            <th className="p-3 text-right">Price</th>
                            <th className="p-3 text-right">Vol</th>
                            <th className="p-3 text-right">RSI</th>
                            <th className="p-3 text-right">Score</th>
                            <th className="p-3">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {data.map((row, idx) => (
                            <tr key={idx} className="hover:bg-slate-700/50 transition duration-150">
                                <td className="p-3 font-bold text-white flex items-center gap-2">
                                    <span className="w-8 h-8 rounded bg-slate-700 flex items-center justify-center text-xs">{row.ticker}</span>
                                </td>
                                <td className="p-3 text-right font-mono">${row.price.toFixed(2)}</td>
                                <td className="p-3 text-right text-slate-400">{(row.volume / 1000000).toFixed(1)}M</td>
                                <td className={`p-3 text-right font-bold ${row.rsi < 30 ? 'text-green-400' : row.rsi > 70 ? 'text-red-400' : 'text-slate-300'}`}>
                                    {row.rsi.toFixed(1)}
                                </td>
                                <td className="p-3 text-right font-bold text-blue-400">{row.score}</td>
                                <td className="p-3">
                                    <button
                                        onClick={() => onTickerClick(row.ticker)}
                                        className="bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white px-2 py-1 rounded text-xs transition border border-blue-600/30"
                                    >
                                        Chart
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
                        Algorithmic Market Scanner
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">Real-time technical analysis engine tracking 200+ top tickers.</p>
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
                        {scanning ? 'Analyzing Market...' : 'Run Algo Scan'}
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
                    <p className="text-slate-400 mt-2">Press "Run Algo Scan" to analyze the market structure.</p>
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

            {results.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {renderTable(results.filter(r => r.score >= 70), "High Probability Setups", "green", "🚀")}
                    {renderTable(results.filter(r => r.score < 70), "Watchlist Candidates", "yellow", "👀")}
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
                            <th className="p-3">Str/Exp</th>
                            <th className="p-3 text-right">Ratio</th>
                            <th className="p-3 text-right">Vol</th>
                            <th className="p-3 text-right">IV</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700">
                        {data.map((row, idx) => (
                            <tr key={idx} className="hover:bg-slate-700/50 transition duration-150">
                                <td className="p-3 font-bold text-white">{row.ticker}</td>
                                <td className="p-3">
                                    <div className="flex flex-col">
                                        <span className={`font-mono text-xs ${row.type === 'CALL' ? 'text-green-400' : 'text-red-400'}`}>
                                            ${row.strike} {row.type}
                                        </span>
                                        <span className="text-[10px] text-slate-500">{row.expiration}</span>
                                    </div>
                                </td>
                                <td className={`p-3 text-right font-bold ${row.vol_oi_ratio > 3 ? 'text-yellow-400' : 'text-slate-300'}`}>
                                    {row.vol_oi_ratio}x
                                </td>
                                <td className="p-3 text-right text-slate-300">{row.volume.toLocaleString()}</td>
                                <td className="p-3 text-right text-slate-400">{row.impliedVolatility}%</td>
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
                        Unusual Options Scanner
                        <span className="text-sm font-normal text-purple-400 border border-purple-500/30 bg-purple-500/10 px-2 py-1 rounded">Beta</span>
                    </h2>
                    <p className="text-slate-400 text-sm mt-1">Detects high volume option flow (Vol &gt; OI * 1.5) on tech leaders.</p>
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
    const [aiData, setAiData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        Promise.all([
            axios.get(`${API_BASE}/market-status`),
            axios.get(`${API_BASE}/ai-recommendations`)
        ])
            .then(([marketRes, aiRes]) => {
                setMarketData(marketRes.data);
                setAiData(aiRes.data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    if (loading) return <div className="p-8 text-center text-slate-500">Loading Market Intelligence...</div>;
    if (!marketData || !aiData) return <div className="p-8 text-center text-red-400">Error loading data</div>;

    const { indices, sectors, expert_summary, breadth, calendar } = marketData;
    const { Aggressive, Moderate, Safe } = aiData;

    const renderTrafficLight = (ticker, info) => {
        if (!info) return (
            <div className="p-4 rounded-xl border border-slate-700 bg-slate-800/50 flex flex-col items-center justify-center">
                <div className="text-sm font-bold opacity-50 mb-1">{ticker}</div>
                <div className="text-xl font-bold text-slate-500">N/A</div>
            </div>
        );

        const colorClass = info.color === 'Green' ? 'bg-green-500/20 text-green-400 border-green-500/50' :
            (info.color === 'Red' ? 'bg-red-500/20 text-red-400 border-red-500/50' : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50');

        return (
            <div className={`p-4 rounded-xl border ${colorClass} flex flex-col items-center justify-center`}>
                <div className="text-sm font-bold opacity-70 mb-1">{ticker}</div>
                <div className="text-2xl font-bold">{info.desc}</div>
                <div className="text-xs mt-2 opacity-60">Price: ${info.price} / EMA21: ${info.ema21}</div>
            </div>
        );
    };

    const renderAiCard = (item, type) => {
        const color = type === 'Aggressive' ? 'text-purple-400' : (type === 'Moderate' ? 'text-blue-400' : 'text-green-400');
        const border = type === 'Aggressive' ? 'border-purple-500/30' : (type === 'Moderate' ? 'border-blue-500/30' : 'border-green-500/30');

        return (
            <div key={item.ticker} className={`bg-slate-800 p-4 rounded-lg border ${border} mb-3`}>
                <div className="flex justify-between items-start mb-2">
                    <div>
                        <div className={`text-lg font-bold ${color}`}>{item.ticker}</div>
                        <div className="text-xs text-slate-500">Score: {item.score}</div>
                    </div>
                    <div className="text-right">
                        <div className="text-sm font-bold text-white">${item.metrics.price}</div>
                        <div className="text-xs text-slate-500">RSI: {item.metrics.rsi}</div>
                    </div>
                </div>
                <div className="space-y-1">
                    {item.rationale.map((r, i) => (
                        <div key={i} className="text-xs text-slate-300 flex items-center gap-1">
                            <span className="w-1 h-1 rounded-full bg-slate-500"></span> {r}
                        </div>
                    ))}
                </div>
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
                                <div className="bg-slate-900/30 p-3 rounded-lg border border-slate-700/30">
                                    <h4 className="text-slate-400 font-bold uppercase text-[10px] mb-2 tracking-wider">The Market Setup</h4>
                                    <p className="text-slate-300 leading-relaxed text-xs" dangerouslySetInnerHTML={{ __html: expert_summary.setup.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>') }}></p>
                                </div>
                                <div className="bg-slate-900/30 p-3 rounded-lg border border-slate-700/30">
                                    <h4 className="text-slate-400 font-bold uppercase text-[10px] mb-2 tracking-wider">Internals & Breadth</h4>
                                    <p className="text-slate-300 leading-relaxed text-xs" dangerouslySetInnerHTML={{ __html: expert_summary.internals.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>') }}></p>
                                </div>
                                <div className="bg-blue-900/10 p-3 rounded-lg border border-blue-500/20">
                                    <h4 className="text-blue-400 font-bold uppercase text-[10px] mb-2 tracking-wider">Tactical Action Plan</h4>
                                    <p className="text-slate-200 leading-relaxed italic border-l-2 border-blue-500/50 pl-3 py-1 text-xs">
                                        "{expert_summary.play}"
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Section 1: Market Health Indices */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {renderTrafficLight('SPY', indices.SPY)}
                    {renderTrafficLight('QQQ', indices.QQQ)}
                    {renderTrafficLight('IWM', indices.IWM)}

                    {indices.VIX ? (
                        <div className={`p-4 rounded-xl border flex flex-col items-center justify-center ${indices.VIX.level === 'Low' ? 'bg-blue-500/20 border-blue-500/50 text-blue-300' : 'bg-orange-500/20 border-orange-500/50 text-orange-300'}`}>
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
                </div>

                {/* Section 2: AI Picks & Recommendations */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Aggressive */}
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-lg">
                        <div className="text-purple-400 font-bold mb-4 flex justify-between items-center border-b border-purple-500/20 pb-2">
                            <span className="flex items-center gap-2">🚀 Aggressive</span>
                            <span className="text-[10px] opacity-60 font-normal uppercase">High Mom - Vol</span>
                        </div>
                        {Aggressive.length === 0 ? <div className="text-slate-600 text-sm italic py-4 text-center">No picks found.</div> : Aggressive.map(item => renderAiCard(item, 'Aggressive'))}
                    </div>

                    {/* Moderate */}
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-lg">
                        <div className="text-blue-400 font-bold mb-4 flex justify-between items-center border-b border-blue-500/20 pb-2">
                            <span className="flex items-center gap-2">⚖️ Moderate</span>
                            <span className="text-[10px] opacity-60 font-normal uppercase">Steady Trend</span>
                        </div>
                        {Moderate.length === 0 ? <div className="text-slate-600 text-sm italic py-4 text-center">No picks found.</div> : Moderate.map(item => renderAiCard(item, 'Moderate'))}
                    </div>

                    {/* Safe */}
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 shadow-lg">
                        <div className="text-green-400 font-bold mb-4 flex justify-between items-center border-b border-green-500/20 pb-2">
                            <span className="flex items-center gap-2">🛡️ Safe</span>
                            <span className="text-[10px] opacity-60 font-normal uppercase">Dip / Value</span>
                        </div>
                        {Safe.length === 0 ? <div className="text-slate-600 text-sm italic py-4 text-center">No picks found.</div> : Safe.map(item => renderAiCard(item, 'Safe'))}
                    </div>
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
                                <div key={s.ticker} className="flex justify-between items-center p-2 rounded hover:bg-slate-700/50">
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
                                            <div>
                                                <div className="text-green-400 font-bold mb-0.5">🏆 Leader</div>
                                                <div className="font-mono">{s.deep_dive.leader.ticker} <span className="text-green-300">+{s.deep_dive.leader.perf.toFixed(1)}%</span></div>
                                            </div>
                                            <div className="text-right">
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
    const [selectedTicker, setSelectedTicker] = useState(null);
    const [overrideMetrics, setOverrideMetrics] = useState({});
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

    // Parse URL Params
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const t = params.get('ticker');
        const entry = parseFloat(params.get('entry') || 0);
        const stop = parseFloat(params.get('stop') || 0);
        const target = parseFloat(params.get('target') || 0);

        if (t) {
            setSelectedTicker(t);
            if (entry || stop || target) {
                setOverrideMetrics({ entry, stop_loss: stop, target });
            }
        }
    }, []);

    const handleTickerClick = (ticker) => {
        setSelectedTicker(ticker);
        setOverrideMetrics({});
    };

    return (
        <div className="min-h-screen bg-slate-900 text-slate-100 font-sans selection:bg-purple-500 selection:text-white">
            <div className="flex h-screen overflow-hidden">
                {/* Sidebar Navigation */}
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

                {/* Main Content Area */}
                <main className="flex-1 overflow-y-auto bg-slate-900 relative">
                    {/* Top Bar / Header */}
                    <div className="sticky top-0 z-10 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-8 py-4 flex justify-between items-center">
                        <h1 className="text-xl font-bold text-white uppercase tracking-wider">
                            {view === 'dashboard' && 'Market Command Center'}
                            {view === 'scanner' && 'Algorithmic Scanner'}
                            {view === 'options' && 'Options Flow Intelligence'}
                            {view === 'journal' && 'Trade Journal & Performance'}
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

                    {showConnectModal && <ConnectModal onClose={() => setShowConnectModal(false)} />}

                    {view === 'dashboard' && <MarketDashboard onTickerClick={handleTickerClick} />}
                    {view === 'scanner' && <Scanner onTickerClick={handleTickerClick} />}
                    {view === 'options' && <OptionsScanner />}
                    {view === 'journal' && <TradeJournal />}
                    {view === 'settings' && <Settings />}
                </main>
            </div>
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);

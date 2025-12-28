const { useState, useEffect, useMemo } = React;
const API_BASE = "/api";

// --- Components ---


// TradingView Chart Component
function TradeJournal() {
    return (
        <div className="p-6 text-slate-400">
            <h2 className="text-2xl font-semibold mb-4">Trade Journal</h2>
            <p>This section is under construction. Add your journal UI here.</p>
        </div>
    );
}

// TradingView Chart Component
function TradingViewChart({ chartData, elliottWave, metrics }) {
    const chartContainerRef = React.useRef(null);
    const chartRef = React.useRef(null);

    React.useEffect(() => {
        if (!chartContainerRef.current || !chartData || chartData.length === 0) return;

        // Create chart
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

        // Add candlestick series
        const candlestickSeries = chart.addCandlestickSeries({
            upColor: '#10b981',
            downColor: '#ef4444',
            borderUpColor: '#10b981',
            borderDownColor: '#ef4444',
            wickUpColor: '#10b981',
            wickDownColor: '#ef4444',
        });

        // Convert data to TradingView format
        const tvData = chartData.map(d => ({
            time: new Date(d.date).getTime() / 1000, // Unix timestamp
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        })).filter(d => d.open && d.high && d.low && d.close);

        candlestickSeries.setData(tvData);

        // Add SMA lines
        const sma50Series = chart.addLineSeries({
            color: '#f59e0b',
            lineWidth: 2,
            lineStyle: 2,
            title: 'SMA 50',
        });

        const sma50Data = chartData
            .filter(d => d.sma_50)
            .map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d.sma_50,
            }));
        sma50Series.setData(sma50Data);

        const sma150Series = chart.addLineSeries({
            color: '#8b5cf6',
            lineWidth: 2,
            lineStyle: 2,
            title: 'SMA 150',
        });

        const sma150Data = chartData
            .filter(d => d.sma_150)
            .map(d => ({
                time: new Date(d.date).getTime() / 1000,
                value: d.sma_150,
            }));
        sma150Series.setData(sma150Data);

        // Add projection line
        if (chartData.some(d => d.projected)) {
            const projectionSeries = chart.addLineSeries({
                color: '#22c55e',
                lineWidth: 3,
                lineStyle: 2,
                title: 'Projection',
            });

            const projectionData = chartData
                .filter(d => d.projected)
                .map(d => ({
                    time: new Date(d.date).getTime() / 1000,
                    value: d.projected,
                }));
            projectionSeries.setData(projectionData);
        }

        // Add Elliott Wave markers
        if (elliottWave?.wave_labels && elliottWave.wave_labels.length > 0) {
            console.log('Elliott Wave Labels:', elliottWave.wave_labels);

            const markers = elliottWave.wave_labels.map(wave => {
                const colors = {
                    '1': '#10b981', '2': '#ef4444', '3': '#8b5cf6', '4': '#f59e0b',
                    '5': '#06b6d4', 'A': '#ec4899', 'B': '#6366f1', 'C': '#14b8a6'
                };

                // Use the 'type' field from backend - it knows if it's a peak or trough
                // Backend already calculated this based on actual price action
                const position = wave.type === 'peak' ? 'aboveBar' : 'belowBar';

                console.log(`Wave ${wave.label}: position=${position}, price=${wave.price.toFixed(2)}, type=${wave.type}`);

                return {
                    time: new Date(wave.date).getTime() / 1000,
                    position: position,
                    color: colors[wave.label] || '#a855f7',
                    shape: 'circle',
                    text: wave.label,
                    size: 2,
                };
            });

            candlestickSeries.setMarkers(markers);
        }

        // Add price lines
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

        // Fit content
        chart.timeScale().fitContent();

        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: chartContainerRef.current.clientHeight,
                });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
            }
        };
    }, [chartData, elliottWave, metrics]);

    return <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />;
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

function DetailView({ ticker, onClose }) {
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
                            <div className="flex justify-between">
                                <span className="text-slate-500">Mast Height</span>
                                <span className="text-slate-200">${metrics.mast_height.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-slate-500">Flag Depth</span>
                                <span className="text-slate-200">${metrics.flag_depth.toFixed(2)}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div >
        </div >
    );
}
function App() {
    console.log("🔥 App component rendering");

    const [results, setResults] = useState([]);
    const [view, setView] = useState('scanner'); // Scanner or Journal view
    const [scanning, setScanning] = useState(false);
    const [limit, setLimit] = useState(20000);
    const [selectedTicker, setSelectedTicker] = React.useState(null);
    const [scanResults, setScanResults] = React.useState([]);
    const [scanStats, setScanStats] = React.useState(null);
    const [loading, setLoading] = React.useState(false);


    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const ticker = params.get("ticker");
        if (ticker) {
            setSelectedTicker(ticker);
        }
    }, []);

    const runScan = async () => {
        setScanning(true);
        setResults([]);
        setScanStats(null);
        try {
            const res = await axios.post(`${API_BASE}/scan`, { limit }, { timeout: 0 });
            if (res.data.error) {
                alert("Scan Error: " + res.data.error);
            } else {
                setResults(res.data.results);
                setScanStats({
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
        }
    };

    return (
        <div className="h-full flex flex-col bg-slate-900 text-white">
            {/* Nav */}
            <div className="border-b border-slate-800 p-4 flex items-center justify-between bg-slate-950">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-lg">M</div>
                        <h1 className="font-bold text-xl tracking-tight">Momentum<span className="text-blue-500">Hunter</span></h1>
                    </div>
                    <div className="flex items-center gap-4">
                        {/* Tabs */}
                        <button
                            className={`px-4 py-2 rounded ${view === 'scanner' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'} transition`}
                            onClick={() => setView('scanner')}
                        >
                            🔍 Scanner
                        </button>
                        <button
                            className={`px-4 py-2 rounded ${view === 'journal' ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300'} transition`}
                            onClick={() => setView('journal')}
                        >
                            📊 Journal
                        </button>
                    </div>
                    <button
                        onClick={runScan}
                        disabled={scanning}
                        className={`px-6 py-2 rounded-lg font-medium transition flex items-center gap-2 ${scanning ? 'bg-slate-700 cursor-not-allowed text-slate-400' : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/20'}`}
                    >
                        {scanning ? (
                            <>
                                <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
                                Scanning ({limit})...
                            </>
                        ) : 'Run Scanner'}
                    </button>
                    <div className="h-6 w-px bg-slate-700 mx-2"></div>
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            const val = e.target.elements.ticker.value.trim().toUpperCase();
                            if (val) {
                                setSelectedTicker(val);
                                e.target.reset();
                            }
                        }}
                        className="flex items-center gap-2"
                    >
                        <input
                            name="ticker"
                            type="text"
                            placeholder="Check: e.g. GSIT"
                            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-sm w-32 focus:outline-none focus:border-blue-500 uppercase placeholder-slate-600"
                        />
                        <button type="submit" className="bg-slate-800 hover:bg-slate-700 border border-slate-600 px-3 py-1.5 rounded text-sm transition">
                            Go
                        </button>
                    </form>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto">
                {view === 'journal' ? (
                    <TradeJournal />
                ) : (
                    <div className="p-6 container mx-auto max-w-7xl">
                        {!scanning && results.length === 0 && !scanStats && (
                            <div className="h-64 flex flex-col items-center justify-center text-slate-500 border-2 border-dashed border-slate-800 rounded-xl">
                                <div className="text-4xl mb-2">🔭</div>
                                <p>Ready to scan the market.</p>
                                <p className="text-sm">Select a limit and hit Run.</p>
                            </div>
                        )}
                        {!scanning && scanStats && results.length === 0 && (
                            <div className="h-64 flex flex-col items-center justify-center text-slate-400 border-2 border-dashed border-slate-800 rounded-xl bg-slate-800/20">
                                <div className="text-4xl mb-2">🤷‍♂️</div>
                                <p className="font-medium text-lg">No matches found.</p>
                                <p className="text-slate-500">Scanned {scanStats.scanned} tickers. None met the strict momentum criteria.</p>
                            </div>
                        )}
                        {results.length > 0 && (
                            <div className="grid gap-4">
                                {/* Educational Guide */}
                                <div className="bg-blue-900/10 border border-blue-700/30 rounded-lg p-4 mb-2">
                                    <h3 className="text-blue-300 font-semibold mb-2 text-sm">📚 Cómo Interpretar los Resultados</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
                                        <div className="bg-green-900/20 border border-green-700/30 rounded p-2">
                                            <div className="text-green-400 font-bold mb-1">Grade A (85-100)</div>
                                            <div className="text-slate-300 mb-1">Setup Elite</div>
                                            <div className="text-slate-400">Máxima probabilidad. Momentum fuerte + consolidación ideal + volumen alto.</div>
                                            <div className="text-green-300 text-xs mt-1 font-semibold">→ Position sizing agresivo</div>
                                        </div>
                                        <div className="bg-blue-900/20 border border-blue-700/30 rounded p-2">
                                            <div className="text-blue-400 font-bold mb-1">Grade B (70-84)</div>
                                            <div className="text-slate-300 mb-1">Setup Fuerte</div>
                                            <div className="text-slate-400">Buen momentum con patrón sólido de consolidación.</div>
                                            <div className="text-blue-300 text-xs mt-1 font-semibold">→ Excelente R/R, size estándar</div>
                                        </div>
                                        <div className="bg-yellow-900/20 border border-yellow-700/30 rounded p-2">
                                            <div className="text-yellow-400 font-bold mb-1">Grade C (55-69)</div>
                                            <div className="text-slate-300 mb-1">Setup Decente</div>
                                            <div className="text-slate-400">Cumple criterios pero patrón menos ideal.</div>
                                            <div className="text-yellow-300 text-xs mt-1 font-semibold">→ Selectivo, confirmar entry</div>
                                        </div>
                                        <div className="bg-slate-800/50 border border-slate-700 rounded p-2">
                                            <div className="text-slate-400 font-bold mb-1">Grade D (&lt;55)</div>
                                            <div className="text-slate-300 mb-1">Marginal</div>
                                            <div className="text-slate-400">Califica pero setup de baja calidad.</div>
                                            <div className="text-slate-500 text-xs mt-1 font-semibold">→ Generalmente skip</div>
                                        </div>
                                    </div>
                                    <div className="mt-3 text-xs text-slate-400 border-t border-slate-700 pt-2">
                                        <strong className="text-blue-300">RS vs SPY:</strong> Outperformance vs el mercado. Valores altos (&gt;50%) indica momentum relativo excepcional.
                                    </div>
                                </div>

                                {/* Results Table */}
                                <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
                                    <table className="w-full text-left">
                                        <thead className="bg-slate-900 text-slate-400 text-xs uppercase tracking-wider">
                                            <tr>
                                                <th className="p-4">Ticker</th>
                                                <th className="p-4 text-center">Grade</th>
                                                <th className="p-4 text-right">RS vs SPY</th>
                                                <th className="p-4 text-right">Close</th>
                                                <th className="p-4 text-right">3M Rtn</th>
                                                <th className="p-4 text-right">1M Rtn</th>
                                                <th className="p-4 text-right">1W Rtn</th>
                                                <th className="p-4 text-center">Action</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-700/50">
                                            {results.map((r, i) => {
                                                const scoreColor = r.score >= 80 ? 'text-green-400 font-bold' :
                                                    r.score >= 60 ? 'text-yellow-400' : 'text-slate-300';
                                                const rsColor = r.rs_spy > 50 ? 'text-green-400' :
                                                    r.rs_spy > 0 ? 'text-blue-400' : 'text-slate-400';
                                                return (
                                                    <tr key={i} className="hover:bg-slate-700/30 transition group">
                                                        <td className="p-4 font-bold text-white">{r.ticker}</td>
                                                        <td className={`p-4 text-right ${scoreColor}`}>{r.score?.toFixed(1) || '-'}</td>
                                                        <td className={`p-4 text-right ${rsColor}`}>{r.rs_spy !== undefined ? `${r.rs_spy >= 0 ? '+' : ''}${r.rs_spy.toFixed(1)}%` : '-'}</td>
                                                        <td className="p-4 text-right text-slate-300">{r.close.toFixed(2)}</td>
                                                        <td className="p-4 text-right text-green-400">+{r.ret_3m_pct.toFixed(1)}%</td>
                                                        <td className="p-4 text-right text-yellow-400">{r.ret_1m_pct.toFixed(1)}%</td>
                                                        <td className="p-4 text-right text-green-400">+{r.ret_1w_pct.toFixed(1)}%</td>
                                                        <td className="p-4 text-center">
                                                            <a href={`?ticker=${r.ticker}`} target="_blank" rel="noopener noreferrer"
                                                                className="inline-block text-blue-400 hover:text-blue-300 text-sm font-medium px-3 py-1 rounded hover:bg-blue-900/30 transition opacity-0 group-hover:opacity-100">
                                                                Analyze Chart
                                                            </a>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Modal */}
            {selectedTicker && (
                <DetailView ticker={selectedTicker} onClose={() => setSelectedTicker(null)} />
            )}
        </div>
    );
}

// ---- Render root ----
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);

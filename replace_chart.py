import re

# Read the file
with open('backend/static/app_v2.js', 'r', encoding='utf-8') as f:
    content = f.read()

# New Trading View Chart Component with 2 separate charts
new_tradingview_chart = '''// TradingView Chart Component with separate RSI panel
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
        chart.timeScale().subscribeVisibleTimeRangeChange(() => {
            const timeRange = chart.timeScale().getVisibleRange();
            if (timeRange) {
                rsiChart.timeScale().setVisibleRange(timeRange);
            }
        });

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
}'''

# Find and replace the TradingViewChart function
# Pattern: from "function TradingViewChart" to the next "function" declaration
pattern = r'(// TradingView Chart.*?\nfunction TradingViewChart.*?)\n(?=function MetricCard)'

replacement = new_tradingview_chart + '\n\n'

content_new = re.sub(pattern, replacement, content, flags=re.DOTALL)

if content != content_new:
    with open('backend/static/app_v2.js', 'w', encoding='utf-8') as f:
        f.write(content_new)
    print("✅ TradingViewChart replaced successfully!")
    print(f"File size: {len(content)} → {len(content_new)} bytes")
else:
    print("❌ Pattern not found, trying manual search...")
    # Find where TradingViewChart starts
    idx = content.find('function TradingViewChart')
    if idx != -1:
        print(f"Found TradingViewChart at position {idx}")
        # Find next function
        next_func = content.find('\nfunction ', idx + 100)
        print(f"Next function at position {next_func}")

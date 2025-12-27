
import os
import re

APP_JS_PATH = r"backend/static/app_v2.js"

NEW_SCANNER_CODE = r"""// Algorithmic Scanner Component
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
                            <div className="text-xs text-slate-500 mt-2">
                                {((progress.current / progress.total) * 100).toFixed(0)}% Complete
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
"""

def main():
    try:
        with open(APP_JS_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to find the existing Scanner logic
        # We look for "function Scanner" and end before "function OptionsScanner"
        pattern = r"// Algorithmic Scanner Component\s*function Scanner.*?}\s*// Options Scanner Component"
        
        # We need dotall to match newlines
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            print("Could not find Scanner component block")
            # Fallback: try to find just the function start and assume end based on indentation or next component
            # But here we know OptionsScanner follows it
            return

        print(f"Found block of length {len(match.group(0))}")
        
        # Prepare replacement
        # We need to keep the "// Options Scanner Component" part at the end because the regex consumed it (or stopped before it?)
        # Actually my regex `.*?}` is non-greedy but effectively we want to replace until `// Options Scanner`.
        
        # Better approach: Split string
        parts = content.split("// Algorithmic Scanner Component")
        if len(parts) < 2:
            print("Could not split by header")
            return
            
        pre_scanner = parts[0]
        # logic after header
        scanner_and_rest = parts[1]
        
        # split by next component
        scanner_parts = scanner_and_rest.split("// Options Scanner Component")
        if len(scanner_parts) < 2:
            print("Could not find Options Scanner header")
            return
            
        post_scanner = scanner_parts[1]
        
        # Reassemble
        new_content = pre_scanner + NEW_SCANNER_CODE + "// Options Scanner Component" + post_scanner
        
        with open(APP_JS_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print("Successfully updated Scanner component")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

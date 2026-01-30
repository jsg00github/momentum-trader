import React, { useState } from 'react';
import { scannerService } from './services/scanner';

export default function ScannerWidget() {
    const [results, setResults] = useState([]);
    const [scanning, setScanning] = useState(false);
    const [lastScan, setLastScan] = useState(null);

    const runScan = async () => {
        setScanning(true);
        setResults([]);
        try { // Using default tickers if empty
            const data = await scannerService.scanMarket();
            setResults(data);
            setLastScan(new Date());
        } catch (e) {
            console.error(e);
            alert("Scan failed: " + e.message);
        } finally {
            setScanning(false);
        }
    };

    return (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 shadow-2xl animate-fade-in">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        🛰️ Market Scanner
                        <span className="text-[10px] bg-blue-600 px-2 py-0.5 rounded text-white uppercase tracking-wide">Beta</span>
                    </h2>
                    <p className="text-xs text-slate-500 mt-1">Real-time technical analysis engine</p>
                </div>
                <div className="flex items-center gap-4">
                    {lastScan && <span className="text-xs text-slate-500">Last: {lastScan.toLocaleTimeString()}</span>}
                    <button
                        onClick={runScan}
                        disabled={scanning}
                        className={`px-6 py-2 rounded-lg font-bold text-white transition flex items-center gap-2 ${scanning ? 'bg-slate-600 cursor-not-allowed' : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-lg shadow-blue-900/50'}`}
                    >
                        {scanning ? (
                            <>
                                <span className="animate-spin text-lg">⟳</span> Scanning...
                            </>
                        ) : (
                            <>
                                <span>🚀</span> Run Scan
                            </>
                        )}
                    </button>
                </div>
            </div>

            <div className="overflow-hidden border border-slate-700 rounded-lg bg-[#0f172a]">
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs whitespace-nowrap">
                        <thead className="bg-slate-900/50 text-slate-400 uppercase font-bold border-b border-slate-700/50">
                            <tr>
                                <th className="p-3 pl-4">Ticker</th>
                                <th className="p-3 text-right">Price</th>
                                <th className="p-3 text-right">Change</th>
                                <th className="p-3 text-center">Score</th>
                                <th className="p-3 text-center">RSI</th>
                                <th className="p-3">Signal</th>
                                <th className="p-3">Pattern</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                            {results.length === 0 ? (
                                <tr>
                                    <td colSpan="7" className="p-12 text-center text-slate-500 italic flex flex-col items-center gap-2">
                                        <div className="text-3xl opacity-20">📡</div>
                                        {scanning ? 'Analyzing market data...' : 'System ready. Initialize scan to find setups.'}
                                    </td>
                                </tr>
                            ) : (
                                results.map((r, i) => (
                                    <tr key={i} className="hover:bg-slate-800/60 transition group">
                                        <td className="p-3 pl-4 font-black text-white group-hover:text-blue-400 transition-colors">{r.ticker}</td>
                                        <td className="p-3 text-right font-mono text-yellow-300 font-bold">${r.price?.toFixed(2)}</td>
                                        <td className={`p-3 text-right font-bold ${r.dayChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {r.dayChange ? `${r.dayChange > 0 ? '+' : ''}${r.dayChange.toFixed(2)}%` : '-'}
                                        </td>
                                        <td className="p-3 text-center font-bold font-mono">
                                            <span className={`px-2 py-0.5 rounded ${r.score >= 80 ? 'bg-green-500/20 text-green-400' : 'bg-slate-700/30 text-slate-400'}`}>
                                                {r.score}
                                            </span>
                                        </td>
                                        <td className="p-3 text-center text-slate-300 font-mono">{r.rsi?.toFixed(1) || '-'}</td>
                                        <td className="p-3 font-bold">
                                            <span className={`px-2 py-1 rounded text-[10px] uppercase tracking-wider ${r.signal === 'BUY' ? 'bg-green-600/20 text-green-400 ring-1 ring-green-500/50' : (r.signal === 'SELL' ? 'bg-red-600/20 text-red-400 ring-1 ring-red-500/50' : 'text-slate-500')}`}>
                                                {r.signal}
                                            </span>
                                        </td>
                                        <td className="p-3 text-slate-300 italic">{r.setup || 'None'}</td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
            {results.length > 0 && (
                <div className="mt-4 text-[10px] text-slate-500 text-right">
                    Found {results.length} matches based on current technical criteria.
                </div>
            )}
        </div>
    );
}

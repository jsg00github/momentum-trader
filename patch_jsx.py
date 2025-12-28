
import os

target_file = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\app_v2.js"

new_jsx = """                            return (
                                <Fragment key={ticker}>
                                    {/* GROUP ROW */}
                                    <tr className="bg-slate-900 hover:bg-slate-800 transition border-b border-slate-800 cursor-pointer" onClick={() => toggleGroup(ticker)}>
                                        <td className="p-2 border-r border-slate-800 font-bold text-blue-400 sticky left-0 bg-slate-900 z-10 flex items-center gap-2">
                                            <span className="text-slate-500 text-[10px] w-4">{isExpanded ? '▼' : '▶'}</span>
                                            {ticker}
                                        </td>
                                        <td className="p-2 border-r border-slate-800 text-slate-500 italic text-[10px]">{groupTrades.length} trades</td>
                                        <td className="p-2 text-right border-r border-slate-800 text-yellow-200 font-mono font-bold">${avgPpc.toFixed(2)}</td>
                                        <td className="p-2 text-right border-r border-slate-800 text-slate-300 font-bold">{displayShares}</td>
                                        <td className="p-2 text-right border-r border-slate-800 text-slate-500">${displayCost.toFixed(0)}</td>

                                        {/* Aggregated P/L */}
                                        <td className={`p-2 text-right border-r border-slate-800 font-bold font-mono ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            ${totalPnl.toFixed(0)}
                                        </td>

                                        {/* Live Data / Avg Exit */}
                                        <td className="p-2 text-right border-r border-slate-800 text-blue-200 font-mono font-bold">
                                            ${displayPrice.toFixed(2)}
                                        </td>
                                        <td className={`p-2 text-center border-r border-slate-800 ${!isHistory && dayChange >= 0 ? 'text-green-400' : (!isHistory ? 'text-red-400' : 'text-slate-400')}`}>
                                            {displayChange}
                                        </td>
                                        <td className={`p-2 text-right border-r border-slate-800 font-bold ${totalPnlPct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {totalPnlPct.toFixed(2)}%
                                        </td>

                                        {/* SL/TP placeholders */}
                                        <td className="p-2 border-r border-slate-800 text-center text-slate-500">-</td>
                                        <td className="p-2 border-r border-slate-800 text-center text-slate-500">-</td>
                                        <td className="p-2 border-r border-slate-800 text-center text-slate-500">-</td>
                                        <td className="p-2 border-r border-slate-800 text-center text-slate-500">-</td>
                                        
                                        {/* Days Held */}
                                        <td className="p-2 border-r border-slate-800 text-center font-bold text-slate-300">{daysHeld}</td>

                                        {/* Strategy */}
                                        <td className="p-2 border-r border-slate-800 text-slate-500 italic text-[10px]">-</td>

                                        {/* EMAS (Group level) */}
                                        <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_8)}`}>
                                            {emas.ema_8 ? `$${emas.ema_8.toFixed(2)}` : '-'}
                                        </td>
                                        <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_21)}`}>
                                            {emas.ema_21 ? `$${emas.ema_21.toFixed(2)}` : '-'}
                                        </td>
                                        <td className={`p-2 text-center border-r border-slate-800 ${getEmaColor(currentPrice || 0, emas.ema_35)}`}>
                                            {emas.ema_35 ? `$${emas.ema_35.toFixed(2)}` : '-'}
                                        </td>
                                        <td className={`p-2 text-center ${getEmaColor(currentPrice || 0, emas.ema_200)}`}>
                                            {emas.ema_200 ? `$${emas.ema_200.toFixed(2)}` : '-'}
                                        </td>
                                        <td className="p-2 bg-slate-900"></td>
                                    </tr>"""

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "const isExpanded = expandedGroups[ticker];"
# Use a distinctive line from the DETAIL ROWS section as end marker to ensure we capture the whole row
end_marker = "{/* DETAIL ROWS */}"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Error: Could not find markers")
else:
    # Keep start marker, append new JSX, then keep end marker
    # Note: Logic in previous patch added isExpanded line, so we need to be careful not to duplicate or lose it.
    # The previous patch `new_logic` ENDED at `const emas = live.emas || {};`
    # It did NOT include `const isExpanded`.
    # Wait, looking at patch_app.py in Step 1423...
    # `new_logic` ENDED with `const emas = live.emas || {};`.
    # AND `end_marker` was `const isExpanded = expandedGroups[ticker];`.
    # So `isExpanded` line IS PRESERVED in `content[end_idx:]`.
    
    # So in this script, we search for `isExpanded` line.
    
    new_content = content[:start_idx + len(start_marker)] + "\n\n" + new_jsx + "\n\n                                    " + content[end_idx:]
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Success: JSX patched.")

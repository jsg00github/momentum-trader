
import os

target_file = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\app_v2.js"

# We want to replace the mapping callback for detail rows
new_detail_logic = """                                    {isExpanded && groupTrades.map(trade => {
                                        const live = liveData[trade.ticker] || {};
                                        const isClosed = trade.status === 'CLOSED';
                                        
                                        // Price Logic
                                        const currentPrice = isClosed ? trade.exit_price : (live.current_price || trade.entry_price);
                                        const displayPrice = isClosed ? trade.exit_price : (live.current_price || null);
                                        
                                        // Day/Date Logic
                                        const dayChange = live.day_change_pct || 0;
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
                                                <td className="p-2 text-right border-r border-slate-800 text-slate-400 font-mono text-[10px]">${trade.entry_price.toFixed(2)}</td>
                                                <td className="p-2 text-right border-r border-slate-800 text-slate-500 text-[10px]">{trade.shares}</td>
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
                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.target || '-'}</td>
                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.target2 || '-'}</td>
                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.target3 || '-'}</td>
                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 font-mono text-[10px]">{trade.stop_loss || '-'}</td>
                                                <td className="p-2 text-center border-r border-slate-800 text-slate-600 text-[10px]">{daysHeld}</td>
                                                <td className="p-2 border-r border-slate-800 text-slate-600 text-[10px] truncate max-w-[80px]">{trade.notes}</td>
                                                <td colSpan="5" className="p-2 text-center text-slate-600 text-[10px]">
                                                    <button onClick={() => handleDelete(trade.id)} className="hover:text-red-400">Delete</button>
                                                </td>
                                            </tr>
                                        );
                                    })}"""

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = "{/* DETAIL ROWS */}"
# We'll use the closing Fragment tag as the end marker for this block
end_marker = "</Fragment>"

start_idx = content.find(start_marker)
# Find the end marker AFTER the start marker
end_idx = content.find(end_marker, start_idx)

if start_idx == -1 or end_idx == -1:
    print("Error: Could not find markers")
else:
    # Keep start marker, append new logic, then put end marker back
    new_content = content[:start_idx + len(start_marker)] + "\n" + new_detail_logic + "\n                                " + content[end_idx:]
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Success: Detail rows patched.")

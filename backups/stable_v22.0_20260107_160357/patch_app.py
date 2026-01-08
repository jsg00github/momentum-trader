
import os

target_file = r"C:\Users\micro\.gemini\antigravity\playground\ancient-glenn\backend\static\app_v2.js"

new_logic = """                            // Aggregation Variables
                            let openShares = 0;
                            let openCost = 0;

                            let totalHistoryShares = 0;
                            let totalHistoryCost = 0;
                            let totalExitValue = 0;       // For Avg Exit Price
                            
                            let minEntryDate = null;      // Last Exit - First Entry = Days Held
                            let maxExitDate = null;

                            let totalPnl = 0;
                            let totalRealized = 0;

                            groupTrades.forEach(t => {
                                const isLong = t.direction === 'LONG';
                                
                                // Track Total History (Open + Closed)
                                totalHistoryShares += t.shares;
                                totalHistoryCost += t.entry_price * t.shares;

                                // Date Tracking for "Days Held"
                                if (!minEntryDate || new Date(t.entry_date) < new Date(minEntryDate)) {
                                    minEntryDate = t.entry_date;
                                }

                                if (t.status === 'OPEN') {
                                    openShares += t.shares;
                                    openCost += t.entry_price * t.shares;
                                    
                                    // Unrealized PnL of open position
                                    const currentPrice = live.current_price || t.entry_price;
                                    const upnl = (currentPrice - t.entry_price) * t.shares * (isLong ? 1 : -1);
                                    totalPnl += upnl;
                                } else {
                                    // Realized PnL from closed trades in this group (partials)
                                    if (t.pnl) totalPnl += t.pnl;
                                    
                                    // Exit Values for History Avg
                                    if (t.exit_price) totalExitValue += (t.exit_price * t.shares);
                                    if (t.exit_date) {
                                        if (!maxExitDate || new Date(t.exit_date) > new Date(maxExitDate)) {
                                            maxExitDate = t.exit_date;
                                        }
                                    }
                                }
                            });

                            // Determine what to show based on Tab
                            // Active Tab: Show OPEN details (Shares, Cost of Open).
                            // History Tab: Show CLOSED details (Avg Entry of campaign).
                            
                            const isHistory = activeTab === 'history';
                            
                            const displayShares = isHistory ? totalHistoryShares : openShares; 
                            const displayCost = isHistory ? totalHistoryCost : openCost; 
                            
                            // PPC: For Active, use Open Avg. For History, use Campaign Avg.
                            const avgPpc = isHistory 
                                ? (totalHistoryShares > 0 ? totalHistoryCost / totalHistoryShares : 0)
                                : (openShares > 0 ? openCost / openShares : 0);
                                
                            // Avg Exit Price (For History)
                            const avgExitPrice = (isHistory && totalHistoryShares > 0) ? totalExitValue / totalHistoryShares : 0;

                            // Days Held
                            let daysHeld = 0;
                            if (minEntryDate) {
                                const start = new Date(minEntryDate);
                                const end = isHistory && maxExitDate ? new Date(maxExitDate) : new Date(); // If active, today
                                const diffTime = Math.abs(end - start);
                                daysHeld = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
                            }

                            // % Trade: PnL / Invested. 
                            const returnBasis = isHistory ? totalHistoryCost : openCost;
                            const totalPnlPct = returnBasis > 0 ? (totalPnl / returnBasis) * 100 : 0;

                            const currentPrice = live.current_price || avgPpc;
                            const dayChange = live.day_change_pct || 0;
                            const displayPrice = isHistory ? avgExitPrice : currentPrice;
                            const displayChange = isHistory && maxExitDate ? maxExitDate : (dayChange ? `${dayChange > 0 ? '+' : ''}${dayChange.toFixed(2)}%` : '-');

                            const emas = live.emas || {};
"""

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Define start and end markers based on known unique lines
start_marker = "const live = liveData[ticker] || {};"
end_marker = "const isExpanded = expandedGroups[ticker];"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Error: Could not find markers")
    print(f"Start found: {start_idx != -1}")
    print(f"End found: {end_idx != -1}")
else:
    # Keep the start marker line, append new logic
    new_content = content[:start_idx + len(start_marker)] + "\n\n" + new_logic + "\n" + content[end_idx:]
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Success: File patched.")

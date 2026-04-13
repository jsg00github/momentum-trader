import React, { useState, useEffect } from 'react';

/**
 * MarketClock — dual-timezone clock showing NY and Buenos Aires market status
 * Updates every second. Shows OPEN/PRE/POST/CLOSED status.
 */
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

export default MarketClock;

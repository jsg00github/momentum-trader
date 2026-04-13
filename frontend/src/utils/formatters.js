/**
 * UI Formatters for trading data
 * Used across Journal, Scanner, DetailView, and Portfolio components.
 */

/**
 * Returns Tailwind classes for P&L display with gradient intensity.
 * Bigger winners = brighter green + bolder. Bigger losers = brighter red + bolder.
 */
export const getPnlColor = (pnlPct) => {
    if (pnlPct == null || isNaN(pnlPct)) return 'text-slate-400';
    if (pnlPct > 20) return 'text-emerald-400 font-black';
    if (pnlPct > 5) return 'text-green-400 font-bold';
    if (pnlPct > 0) return 'text-green-500';
    if (pnlPct > -5) return 'text-red-400';
    if (pnlPct > -15) return 'text-red-500 font-bold';
    return 'text-red-600 font-black';
};

/**
 * Returns Tailwind classes for trade status badges (OPEN, CLOSED, STOPPED)
 */
export const getStatusBadge = (status) => {
    const styles = {
        OPEN: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
        CLOSED: 'bg-slate-500/15 text-slate-400 border border-slate-500/30',
        STOPPED: 'bg-red-500/15 text-red-400 border border-red-500/30',
    };
    return styles[status] || styles.CLOSED;
};

/**
 * Format currency with proper sign
 */
export const formatCurrency = (value, decimals = 2) => {
    if (value == null || isNaN(value)) return '$0.00';
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`;
};

/**
 * Format percentage with sign
 */
export const formatPercent = (value, decimals = 2) => {
    if (value == null || isNaN(value)) return '0.00%';
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(decimals)}%`;
};

/**
 * Format large numbers with abbreviations (1.2K, 3.4M, etc.)
 */
export const formatCompact = (num) => {
    if (num == null || isNaN(num)) return '0';
    if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(1) + 'B';
    if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(1) + 'M';
    if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(1) + 'K';
    return num.toFixed(0);
};

/**
 * Relative time (e.g., "2 days ago")
 */
export const timeAgo = (dateStr) => {
    if (!dateStr) return '';
    const now = new Date();
    const date = new Date(dateStr);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

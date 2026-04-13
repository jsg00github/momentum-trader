/**
 * Trading Calendar Utilities
 * US Market Holidays and trading day calculations.
 */

// US Market Holidays (NYSE/NASDAQ) - Updated annually
// Format: 'YYYY-MM-DD'
export const US_MARKET_HOLIDAYS = new Set([
    // 2025
    '2025-01-01', '2025-01-20', '2025-02-17', '2025-04-18', '2025-05-26',
    '2025-06-19', '2025-07-04', '2025-09-01', '2025-11-27', '2025-12-25',
    // 2026
    '2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25',
    '2026-06-19', '2026-07-03', '2026-09-07', '2026-11-26', '2026-12-25',
]);

/**
 * Calculate trading days between two dates (excludes weekends and US holidays)
 * @param {Date|string} startDate - Start date
 * @param {Date|string} endDate - End date (defaults to today)
 * @returns {number} Number of trading days
 */
export function getTradingDaysBetween(startDate, endDate = new Date()) {
    const parseLocal = (d) => {
        if (typeof d === 'string' && d.match(/^\d{4}-\d{2}-\d{2}$/)) {
            const [y, m, day] = d.split('-').map(Number);
            return new Date(y, m - 1, day);
        }
        return new Date(d);
    };

    const start = parseLocal(startDate);
    const end = parseLocal(endDate);

    if (isNaN(start.getTime()) || start > end) return 0;

    let tradingDays = 0;
    const current = new Date(start);
    current.setHours(0, 0, 0, 0);
    end.setHours(0, 0, 0, 0);

    // If same date, it's Day 1
    if (current.getTime() === end.getTime()) return 1;

    while (current <= end) {
        const dayOfWeek = current.getDay();
        const dateStr = current.getFullYear() + '-' + String(current.getMonth() + 1).padStart(2, '0') + '-' + String(current.getDate()).padStart(2, '0');

        // Skip weekends (0 = Sunday, 6 = Saturday)
        // Skip US market holidays
        if (dayOfWeek !== 0 && dayOfWeek !== 6 && !US_MARKET_HOLIDAYS.has(dateStr)) {
            tradingDays++;
        }

        current.setDate(current.getDate() + 1);
    }

    // Safety check: if today is start date, ensure at least 1
    return tradingDays > 0 ? tradingDays : 1;
}

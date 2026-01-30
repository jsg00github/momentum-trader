
export const PatternType = {
    LONG_BASE_BREAKOUT: 'LONG_BASE_BREAKOUT',
    ONE_MONTH_BASE: 'ONE_MONTH_BASE',
    WEEKLY_BREAKOUT_VOL: 'WEEKLY_BREAKOUT_VOL',
    ASCENDING_TRIANGLE: 'ASCENDING_TRIANGLE',
    ELLIOTT_WAVE_3: 'ELLIOTT_WAVE_3',
    INVERSE_HEAD_AND_SHOULDERS: 'INVERSE_HEAD_AND_SHOULDERS',
    BULL_FLAG: 'BULL_FLAG',
    BREAKOUT_RETEST: 'BREAKOUT_RETEST',
    STRONG_BASE_BREAKOUT: 'STRONG_BASE_BREAKOUT'
};

// Yahoo Finance API via CORS Proxy to bypass browser restrictions
const CORS_PROXY = 'https://corsproxy.io/?';
const BASE_URL = 'https://query1.finance.yahoo.com/v8/finance/chart';

// Helper to fetch raw data
const fetchRawData = async (symbol, timeframe, customInterval, customRange) => {
    try {
        let interval = '1d';
        let range = '3mo';

        if (customInterval && customRange) {
            interval = customInterval;
            range = customRange;
        } else {
            switch (timeframe) {
                case '1D':
                    interval = '1d';
                    range = '1y';
                    break;
                case '1W':
                    interval = '1wk';
                    range = '2y';
                    break;
                case '1Y':
                    interval = '1mo';
                    range = '5y';
                    break;
            }
        }

        const targetUrl = `${BASE_URL}/${symbol}?interval=${interval}&range=${range}`;
        const url = `${CORS_PROXY}${encodeURIComponent(targetUrl)}`;

        const response = await fetch(url);
        if (!response.ok) return null;

        const json = await response.json();
        const result = json.chart.result?.[0];

        if (!result) return null;

        const timestamps = result.timestamp;
        const quotes = result.indicators.quote[0];

        if (!timestamps || !quotes) return null;

        const chartData = [];

        timestamps.forEach((time, index) => {
            if (quotes.open[index] === null) return;

            const date = new Date(time * 1000);
            const timeString = interval === '1h' || timeframe === '1D'
                ? date.toISOString()
                : date.toISOString().split('T')[0];

            chartData.push({
                time: timeString,
                open: quotes.open[index],
                high: quotes.high[index],
                low: quotes.low[index],
                close: quotes.close[index],
                volume: quotes.volume[index] || 0
            });
        });

        return chartData;
    } catch (e) {
        return null;
    }
};

// --- HELPER: Calculate DMI (DI+ / DI-) for a dataset ---
const calcLastDMI = (data, period = 14) => {
    if (data.length < period * 2) return { diPlus: 0, diMinus: 0 }; // Need some warmup data

    let tr14 = 0;
    let plusDm14 = 0;
    let minusDm14 = 0;

    const trs = [];
    const plusDms = [];
    const minusDms = [];

    // Calculate TR and DM for each bar
    for (let i = 1; i < data.length; i++) {
        const h = data[i].high;
        const l = data[i].low;
        const pc = data[i - 1].close;

        const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
        const upMove = h - data[i - 1].high;
        const downMove = data[i - 1].low - l;

        let plusDm = 0;
        let minusDm = 0;
        if (upMove > downMove && upMove > 0) plusDm = upMove;
        if (downMove > upMove && downMove > 0) minusDm = downMove;

        trs.push(tr);
        plusDms.push(plusDm);
        minusDms.push(minusDm);
    }

    // Initial SMA for first 14 periods
    for (let i = 0; i < period; i++) {
        tr14 += trs[i];
        plusDm14 += plusDms[i];
        minusDm14 += minusDms[i];
    }

    let lastDiPlus = 0;
    let lastDiMinus = 0;

    // Wilder's Smoothing for the rest
    for (let i = period; i < trs.length; i++) {
        tr14 = tr14 - (tr14 / period) + trs[i];
        plusDm14 = plusDm14 - (plusDm14 / period) + plusDms[i];
        minusDm14 = minusDm14 - (minusDm14 / period) + minusDms[i];

        lastDiPlus = 100 * (plusDm14 / tr14);
        lastDiMinus = 100 * (minusDm14 / tr14);
    }

    return { diPlus: lastDiPlus, diMinus: lastDiMinus };
};

// --- WEINSTEIN STAGE DETECTION ---
const detectWeinsteinStage = (weeklyData) => {
    if (weeklyData.length < 35) return 'Stage 1 (Base)'; // Not enough data

    const closes = weeklyData.map(d => d.close);
    // Weinstein uses 30-week SMA
    const sma30 = calcSMA(closes, 30);

    // We need SMA array to check slope
    const sma30Array = [];
    for (let i = 30; i < closes.length; i++) {
        const slice = closes.slice(i - 30, i);
        const sum = slice.reduce((a, b) => a + b, 0);
        sma30Array.push(sum / 30);
    }

    if (sma30Array.length < 5) return 'Stage 1 (Base)';

    const currentMA = sma30Array[sma30Array.length - 1];
    const prevMA = sma30Array[sma30Array.length - 5]; // Check slope over last 5 weeks
    const currentPrice = closes[closes.length - 1];

    const slope = (currentMA - prevMA) / prevMA; // % change of MA

    // Logic for Stages
    if (currentPrice > currentMA) {
        if (slope > 0.005) return 'Stage 2 (Uptrend)'; // Price above, MA rising
        if (Math.abs(slope) <= 0.005) return 'Stage 1 (Base)'; // Price above but MA flat
        return 'Stage 3 (Top)'; // Price above but MA falling (uncommon, usually volatile top)
    } else {
        if (slope < -0.005) return 'Stage 4 (Downtrend)'; // Price below, MA falling
        if (Math.abs(slope) <= 0.005) return 'Stage 1 (Base)'; // Price below but MA flat (early base)
        return 'Stage 3 (Top)'; // Price below but MA rising (rolling over)
    }
};

// --- MULTI-TIMEFRAME MOMENTUM CHECKER (DMI LOGIC) ---
const checkMultiTimeframeMomentum = async (symbol) => {
    try {
        // Fetch Daily Data (enough for DMI 14)
        const dailyData = await fetchRawData(symbol, '1D', '1d', '3mo');

        // Fetch Hourly Data
        const hourlyData = await fetchRawData(symbol, '1D', '1h', '25d');

        const result = { h1: false, h4: false, d1: false };

        // 1. D1 Analysis (DI+ > DI-)
        if (dailyData && dailyData.length > 20) {
            const d1Dmi = calcLastDMI(dailyData, 14);
            result.d1 = d1Dmi.diPlus > d1Dmi.diMinus;
        }

        if (hourlyData && hourlyData.length > 50) {
            // 2. H1 Analysis (DI+ > DI-)
            const h1Dmi = calcLastDMI(hourlyData, 14);
            result.h1 = h1Dmi.diPlus > h1Dmi.diMinus;

            // 3. H4 Analysis (Aggregate H1 -> H4)
            const h4Data = [];
            for (let i = 0; i < hourlyData.length; i += 4) {
                const chunk = hourlyData.slice(i, i + 4);
                if (chunk.length > 0) {
                    h4Data.push({
                        time: chunk[0].time,
                        open: chunk[0].open,
                        high: Math.max(...chunk.map(c => c.high)),
                        low: Math.min(...chunk.map(c => c.low)),
                        close: chunk[chunk.length - 1].close,
                        volume: chunk.reduce((sum, c) => sum + c.volume, 0)
                    });
                }
            }

            if (h4Data.length > 20) {
                const h4Dmi = calcLastDMI(h4Data, 14);
                result.h4 = h4Dmi.diPlus > h4Dmi.diMinus;
            }
        }

        return result;

    } catch (e) {
        console.warn("Error calculating momentum alignment", e);
        return { h1: false, h4: false, d1: false };
    }
};


// --- HELPER: Recency Window Calculation ---
const getRecencyWindow = (timeframe) => {
    switch (timeframe) {
        case '1D': return 10;
        case '1W': return 3;
        case '1Y': return 1;
    }
    return 10;
};

// --- Pattern Detection Logic ---

// ** DETECTOR: LONG BASE BREAKOUT (2 months / 8 weeks) **
const detectLongBaseBreakout = (weeklyData) => {
    if (weeklyData.length < 52) return false;

    // 1. Calculate 52-Week High
    const last52Weeks = weeklyData.slice(-52);
    const fiftyTwoWeekHigh = Math.max(...last52Weeks.map(d => d.high));
    const currentPrice = weeklyData[weeklyData.length - 1].close;

    // Check if within 15% of 52-week High
    if (currentPrice < fiftyTwoWeekHigh * 0.85) return false;

    // 2. Check Consolidation (2 Months ~ 8 Weeks)
    const baseLength = 8;
    const baseData = weeklyData.slice(-baseLength - 1, -1);
    if (baseData.length < baseLength) return false;

    const baseHigh = Math.max(...baseData.map(d => d.high));
    const baseLow = Math.min(...baseData.map(d => d.low));

    // Tightness: The base depth should not be too deep
    const baseDepth = (baseHigh - baseLow) / baseHigh;
    if (baseDepth > 0.30) return false;

    // 3. Check Rising Volume
    // Current volume > Avg Volume of base OR trend of volume is positive
    const baseAvgVol = baseData.reduce((acc, d) => acc + d.volume, 0) / baseData.length;
    const currentVol = weeklyData[weeklyData.length - 1].volume;

    if (currentPrice > baseHigh * 0.98 && currentVol > baseAvgVol * 1.2) {
        return true;
    }

    return false;
};

// ** DETECTOR: 1-MONTH BASE BREAKOUT (4-5 weeks) **
const detectOneMonthBase = (weeklyData) => {
    if (weeklyData.length < 52) return false;

    const current = weeklyData[weeklyData.length - 1];

    // 1. Must be very close to 52-Week Highs (High Tight Flag logic)
    const last52Weeks = weeklyData.slice(-52);
    const fiftyTwoWeekHigh = Math.max(...last52Weeks.map(d => d.high));

    if (current.close < fiftyTwoWeekHigh * 0.90) return false; // Strict 10% from highs

    // 2. Short Consolidation (4 Weeks)
    const baseLength = 4;
    const baseData = weeklyData.slice(-baseLength - 1, -1);
    if (baseData.length < baseLength) return false;

    const baseHigh = Math.max(...baseData.map(d => d.high));
    const baseLow = Math.min(...baseData.map(d => d.low));

    // High Tight Flag: Very tight volatility in the flag portion
    const baseDepth = (baseHigh - baseLow) / baseHigh;
    if (baseDepth > 0.15) return false; // Maximum 15% depth for a 1-month flag

    // 3. Breakout logic
    const isBreakingOut = current.close > baseHigh * 0.99;

    // 4. Prior Trend (Pole) Check: The month BEFORE the base must have been strong
    const poleData = weeklyData.slice(-baseLength - 5, -baseLength - 1);
    if (poleData.length > 0) {
        const poleStart = poleData[0].low;
        const poleEnd = poleData[poleData.length - 1].high;
        const poleGain = (poleEnd - poleStart) / poleStart;
        if (poleGain < 0.20) return false; // Needs 20% run before the 1-mo base
    }

    return isBreakingOut;
};

const detectAscendingTriangle = (data, currentPrice) => {
    if (data.length < 30) return false;

    // Look at last 50 bars
    const subset = data.slice(-50);

    // 1. Find Pivot Highs
    const highs = [];
    for (let i = 2; i < subset.length - 2; i++) {
        if (subset[i].high > subset[i - 1].high && subset[i].high > subset[i - 2].high &&
            subset[i].high > subset[i + 1].high && subset[i].high > subset[i + 2].high) {
            highs.push({ index: i, val: subset[i].high });
        }
    }

    // 2. Find Pivot Lows
    const lows = [];
    for (let i = 2; i < subset.length - 2; i++) {
        if (subset[i].low < subset[i - 1].low && subset[i].low < subset[i - 2].low &&
            subset[i].low < subset[i + 1].low && subset[i].low < subset[i + 2].low) {
            lows.push({ index: i, val: subset[i].low });
        }
    }

    if (highs.length < 2 || lows.length < 2) return false;

    // 3. Check for Flat Top (Resistance)
    const lastHighs = highs.slice(-3);
    if (lastHighs.length < 2) return false;

    const maxH = Math.max(...lastHighs.map(h => h.val));
    const minH = Math.min(...lastHighs.map(h => h.val));
    const diff = (maxH - minH) / minH;

    if (diff > 0.02) return false;

    const resistanceLevel = maxH;

    // 4. Check for Ascending Lows
    const lastLows = lows.slice(-3);
    if (lastLows.length < 2) return false;

    let isAscending = true;
    for (let i = 1; i < lastLows.length; i++) {
        if (lastLows[i].val <= lastLows[i - 1].val * 0.995) {
            isAscending = false;
            break;
        }
    }

    if (!isAscending) return false;

    // 5. INCIPIENT BREAKOUT CHECK
    if (currentPrice > resistanceLevel && currentPrice < resistanceLevel * 1.035) {
        return true;
    }

    return false;
};

const detectWeeklyVolBreakout = (weeklyData) => {
    if (weeklyData.length < 20) return false;

    const current = weeklyData[weeklyData.length - 1];
    const consolidationPeriod = 8;
    const startIdx = weeklyData.length - 1 - consolidationPeriod;
    const endIdx = weeklyData.length - 1;

    const contextData = weeklyData.slice(startIdx, endIdx);
    const highs = contextData.map(d => d.high);
    const lows = contextData.map(d => d.low);
    const consolidationHigh = Math.max(...highs);
    const consolidationLow = Math.min(...lows);

    const range = (consolidationHigh - consolidationLow) / consolidationLow;
    if (range > 0.25) return false;

    // Breakout check
    if (current.close < consolidationHigh * 1.005) return false;

    // INCIPIENT CHECK: If it already ran > 15% in one week, it's chased.
    const weeklyMove = (current.close - current.open) / current.open;
    if (weeklyMove > 0.15) return false;

    const avgVolume = contextData.reduce((acc, d) => acc + d.volume, 0) / contextData.length;

    // Volume must be high (1.5x)
    if (current.volume < avgVolume * 1.5) return false;

    if (weeklyMove < 0.02) return false;

    return true;
};

const detectElliottWave3 = (data, currentPrice, timeframe) => {
    if (data.length < 50) return false;

    const window = getRecencyWindow(timeframe);
    let p2Index = -1;
    let p2Price = Infinity;
    const scanStart = Math.max(0, data.length - 15);

    // Find Point 2 (Wave 2 Low)
    for (let i = scanStart; i < data.length - 1; i++) {
        if (data[i].low <= data[i - 1].low && data[i].low <= data[i + 1].low) {
            if (data[i].low < p2Price) {
                p2Price = data[i].low;
                p2Index = i;
            }
        }
    }

    if (p2Index === -1) return false;
    if (data.length - p2Index > window + 2) return false;

    // Find Point 1 (Wave 1 High)
    let p1Index = -1;
    let p1Price = -Infinity;
    for (let i = p2Index - 1; i > Math.max(0, p2Index - 30); i--) {
        if (data[i].high > p1Price) {
            p1Price = data[i].high;
            p1Index = i;
        }
    }

    if (p1Index === -1) return false;

    // Find Point 0 (Start)
    let p0Index = -1;
    let p0Price = Infinity;
    for (let i = p1Index - 1; i > Math.max(0, p1Index - 30); i--) {
        if (data[i].low < p0Price) {
            p0Price = data[i].low;
            p0Index = i;
        }
    }

    if (p0Index === -1) return false;

    if (p0Price >= p2Price) return false;
    if (p2Price >= p1Price) return false;

    const wave1Height = p1Price - p0Price;
    const wave2Depth = p1Price - p2Price;
    const ratio = wave2Depth / wave1Height;

    if (ratio < 0.3 || ratio > 0.85) return false;

    // INCIPIENT TRIGGER
    const bounceHeight = currentPrice - p2Price;
    const bounceRatio = bounceHeight / wave2Depth;

    if (bounceRatio < 0.03) return false;
    if (currentPrice > p1Price * 1.02) return false;

    return true;
};

const detectInverseHeadAndShoulders = (data, currentPrice, timeframe) => {
    if (data.length < 30) return false;
    const lookback = Math.min(data.length, 150);
    const subsetStartIndex = data.length - lookback;
    const subset = data.slice(subsetStartIndex);

    let headIndex = -1;
    let headLow = Infinity;
    for (let i = 0; i < subset.length; i++) {
        if (subset[i].low < headLow) {
            headLow = subset[i].low;
            headIndex = i;
        }
    }
    if (headIndex < 5 || headIndex > subset.length - 5) return false;

    let leftShoulderLow = Infinity;
    let leftShoulderIndex = -1;
    for (let i = 0; i < headIndex - 2; i++) {
        if (subset[i].low < leftShoulderLow) { leftShoulderLow = subset[i].low; leftShoulderIndex = i; }
    }
    let rightShoulderLow = Infinity;
    let rightShoulderIndex = -1;
    for (let i = headIndex + 2; i < subset.length - 1; i++) {
        if (subset[i].low < rightShoulderLow) { rightShoulderLow = subset[i].low; rightShoulderIndex = i; }
    }

    if (leftShoulderIndex === -1 || rightShoulderIndex === -1) return false;
    const isHeadLowest = headLow < leftShoulderLow && headLow < rightShoulderLow;

    let necklinePrice = 0;
    for (let i = leftShoulderIndex; i <= rightShoulderIndex; i++) {
        if (subset[i].high > necklinePrice) necklinePrice = subset[i].high;
    }

    // INCIPIENT CHECK
    const recencyWindow = getRecencyWindow(timeframe);
    let wasBelowRecently = false;
    const checkStart = Math.max(0, subset.length - recencyWindow - 2);
    for (let i = checkStart; i < subset.length; i++) {
        if (subset[i].close < necklinePrice * 0.99) { wasBelowRecently = true; break; }
    }

    const isBreakingOut = currentPrice > necklinePrice && currentPrice < necklinePrice * 1.03;

    return isHeadLowest && isBreakingOut && wasBelowRecently;
};

const detectBullFlag = (data, timeframe) => {
    if (data.length < 25) return false;
    const window = getRecencyWindow(timeframe);

    // Find Pole
    const searchEnd = data.length - window;
    const searchStart = Math.max(0, searchEnd - 30);
    let poleTipPrice = -Infinity;
    let poleTipIndex = -1;

    for (let i = searchStart; i < searchEnd; i++) {
        if (data[i].high > poleTipPrice) { poleTipPrice = data[i].high; poleTipIndex = i; }
    }

    if (poleTipIndex === -1) return false;

    const poleBaseIndex = Math.max(0, poleTipIndex - 5);
    if (poleTipPrice < data[poleBaseIndex].low * 1.04) return false;

    // Flag Consolidation
    for (let i = poleTipIndex + 1; i < data.length - 2; i++) {
        if (data[i].close < poleTipPrice * 0.85) return false;
    }

    // INCIPIENT CHECK
    let breakoutIndex = -1;
    for (let i = data.length - 3; i < data.length; i++) {
        if (data[i].close > poleTipPrice * 0.99) {
            breakoutIndex = i;
            break;
        }
    }

    return breakoutIndex !== -1;
};

const detectBreakoutRetest = (data, timeframe) => {
    if (data.length < 50) return false;
    const window = getRecencyWindow(timeframe);

    const buffer = 5;
    const analysisEnd = data.length - window - buffer;
    const analysisStart = Math.max(0, analysisEnd - 120);

    const pastData = data.slice(analysisStart, analysisEnd);
    if (pastData.length === 0) return false;

    const resistance = Math.max(...pastData.map(d => d.high));

    let breakIndex = -1;
    const recentData = data.slice(data.length - window - buffer);
    for (let i = 0; i < recentData.length; i++) {
        if (recentData[i].close > resistance * 1.01) { breakIndex = i; break; }
    }

    if (breakIndex === -1) return false;

    const currentPrice = data[data.length - 1].close;
    // RETEST ZONE
    const isRetesting = (currentPrice >= resistance * 0.98) && (currentPrice <= resistance * 1.03);

    return isRetesting;
};

export const fetchRealStockData = async (symbol, timeframe) => {
    try {
        const chartData = await fetchRawData(symbol, timeframe);
        if (!chartData || chartData.length === 0) return null;

        let weeklyData = [];
        // We always need Weekly data for Weinstein analysis, even if timeframe is Daily
        if (timeframe === '1W') {
            weeklyData = chartData;
        } else {
            const wData = await fetchRawData(symbol, '1W');
            weeklyData = wData || chartData; // Fallback if weekly fails
        }

        const currentPrice = chartData[chartData.length - 1].close;
        const prevPrice = chartData[chartData.length - 2].close;
        const change = ((currentPrice - prevPrice) / prevPrice) * 100;

        let detectedPattern = null;
        let baseScore = 50;

        const wTech = calculateCustomIndicators(weeklyData);

        let isCompressed = false;
        if (weeklyData.length >= 15) {
            // VCP Logic...
            const offset = 1;
            let recentVolSum = 0;
            const recentPeriod = 4;
            for (let i = weeklyData.length - offset - recentPeriod; i < weeklyData.length - offset; i++) {
                const d = weeklyData[i];
                recentVolSum += (d.high - d.low) / d.close;
            }
            const recentVol = recentVolSum / recentPeriod;
            let pastVolSum = 0;
            const pastPeriod = 8;
            for (let i = weeklyData.length - offset - recentPeriod - pastPeriod; i < weeklyData.length - offset - recentPeriod; i++) {
                const d = weeklyData[i];
                pastVolSum += (d.high - d.low) / d.close;
            }
            const pastVol = pastVolSum / pastPeriod;
            isCompressed = (recentVol < pastVol * 0.85) || (recentVol < 0.035);
        }

        // --- EXECUTE DETECTORS ---

        // Note: We check 2-month (Long Base) first as it is more stable.
        if (detectLongBaseBreakout(weeklyData)) {
            detectedPattern = PatternType.LONG_BASE_BREAKOUT;
            baseScore = 98;
        }
        // Then we check 1-month (High Tight Flag)
        else if (detectOneMonthBase(weeklyData)) {
            detectedPattern = PatternType.ONE_MONTH_BASE;
            baseScore = 96;
        }
        else if (detectWeeklyVolBreakout(weeklyData)) {
            detectedPattern = PatternType.WEEKLY_BREAKOUT_VOL;
            baseScore = 95;
        }
        else if (detectAscendingTriangle(chartData, currentPrice)) {
            detectedPattern = PatternType.ASCENDING_TRIANGLE;
            baseScore = 92;
        }
        else if (detectElliottWave3(chartData, currentPrice, timeframe)) {
            detectedPattern = PatternType.ELLIOTT_WAVE_3;
            baseScore = 90;
        }
        else if (detectInverseHeadAndShoulders(weeklyData, currentPrice, timeframe === '1W' ? '1W' : '1D')) {
            detectedPattern = PatternType.INVERSE_HEAD_AND_SHOULDERS;
            baseScore = 85;
        }
        else if (detectBullFlag(chartData, timeframe)) {
            detectedPattern = PatternType.BULL_FLAG;
            baseScore = 80;
        }
        else if (detectBreakoutRetest(chartData, timeframe)) {
            detectedPattern = PatternType.BREAKOUT_RETEST;
            baseScore = 75;
        }
        else {
            const isStrongBase =
                (wTech.diPlus > wTech.diMinus && wTech.diPlus > wTech.adx) &&
                (wTech.smi > 0) &&
                (wTech.macd > 0) &&
                (wTech.rsiSma3 > wTech.rsiSma14) &&
                isCompressed;

            if (isStrongBase) {
                detectedPattern = PatternType.STRONG_BASE_BREAKOUT;
                baseScore = 70;
            }
        }

        if (!detectedPattern) return null;

        let score = calculateMomentumScore(chartData);
        score = Math.floor((score + baseScore) / 2);
        if (score > 99) score = 99;

        // --- WEINSTEIN & 52-WEEK ANALYSIS ---
        const weinsteinStage = detectWeinsteinStage(weeklyData);

        // Calculate 52-Week High/Low (Using Weekly Data covers last year efficiently)
        const last52Weeks = weeklyData.slice(-52);
        const fiftyTwoWeekHigh = Math.max(...last52Weeks.map(d => d.high));
        const fiftyTwoWeekLow = Math.min(...last52Weeks.map(d => d.low));

        // Proximity Percentage (0 = Low, 100 = High)
        let fiftyTwoWeekProximity = 0;
        if (fiftyTwoWeekHigh !== fiftyTwoWeekLow) {
            fiftyTwoWeekProximity = ((currentPrice - fiftyTwoWeekLow) / (fiftyTwoWeekHigh - fiftyTwoWeekLow)) * 100;
        }

        // --- MOMENTUM ALIGNMENT CHECK ---
        const momentumAlignment = await checkMultiTimeframeMomentum(symbol);

        // --- VOLUME TRACKING (RVOL) ---
        // Calculate avg volume over last 20 bars
        let avgVolume = 0;
        const volPeriod = 20;
        if (chartData.length > volPeriod) {
            const last20Vols = chartData.slice(-volPeriod).map(d => d.volume);
            avgVolume = last20Vols.reduce((a, b) => a + b, 0) / volPeriod;
        } else {
            avgVolume = chartData.map(d => d.volume).reduce((a, b) => a + b, 0) / chartData.length;
        }

        const currentVolume = chartData[chartData.length - 1].volume;
        const rvol = avgVolume > 0 ? Number((currentVolume / avgVolume).toFixed(2)) : 0;


        return {
            symbol: symbol.toUpperCase(),
            price: currentPrice,
            change: parseFloat(change.toFixed(2)),
            pattern: detectedPattern,
            score: score,
            chartData: chartData,
            momentumAlignment,
            weinsteinStage,
            fiftyTwoWeekHigh,
            fiftyTwoWeekLow,
            fiftyTwoWeekProximity,
            rvol,      // NEW
            avgVolume  // NEW
        };

    } catch (error) {
        console.error(`Failed to fetch Yahoo data for ${symbol}:`, error);
        return null;
    }
};

// --- TECHNICAL ANALYSIS HELPERS ---

const calculateMomentumScore = (data) => {
    if (data.length < 14) return 50;
    let gains = 0;
    let losses = 0;
    for (let i = data.length - 14; i < data.length; i++) {
        const change = data[i].close - data[i - 1].close;
        if (change > 0) gains += change;
        else losses -= change;
    }
    if (losses === 0) return 100;
    const rs = gains / losses;
    return Math.floor(100 - (100 / (1 + rs)));
};

// Helper: Calculate EMA
const calcEMA = (values, period) => {
    const k = 2 / (period + 1);
    const emaArray = [values[0]];
    for (let i = 1; i < values.length; i++) {
        const val = values[i] !== undefined ? values[i] : values[i - 1];
        const prev = emaArray[i - 1] !== undefined ? emaArray[i - 1] : val;
        emaArray.push(val * k + prev * (1 - k));
    }
    return emaArray;
};

// Helper: Calculate RSI Array
const calcRSIArray = (closes, period = 14) => {
    const rsiArray = [];
    let gains = 0;
    let losses = 0;

    // First average
    for (let i = 1; i <= period; i++) {
        const change = closes[i] - closes[i - 1];
        if (change > 0) gains += change;
        else losses -= Math.abs(change);
    }
    let avgGain = gains / period;
    let avgLoss = losses / period;

    rsiArray.push(100 - (100 / (1 + avgGain / (avgLoss === 0 ? 1 : avgLoss))));

    // Subsequent values (Wilder's Smoothing)
    for (let i = period + 1; i < closes.length; i++) {
        const change = closes[i] - closes[i - 1];
        const gain = change > 0 ? change : 0;
        const loss = change < 0 ? Math.abs(change) : 0;

        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;

        rsiArray.push(100 - (100 / (1 + avgGain / (avgLoss === 0 ? 1 : avgLoss))));
    }
    // Pad the beginning to match length
    const padding = new Array(period).fill(50);
    return [...padding, ...rsiArray];
};

// Helper: Simple Moving Average of an Array
const calcSMA = (values, period) => {
    if (values.length < period) return 0;
    const slice = values.slice(-period);
    const sum = slice.reduce((a, b) => a + b, 0);
    return sum / period;
};

const calculateCustomIndicators = (data) => {
    // Need sufficient data for Weekly calculations (at least ~30 bars for ADX/SMI stabilization)
    if (data.length < 30) return { adx: 0, diPlus: 0, diMinus: 0, smi: 0, macd: 0, rsiSma3: 0, rsiSma14: 0 };

    const highs = data.map(d => d.high);
    const lows = data.map(d => d.low);
    const closes = data.map(d => d.close);

    // 1. RSI (14) -> SMA(3) vs SMA(14)
    // We calculate RSI first, then take SMAs of the RSI values
    const rsiValues = calcRSIArray(closes, 14);
    // Recent RSI values
    const rsiSma3 = calcSMA(rsiValues, 3);
    const rsiSma14 = calcSMA(rsiValues, 14);

    // 2. MACD (12, 26, 9)
    const ema12 = calcEMA(closes, 12);
    const ema26 = calcEMA(closes, 26);
    const macdLine = (ema12[ema12.length - 1] || 0) - (ema26[ema26.length - 1] || 0);

    // 3. SMI (Stochastic Momentum Index)
    const len = 10;
    const smooth1 = 3;
    const smooth2 = 3;

    const diff = [];
    const hl = [];

    for (let i = len; i < data.length; i++) {
        const sliceH = highs.slice(i - len + 1, i + 1);
        const sliceL = lows.slice(i - len + 1, i + 1);
        const hh = Math.max(...sliceH);
        const ll = Math.min(...sliceL);
        const midpoint = (hh + ll) / 2;

        diff.push(closes[i] - midpoint);
        hl.push(hh - ll);
    }

    const emaDiff1 = calcEMA(diff, smooth1);
    const emaDiff2 = calcEMA(emaDiff1, smooth2);
    const emaHL1 = calcEMA(hl, smooth1);
    const emaHL2 = calcEMA(emaHL1, smooth2);

    const lastDiff = emaDiff2[emaDiff2.length - 1] || 0;
    const lastHL = emaHL2[emaHL2.length - 1] || 1;

    const smi = 100 * (lastDiff / (0.5 * lastHL));


    // 4. DMI / ADX (14)
    // Reuse DMI logic for full object
    const dmi = calcLastDMI(data, 14);

    // For full indicators used in pattern logic, we need more than just last DMI
    // So keeping original logic here or approximating.
    // The original logic computed full arrays for ADX.
    // ...
    let tr14 = 0;
    let plusDm14 = 0;
    let minusDm14 = 0;

    const trs = [];
    const plusDms = [];
    const minusDms = [];

    for (let i = 1; i < data.length; i++) {
        const h = highs[i];
        const l = lows[i];
        const pc = closes[i - 1];

        const tr = Math.max(h - l, Math.abs(h - pc), Math.abs(l - pc));
        const upMove = h - highs[i - 1];
        const downMove = lows[i - 1] - l;

        let plusDm = 0;
        let minusDm = 0;
        if (upMove > downMove && upMove > 0) plusDm = upMove;
        if (downMove > upMove && downMove > 0) minusDm = downMove;

        trs.push(tr);
        plusDms.push(plusDm);
        minusDms.push(minusDm);
    }

    for (let i = 0; i < 14; i++) {
        tr14 += trs[i] || 0;
        plusDm14 += plusDms[i] || 0;
        minusDm14 += minusDms[i] || 0;
    }

    let prevAdx = 0;
    let dxSum = 0;
    let lastDiPlus = 0;
    let lastDiMinus = 0;

    for (let i = 14; i < trs.length; i++) {
        tr14 = tr14 - (tr14 / 14) + trs[i];
        plusDm14 = plusDm14 - (plusDm14 / 14) + plusDms[i];
        minusDm14 = minusDm14 - (minusDm14 / 14) + minusDms[i];

        const diPlus = 100 * (plusDm14 / tr14);
        const diMinus = 100 * (minusDm14 / tr14);

        const sum = diPlus + diMinus;
        const dx = sum === 0 ? 0 : 100 * (Math.abs(diPlus - diMinus) / sum);

        if (i === 27) {
            prevAdx = dxSum / 14;
        } else if (i > 27) {
            prevAdx = ((prevAdx * 13) + dx) / 14;
        } else {
            dxSum += dx;
        }

        lastDiPlus = diPlus;
        lastDiMinus = diMinus;
    }

    return {
        adx: prevAdx,
        diPlus: lastDiPlus,
        diMinus: lastDiMinus,
        smi: smi,
        macd: macdLine,
        rsiSma3: rsiSma3,
        rsiSma14: rsiSma14
    };
};

const DEFAULT_TICKERS = ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMD', 'GOOGL', 'AMZN', 'META', 'NFLX', 'COIN', 'MSTR'];

export const scanMarket = async (onProgress) => {
    const results = [];
    const tickers = DEFAULT_TICKERS;

    for (const ticker of tickers) {
        if (onProgress) onProgress(`Scanning ${ticker}...`);
        try {
            const data = await fetchRealStockData(ticker, '1D');
            if (data) {
                if (!data.signal) {
                    if (data.score >= 80) data.signal = 'BUY';
                    else if (data.score <= 30) data.signal = 'SELL';
                    else data.signal = 'NEUTRAL';
                }
                if (!data.setup) data.setup = data.pattern || '-';
                results.push(data);
            }
        } catch (e) {
            console.error(e);
        }
    }
    return results.sort((a, b) => b.score - a.score);
};

export const scannerService = {
    scanMarket,
    fetchRealStockData
};


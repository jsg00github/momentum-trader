"""
Market Regime Detection via Hidden Markov Models (HMM)

Statistically-driven regime detection using Gaussian HMM from hmmlearn.
Complements the rule-based market_regime.py with a latent-state approach
that captures shifts in return, range, and volatility structure.

Features used:
  - Log-return:            np.log(Close / Close_prev)
  - Normalised daily range: (High - Low) / Close
  - Realised volatility:    rolling std of log-returns

All features are z-scored (StandardScaler) before training so the
Gaussian emissions are well-conditioned.

Anti-flickering: the transition matrix is initialised with a strong
diagonal prior (default 0.95) to penalise excessive state switching.

Usage:
    from market_regime_hmm import MarketRegimeHMM

    hmm = MarketRegimeHMM(n_regimes=4, vol_window=5)
    hmm.fit(df)                   # df must have OHLCV columns
    decoded = hmm.decode()        # df + 'regime' column
    summary  = hmm.get_regime_summary()
    fig      = hmm.plot_regimes() # matplotlib Figure
"""

import math
import warnings
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Suppress ConvergenceWarning during EM iterations
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    from hmmlearn.hmm import GaussianHMM
except ImportError:
    raise ImportError(
        "hmmlearn is required.  Install it with:  pip install hmmlearn"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_for_json(obj):
    """Recursively convert NaN / Inf / numpy types to JSON-safe values."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return _sanitize_for_json(obj.tolist())
    return obj


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------

class MarketRegimeHMM:
    """
    Hidden Markov Model based market-regime detector.

    Parameters
    ----------
    n_regimes : int, default 4
        Number of latent states (must be between 3 and 7).
    vol_window : int, default 5
        Rolling window for realised-volatility feature (5-10 recommended).
    diag_prior : float, default 0.95
        Diagonal bias of the initial transition matrix.  Higher values
        produce stickier regimes (less flickering).
    n_iter : int, default 200
        Maximum EM iterations for model fitting.
    random_state : int, default 42
        Seed for reproducibility.
    """

    # Regime colour palette (up to 7 states)
    REGIME_COLORS = [
        "#D32F2F",   # 0 – deep red    (most bearish)
        "#F57C00",   # 1 – orange
        "#FBC02D",   # 2 – amber
        "#66BB6A",   # 3 – light green
        "#2E7D32",   # 4 – dark green   (most bullish)
        "#1565C0",   # 5 – blue
        "#6A1B9A",   # 6 – purple
    ]

    REGIME_LABELS_ES = {
        0: "Bajista fuerte",
        1: "Bajista",
        2: "Alta volatilidad",
        3: "Neutral",
        4: "Alcista",
        5: "Alcista fuerte",
        6: "Rally",
    }

    def __init__(
        self,
        n_regimes: int = 4,
        vol_window: int = 5,
        diag_prior: float = 0.95,
        n_iter: int = 200,
        random_state: int = 42,
    ):
        if not 3 <= n_regimes <= 7:
            raise ValueError("n_regimes must be between 3 and 7.")
        if not 5 <= vol_window <= 10:
            raise ValueError("vol_window must be between 5 and 10.")

        self.n_regimes = n_regimes
        self.vol_window = vol_window
        self.diag_prior = diag_prior
        self.n_iter = n_iter
        self.random_state = random_state

        # Internal state set after fit()
        self._model: Optional[GaussianHMM] = None
        self._scaler: Optional[StandardScaler] = None
        self._df_fitted: Optional[pd.DataFrame] = None
        self._states: Optional[np.ndarray] = None
        self._state_order: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _build_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray]:
        """
        Build feature matrix from OHLCV DataFrame.

        Returns
        -------
        df_clean : pd.DataFrame
            Input df without the first `vol_window` rows (NaN warm-up).
        X : np.ndarray, shape (n_samples, 3)
            Normalised feature matrix.
        """
        ohlcv = df.copy()

        # Flatten MultiIndex columns if present (yfinance quirk)
        if isinstance(ohlcv.columns, pd.MultiIndex):
            ohlcv.columns = ohlcv.columns.get_level_values(0)

        required = {"Close", "High", "Low"}
        if not required.issubset(set(ohlcv.columns)):
            raise ValueError(
                f"DataFrame must contain columns {required}. "
                f"Found: {set(ohlcv.columns)}"
            )

        # Drop non-trading days (weekends/holidays) that appear as NaN
        ohlcv = ohlcv.dropna(subset=["Close", "High", "Low"])

        # 1. Log-return
        ohlcv["log_return"] = np.log(ohlcv["Close"] / ohlcv["Close"].shift(1))

        # 2. Normalised daily range  (High - Low) / Close
        ohlcv["daily_range"] = (ohlcv["High"] - ohlcv["Low"]) / ohlcv["Close"]

        # 3. Realised volatility (rolling std of log-returns)
        ohlcv["realized_vol"] = ohlcv["log_return"].rolling(
            window=self.vol_window
        ).std()

        # Drop warm-up NaN rows (first row for log_return, first vol_window for vol)
        ohlcv = ohlcv.dropna(subset=["log_return", "daily_range", "realized_vol"])

        feature_cols = ["log_return", "daily_range", "realized_vol"]
        X_raw = ohlcv[feature_cols].values

        # StandardScaler normalisation
        self._scaler = StandardScaler()
        X = self._scaler.fit_transform(X_raw)

        return ohlcv, X

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> "MarketRegimeHMM":
        """
        Train the Gaussian HMM on the provided OHLCV DataFrame.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain at least Close, High, Low columns.

        Returns
        -------
        self
        """
        df_clean, X = self._build_features(df)

        if len(X) < self.n_regimes * 10:
            raise ValueError(
                f"Not enough data: {len(X)} rows after warm-up, need at "
                f"least {self.n_regimes * 10}."
            )

        # Build strong-diagonal transition matrix prior
        transmat_prior = np.full(
            (self.n_regimes, self.n_regimes),
            (1.0 - self.diag_prior) / (self.n_regimes - 1),
        )
        np.fill_diagonal(transmat_prior, self.diag_prior)

        model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type="full",
            n_iter=self.n_iter,
            random_state=self.random_state,
            params="stmc",
            init_params="smc",  # exclude 't' so our transmat_ prior is kept
        )
        # Set the transition-matrix prior (strong diagonal = sticky states)
        model.transmat_ = transmat_prior

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model.fit(X)

        # Viterbi decode
        raw_states = model.predict(X)

        # Order states by mean log-return (0 = most bearish, N = most bullish)
        mean_returns = np.array(
            [
                df_clean["log_return"].values[raw_states == s].mean()
                for s in range(self.n_regimes)
            ]
        )
        state_order = np.argsort(mean_returns)  # ascending
        remap = np.empty_like(state_order)
        for new_id, old_id in enumerate(state_order):
            remap[old_id] = new_id

        ordered_states = remap[raw_states]

        # Store results
        self._model = model
        self._df_fitted = df_clean.copy()
        self._df_fitted["regime"] = ordered_states
        self._states = ordered_states
        self._state_order = state_order

        return self

    # ------------------------------------------------------------------
    # Decode
    # ------------------------------------------------------------------

    def decode(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Return a DataFrame with a ``regime`` column.

        If *df* is ``None``, returns the training data with regimes.
        If a new *df* is provided, transforms and decodes it using the
        already-fitted model.
        """
        if self._model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        if df is None:
            return self._df_fitted.copy()

        # Decode new data
        df_clean, X = self._build_features(df)

        # Re-use fitted scaler for transform (not fit_transform)
        X = self._scaler.transform(
            df_clean[["log_return", "daily_range", "realized_vol"]].values
        )
        raw_states = self._model.predict(X)

        # Apply same state reordering
        remap = np.empty_like(self._state_order)
        for new_id, old_id in enumerate(self._state_order):
            remap[old_id] = new_id
        df_clean["regime"] = remap[raw_states]

        return df_clean

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    def get_regime_summary(self) -> Dict:
        """
        Return per-regime statistics (JSON-serialisable).

        Returns
        -------
        dict with keys:
            n_regimes, current_regime, regimes (list of per-state dicts),
            transition_matrix
        """
        if self._model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        df = self._df_fitted
        regimes_info = []

        for regime_id in range(self.n_regimes):
            mask = df["regime"] == regime_id
            subset = df.loc[mask]

            label_key = self._label_key(regime_id)

            regimes_info.append(
                {
                    "regime_id": regime_id,
                    "label": label_key,
                    "color": self.REGIME_COLORS[regime_id],
                    "n_days": int(mask.sum()),
                    "pct_days": round(mask.sum() / len(df) * 100, 1),
                    "mean_daily_return_pct": round(
                        float(subset["log_return"].mean()) * 100, 4
                    ),
                    "annualised_return_pct": round(
                        float(subset["log_return"].mean()) * 252 * 100, 2
                    ),
                    "mean_daily_vol_pct": round(
                        float(subset["realized_vol"].mean()) * 100, 4
                    ),
                    "annualised_vol_pct": round(
                        float(subset["realized_vol"].mean()) * np.sqrt(252) * 100, 2
                    ),
                    "mean_daily_range_pct": round(
                        float(subset["daily_range"].mean()) * 100, 4
                    ),
                }
            )

        # Re-order transition matrix rows/cols to match ordered states
        ordered_transmat = self._model.transmat_[self._state_order][
            :, self._state_order
        ]

        current_regime = int(df["regime"].iloc[-1])

        return _sanitize_for_json(
            {
                "n_regimes": self.n_regimes,
                "current_regime": current_regime,
                "current_label": self._label_key(current_regime),
                "regimes": regimes_info,
                "transition_matrix": ordered_transmat.tolist(),
            }
        )

    def _label_key(self, regime_id: int) -> str:
        """Pick a human-friendly label based on n_regimes and regime_id."""
        if self.n_regimes <= 4:
            labels = ["Bear", "High Volatility", "Neutral", "Bull"]
        elif self.n_regimes == 5:
            labels = ["Strong Bear", "Bear", "Neutral", "Bull", "Strong Bull"]
        elif self.n_regimes == 6:
            labels = [
                "Strong Bear", "Bear", "High Vol",
                "Neutral", "Bull", "Strong Bull",
            ]
        else:
            labels = [
                "Strong Bear", "Bear", "Weak Bear", "Neutral",
                "Weak Bull", "Bull", "Strong Bull",
            ]
        return labels[regime_id] if regime_id < len(labels) else f"Regime {regime_id}"

    # ------------------------------------------------------------------
    # Visualisation
    # ------------------------------------------------------------------

    def plot_regimes(
        self,
        df: Optional[pd.DataFrame] = None,
        title: str = "Market Regime Detection (HMM)",
        figsize: Tuple[int, int] = (16, 7),
        price_col: str = "Close",
        save_path: Optional[str] = None,
    ):
        """
        Plot price with colour-shaded regime bands.

        Parameters
        ----------
        df : pd.DataFrame, optional
            If None, uses the fitted data.
        title : str
            Chart title.
        figsize : tuple
            Figure size (width, height).
        price_col : str
            Column name for price line (default 'Close').
        save_path : str, optional
            If provided, saves the figure to this path.

        Returns
        -------
        matplotlib.figure.Figure
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates
        except ImportError:
            raise ImportError(
                "matplotlib is required for plotting.  "
                "Install with: pip install matplotlib"
            )

        if self._model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        plot_df = self.decode(df) if df is not None else self._df_fitted.copy()

        fig, ax = plt.subplots(figsize=figsize, facecolor="#1a1a2e")
        ax.set_facecolor("#1a1a2e")

        # Price line
        dates = plot_df.index
        prices = plot_df[price_col].values
        ax.plot(dates, prices, color="#e0e0e0", linewidth=1.2, zorder=3)

        # Shade regime bands
        regimes = plot_df["regime"].values
        for i in range(len(regimes)):
            color = self.REGIME_COLORS[regimes[i]]
            if i < len(regimes) - 1:
                ax.axvspan(
                    dates[i],
                    dates[i + 1],
                    alpha=0.30,
                    color=color,
                    linewidth=0,
                    zorder=1,
                )

        # Legend entries
        from matplotlib.patches import Patch

        legend_handles = [
            Patch(
                facecolor=self.REGIME_COLORS[r],
                alpha=0.45,
                label=f"Regime {r} — {self._label_key(r)}",
            )
            for r in range(self.n_regimes)
        ]
        ax.legend(
            handles=legend_handles,
            loc="upper left",
            fontsize=9,
            framealpha=0.7,
            facecolor="#16213e",
            edgecolor="#0f3460",
            labelcolor="#e0e0e0",
        )

        # Formatting
        ax.set_title(
            f"{title}  ({self.n_regimes} States)",
            fontsize=14,
            fontweight="bold",
            color="#e0e0e0",
            pad=12,
        )
        ax.set_xlabel("Date", fontsize=11, color="#aaaaaa")
        ax.set_ylabel("Price (USD)", fontsize=11, color="#aaaaaa")
        ax.tick_params(colors="#aaaaaa")
        ax.grid(axis="y", color="#333366", alpha=0.3, linestyle="--")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        fig.autofmt_xdate(rotation=30)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
            print(f"✓ Plot saved to {save_path}")

        return fig


# ---------------------------------------------------------------------------
# Convenience function for quick analysis
# ---------------------------------------------------------------------------

def analyze_regime(
    ticker: str = "SPY",
    n_regimes: int = 4,
    vol_window: int = 5,
    period: str = "1y",
) -> Dict:
    """
    One-call convenience: download data, fit HMM, return summary.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol.
    n_regimes : int
        Number of HMM states (3–7).
    vol_window : int
        Realised-vol rolling window.
    period : str
        yfinance period string (e.g. '1y', '2y').

    Returns
    -------
    dict   (JSON-serialisable regime summary)
    """
    try:
        import market_data

        df = market_data.safe_yf_download(
            ticker, period=period, interval="1d", auto_adjust=False
        )
    except ImportError:
        import yfinance as yf

        df = yf.download(ticker, period=period, interval="1d", auto_adjust=False)

    if df is None or df.empty:
        return {"error": f"No data available for {ticker}"}

    hmm = MarketRegimeHMM(n_regimes=n_regimes, vol_window=vol_window)
    hmm.fit(df)
    summary = hmm.get_regime_summary()
    summary["ticker"] = ticker
    summary["period"] = period
    return summary

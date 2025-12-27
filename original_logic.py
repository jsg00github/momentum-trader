# Screener:
#  - Suba > 90% en los últimos ~3 meses
#  - Performance del último mes entre 0% y -25% (lateral / corrección suave)
#  - Suba > 10% en la última semana
#  - Devuelve mínimo y máximo del rally de 3 meses
#
# Universo: tickers del JSON de la SEC
# URL universo: https://www.sec.gov/files/company_tickers.json
#
# Requisitos previos en Colab:
#   !pip install yfinance pandas numpy requests

import pandas as pd
import numpy as np
import yfinance as yf
import requests
import logging

# ==============================
# 1) OBTENER TICKERS DESDE LA SEC
# ==============================

def get_sec_tickers():
    """
    Descarga el JSON de la SEC con company_tickers y devuelve:
      - lista de tickers (strings)
      - DataFrame con las filas completas (cik_str, ticker, title)
    JSON típico:
        {
          "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
          "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
          ...
        }
    """
    url = "https://www.sec.gov/files/company_tickers.json"

    # La SEC recomienda incluir un User-Agent identificable
    headers = {
        "User-Agent": "Javier Screener 3M Rally (contacto: tu_email@ejemplo.com)"
    }

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    data = resp.json()  # dict: clave -> {cik_str, ticker, title}

    records = []
    tickers = set()
    for _, v in data.items():
        ticker = v.get("ticker")
        if ticker:
            tickers.add(ticker)
            records.append(v)

    tickers_list = sorted(tickers)
    df_sec = pd.DataFrame.from_records(records)

    return tickers_list, df_sec


#tickers_sec, df_sec = get_sec_tickers()
#print(f"Tickers obtenidos desde SEC (company_tickers.json): {len(tickers_sec)}")
#print("Ejemplos:", tickers_sec[:20])


# ==============================
# 2) PARÁMETROS DEL SCREENER
# ==============================

period = "6mo"            # bajamos 6 meses diarios para tener margen
interval = "1d"           # timeframe diario

# Ventanas (en barras de trading)
THREEM_BARS = 63   # ~3 meses
MONTH_BARS  = 21   # ~1 mes
WEEK_BARS   = 5    # ~1 semana

# Condiciones de performance
MIN_RET_3M      = 0.90    # > +90% en 3 meses
MIN_RET_1W      = 0.10    # > +10% en la semana
MIN_RET_1M      = -0.25   # -25% mínimo...
MAX_RET_1M      = 0.0     # ...hasta 0% (lateral / corrección suave)

# Filtros básicos
MIN_PRICE   = 2.0       # precio mínimo
MIN_AVG_VOL = 300_000   # volumen promedio mínimo (para evitar ilíquidos)

# Limitar cantidad de tickers para no matar Colab
MAX_TICKERS = 20000  # podés subirlo si ves que corre bien


# ==============================
# 3) FUNCIÓN QUE EVALÚA LAS CONDICIONES
# ==============================

def compute_3m_pattern(df: pd.DataFrame):
    """
    Evalúa:
      - Suba > 90% en los últimos ~3 meses
      - Perf 1m entre -25% y 0%
      - Perf 1w > 10%
      - Devuelve mínimo y máximo del rally de 3 meses
    Si no se cumple algo, devuelve None.
    """

    if df is None or df.empty:
        return None

    df = df.sort_index().copy().dropna()

    # Necesitamos al menos 3 meses + algo de historial para volumen
    min_len = max(THREEM_BARS, 60) + 5
    if len(df) < min_len:
        return None

    close = df["Close"].values
    high  = df["High"].values
    low   = df["Low"].values
    vol   = df["Volume"].values

    i_last = len(df) - 1
    # Chequeos de longitud para 3m, 1m, 1w
    if i_last - THREEM_BARS < 0: return None
    if i_last - MONTH_BARS  < 0: return None
    if i_last - WEEK_BARS   < 0: return None

    last_close = close[-1]

    # Filtro de precio
    if last_close < MIN_PRICE:
        return None

    # Filtro de liquidez (volumen promedio 60 barras)
    vol_s = pd.Series(vol)
    avg_vol_60 = vol_s.rolling(60).mean().iloc[-1]
    if np.isnan(avg_vol_60) or avg_vol_60 < MIN_AVG_VOL:
        return None

    # -----------------------
    # 1) Performance 3 meses
    # -----------------------
    price_3m_ago = close[-1 - THREEM_BARS]
    if price_3m_ago <= 0:
        return None

    ret_3m = (last_close / price_3m_ago) - 1.0

    # Condición: > +90%
    if ret_3m <= MIN_RET_3M:
        return None

    # Mínimo y máximo del rally en los últimos 3 meses
    rally_window_highs = high[-THREEM_BARS:]
    rally_window_lows  = low[-THREEM_BARS:]

    rally_high = rally_window_highs.max()
    rally_low  = rally_window_lows.min()

    # -----------------------
    # 2) Performance último mes
    # -----------------------
    price_1m_ago = close[-1 - MONTH_BARS]
    if price_1m_ago <= 0:
        return None

    ret_1m = (last_close / price_1m_ago) - 1.0

    # Lateralización / corrección suave: entre 0% y -25%
    if not (MIN_RET_1M <= ret_1m <= MAX_RET_1M):
        return None

    # -----------------------
    # 3) Performance última semana
    # -----------------------
    price_1w_ago = close[-1 - WEEK_BARS]
    if price_1w_ago <= 0:
        return None

    ret_1w = (last_close / price_1w_ago) - 1.0

    if ret_1w <= MIN_RET_1W:
        return None

    # Si llegó hasta acá, cumple todas las condiciones
    last_row = df.iloc[-1]
    result = {
        "date": last_row.name,
        "close": float(last_close),
        "ret_3m_pct": float(ret_3m * 100.0),
        "ret_1m_pct": float(ret_1m * 100.0),
        "ret_1w_pct": float(ret_1w * 100.0),
        "rally_low": float(rally_low),
        "rally_high": float(rally_high),
        "avg_vol_60": float(avg_vol_60),
    }
    return result

# ... (rest of the logic for Bull Flag is conceptualized in the execution)

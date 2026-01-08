import screener

tickers = screener.get_sec_tickers()
print(f"Total Tickers: {len(tickers)}")
print(f"GSIT in list: {'GSIT' in tickers}")
print(f"BE in list: {'BE' in tickers}")

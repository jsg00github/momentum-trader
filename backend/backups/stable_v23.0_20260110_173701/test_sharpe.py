
try:
    print("Testing fundamental_screener import...")
    import fundamental_screener
    print("Import successful.")

    print("Running scan_sharpe_portfolio...")
    results = fundamental_screener.scan_sharpe_portfolio(min_sharpe=1.0, max_results=5)
    print(f"Results: {results}")

    if "results" in results and len(results["results"]) > 0:
        print("Building portfolio...")
        portfolio = fundamental_screener.build_equal_weight_portfolio(results["results"])
        print(f"Portfolio: {portfolio}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()

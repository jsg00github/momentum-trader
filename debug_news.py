
import yfinance as yf
import json

def get_news_sentiment(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        news = t.news
        print(f"--- News for {ticker_symbol} ---")
        # print(json.dumps(news, indent=2)) 
        
        # Simple Sentiment
        positive_words = ["record", "beat", "jump", "soar", "gain", "buy", "upgrade", "growth", "profit", "launch"]
        negative_words = ["drop", "fall", "miss", "loss", "crash", "down", "downgrade", "sell", "warn", "risk"]
        
        score = 0
        headlines = []
        
        if news:
            for n in news[:5]: # Analyze last 5
                title = n.get('title', '').lower()
                headlines.append(title)
                for w in positive_words:
                    if w in title:
                        score += 1
                for w in negative_words:
                    if w in title:
                        score -= 1
                        
        print(f"Headlines: {headlines}")
        print(f"Sentiment Score: {score}")
        return score
        
    except Exception as e:
        print(f"Error: {e}")

get_news_sentiment("NVDA")
get_news_sentiment("TSLA")

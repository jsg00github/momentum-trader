
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

def init_gemini():
    """Initialize the Gemini API client."""
    if not API_KEY:
        print("[Market Brain] Warning: GEMINI_API_KEY not found in environment.")
        return None
    
    try:
        genai.configure(api_key=API_KEY)
        return True
    except Exception as e:
        print(f"[Market Brain] Error initializing Gemini: {e}")
        return None

def get_market_insight(context_data):
    """
    Generate a market insight based on provided context data.
    """
    if not init_gemini():
        return "Error: AI Analyst is offline (Missing API Key)."

    try:
        # Construct the prompt
        prompt = f"""
        You are a seasoned Wall Street Quant and Technical Analyst. 
        Analyze the following market data and provide a concise, high-impact summary of the current market situation.
        
        CONTEXT:
        Indices: {context_data.get('indices', 'N/A')}
        Top Gainers/Losers: {context_data.get('movers', 'N/A')}
        Recent Headlines: {context_data.get('news', 'N/A')}
        Breadth: {context_data.get('breadth', 'N/A')}
        
        INSTRUCTIONS:
        1. Start with a "Sentiment Score" (0-100) and a one-word mood (e.g., "Fear", "Greed", "Caution").
        2. Explain WHY the market is moving this way (correlate news with price action).
        3. Identify any clear sector rotation.
        4. Provide a "Setup of the Day" if any pattern stands out.
        5. Keep it under 150 words. Use financial terminology but keep it readable.
        6. Be direct and confident.
        
        OUTPUT FORMAT:
        **Sentiment:** [Score]/100 ([Mood])
        **Analysis:** [Your analysis]
        **Actionable Insight:** [One clear takeaway]
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        import traceback
        print(f"[Market Brain] Generation error: {e}")
        traceback.print_exc()
        return f"Error generating insight: {e}"


def get_portfolio_insight(portfolio_data):
    """
    Generate portfolio-specific insights and recommendations.
    """
    if not init_gemini():
        return "Error: AI Analyst is offline (Missing API Key)."

    try:
        prompt = f"""
        You are a professional Portfolio Manager and Risk Analyst.
        Analyze the following portfolio and provide actionable recommendations.
        
        PORTFOLIO DATA:
        Open Positions: {portfolio_data.get('positions', 'No positions')}
        Total Value: ${portfolio_data.get('total_value', 'N/A')}
        Unrealized P&L: ${portfolio_data.get('unrealized_pnl', 'N/A')}
        Sector Exposure: {portfolio_data.get('sectors', 'N/A')}
        Top Winners: {portfolio_data.get('winners', 'N/A')}
        Top Losers: {portfolio_data.get('losers', 'N/A')}
        
        INSTRUCTIONS:
        1. Start with a "Portfolio Health Score" (0-100) and risk level (Low/Medium/High).
        2. Identify concentration risks (too much in one sector/stock).
        3. Highlight positions that need attention (stop losses, take profits).
        4. Suggest 1-2 specific actions to improve the portfolio.
        5. Keep it under 200 words. Be specific with ticker symbols.
        
        OUTPUT FORMAT:
        **Sentiment:** [Score]/100 ([Risk Level])
        **Analysis:** [Your portfolio analysis]
        **Actionable Insight:** [Specific recommendations with tickers]
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        import traceback
        print(f"[Market Brain] Portfolio analysis error: {e}")
        traceback.print_exc()
        return f"Error analyzing portfolio: {e}"


def chat_with_portfolio(user_query, conversation_history, portfolio_context):
    """
    Conversational AI assistant for portfolio queries.
    """
    if not init_gemini():
        return "Sorry, I'm currently offline. Please check the API key configuration."

    try:
        # Build conversation context (limit to last 5 exchanges = 10 messages)
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        
        # Format conversation history
        history_text = ""
        for msg in recent_history:
            role = "You" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"
        
        # Extract portfolio data
        positions = portfolio_context.get('positions', [])
        metrics = portfolio_context.get('metrics', {})
        
        # Build positions summary
        positions_summary = ""
        if positions:
            for p in positions[:10]:  # Limit to top 10
                ticker = p.get('ticker', '?')
                shares = p.get('shares', 0)
                entry = p.get('entry_price', 0)
                current = p.get('current_price', entry)
                pnl_pct = ((current / entry) - 1) * 100 if entry > 0 else 0
                positions_summary += f"- {ticker}: {shares} shares @ ${entry:.2f} (current: ${current:.2f}, P&L: {pnl_pct:+.1f}%)\n"
        else:
            positions_summary = "No open positions"
        
        # Construct the prompt
        system_prompt = f"""You are a professional Portfolio Copilot and Trading Assistant.
You have access to the user's live portfolio data and can answer questions about their positions, performance, and provide trading advice.

CURRENT PORTFOLIO DATA:
{positions_summary}

PORTFOLIO METRICS:
- Total Value: ${metrics.get('total_value', 0):,.2f}
- Unrealized P&L: ${metrics.get('unrealized_pnl', 0):,.2f}
- Open Positions: {metrics.get('position_count', 0)}

CONVERSATION HISTORY:
{history_text if history_text else "No previous conversation"}

INSTRUCTIONS:
1. Answer the user's question directly and concisely
2. Use the portfolio data to provide specific, actionable insights
3. Reference specific tickers when relevant
4. Be conversational but professional
5. If asked about a position not in the portfolio, say so clearly
6. Keep responses under 150 words unless more detail is explicitly requested
7. Use emojis sparingly for emphasis (📈📉💰⚠️)

USER QUESTION: {user_query}

Provide a helpful, data-driven response:"""

        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(system_prompt)
        
        return response.text
        
    except Exception as e:
        import traceback
        print(f"[Market Brain] Chat error: {e}")
        traceback.print_exc()
        return f"Sorry, I encountered an error: {str(e)}"

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# API Keys (Hardcoded)
ALPHA_VANTAGE_API_KEY = 'RWD7M0XBNKL9OLFT'  # Alpha Vantage API key
FINNHUB_API_KEY = 'cj378m9r01qqmkuns9m0cj378m9r01qnqmkuns9mg'  # Finnhub API key
GEMINI_API_KEY = 'AIzaSyBKGsbSpEdsVVY2eTb4mKinrnabdOAvJ6U'  # Gemini API key

# API URLs
ALPHA_VANTAGE_URL = 'https://www.alphavantage.co/query'
FINNHUB_BASE_URL = 'https://finnhub.io/api/v1'
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def interpret_stock_query(user_input):
    """Use Gemini to interpret user's stock query and identify stock symbols"""
    prompt = f"""Given this user query about stocks: "{user_input}"
    
    If this refers to a specific company or stock, respond with ONLY the stock symbol in capital letters.
    For example:
    - "tesla stock" → TSLA
    - "apple" → AAPL
    - "microsoft stock price" → MSFT
    - "how is amazon doing" → AMZN
    - "netflix shares" → NFLX
    
    If you can't identify a specific stock or if it's a general market query, respond with "MARKET_OVERVIEW".
    
    Respond with ONLY the symbol or MARKET_OVERVIEW, nothing else."""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 1,
            "maxOutputTokens": 10
        }
    }

    try:
        response = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        gemini_response = response.json()
        if 'candidates' in gemini_response and gemini_response['candidates']:
            symbol = gemini_response['candidates'][0]['content']['parts'][0]['text'].strip()
            return symbol
        return "MARKET_OVERVIEW"
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return "MARKET_OVERVIEW"

def fetch_alpha_vantage_data(symbol):
    """Fetch stock data from Alpha Vantage"""
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol,
        'apikey': ALPHA_VANTAGE_API_KEY
    }
    
    try:
        response = requests.get(ALPHA_VANTAGE_URL, params=params)
        data = response.json()
        
        if 'Global Quote' in data:
            quote = data['Global Quote']
            return {
                'price': quote.get('05. price', 'N/A'),
                'change': quote.get('09. change', 'N/A'),
                'change_percent': quote.get('10. change percent', 'N/A'),
                'volume': quote.get('06. volume', 'N/A'),
                'latest_trading_day': quote.get('07. latest trading day', 'N/A')
            }
        return {'error': 'No data available'}
    except Exception as e:
        return {'error': f'Alpha Vantage API error: {str(e)}'}

def fetch_finnhub_data(symbol):
    """Fetch additional stock data from Finnhub"""
    headers = {'X-Finnhub-Token': FINNHUB_API_KEY}
    
    try:
        # Get company profile
        profile_url = f"{FINNHUB_BASE_URL}/stock/profile2?symbol={symbol}"
        profile_response = requests.get(profile_url, headers=headers)
        profile_data = profile_response.json()
        
        # Get company quote
        quote_url = f"{FINNHUB_BASE_URL}/quote?symbol={symbol}"
        quote_response = requests.get(quote_url, headers=headers)
        quote_data = quote_response.json()
        
        return {
            'company_name': profile_data.get('name', 'N/A'),
            'market_cap': profile_data.get('marketCapitalization', 'N/A'),
            'industry': profile_data.get('finnhubIndustry', 'N/A'),
            'current_price': quote_data.get('c', 'N/A'),
            'high_24h': quote_data.get('h', 'N/A'),
            'low_24h': quote_data.get('l', 'N/A')
        }
    except Exception as e:
        return {'error': f'Finnhub API error: {str(e)}'}

def fetch_market_overview():
    """Fetch market overview data"""
    params = {
        'function': 'TOP_GAINERS_LOSERS',
        'apikey': ALPHA_VANTAGE_API_KEY
    }
    
    try:
        response = requests.get(ALPHA_VANTAGE_URL, params=params)
        data = response.json()
        
        if all(k in data for k in ('top_gainers', 'top_losers', 'most_actively_traded')):
            return {
                'gainers': data['top_gainers'][:5],
                'losers': data['top_losers'][:5],
                'most_active': data['most_actively_traded'][:5],
                'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            }
        return {'error': 'Market overview data not available'}
    except Exception as e:
        return {'error': f'Market overview error: {str(e)}'}

def analyze_with_gemini(data, is_market_overview=False):
    """Generate analysis using Gemini AI"""
    if is_market_overview:
        prompt = f"""Analyze this market overview data and provide insights:
        {data}
        
        Please provide:
        1. Overall market sentiment
        2. Notable market movers
        3. Key trends
        4. Brief outlook
        
        Keep it concise and professional."""
    else:
        prompt = f"""Analyze this stock data and provide insights:
        {data}
        
        Please provide in Markdown Format:
        1. Current performance summary
        2. Key metrics analysis
        3. Notable observations
        4. Brief outlook

        Give in Tables,use Headings and Sub-Headings.
        5. Include a summary of the data at the end. dont give data source.
        
        Keep it concise and professional."""

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 1,
            "maxOutputTokens": 1024
        }
    }

    try:
        response = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        gemini_response = response.json()
        if 'candidates' in gemini_response and gemini_response['candidates']:
            return gemini_response['candidates'][0]['content']['parts'][0]['text']
        return "Unable to generate analysis"
    except Exception as e:
        return f"Analysis error: {str(e)}"

@app.route('/api/stock', methods=['POST'])
def get_stock_analysis():
    try:
        data = request.json
        
        if not data or 'query' not in data:
            return jsonify({"error": "No query provided"}), 400
        
        # Interpret user query
        user_query = data['query']
        interpreted_symbol = interpret_stock_query(user_query)
        
        # Handle market overview case
        if interpreted_symbol == "MARKET_OVERVIEW":
            market_data = fetch_market_overview()
            analysis = analyze_with_gemini(market_data, is_market_overview=True)
            
            return jsonify({
                "type": "market_overview",
                "data": market_data,
                "analysis": analysis,
                "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Handle specific stock case
        alpha_data = fetch_alpha_vantage_data(interpreted_symbol)
        finnhub_data = fetch_finnhub_data(interpreted_symbol)
        
        combined_data = {
            'symbol': interpreted_symbol,
            'query': user_query,
            'alpha_vantage_data': alpha_data,
            'finnhub_data': finnhub_data
        }
        
        analysis = analyze_with_gemini(combined_data)
        
        return jsonify({
            "type": "stock_specific",
            "data": combined_data,
            "analysis": analysis,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
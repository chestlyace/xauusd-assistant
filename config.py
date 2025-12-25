import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ALPHA_VANTAGE_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')
TWELVE_DATA_KEY = os.getenv('TWELVE_DATA_API_KEY')
FINNHUB_KEY = os.getenv('FINNHUB_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
NEWSDATA_IO_KEY = os.getenv('NEWSDATA_IO_KEY')
FMP_API_KEY = os.getenv('FMP_API_KEY')

# Trading Settings
SYMBOL = "XAUUSD"
UPDATE_INTERVAL = 900  # 15 minutes in seconds
TRADING_HOURS = {
    'start': '00:00',  # Forex is 24/5
    'end': '23:59'
}

# News Keywords
NEWS_KEYWORDS = [
    # Gold & Symbol
    'gold', 'gold price', 'XAUUSD', 'XAU/USD',

    # USD & Currency
    'US dollar', 'USD', 'DXY', 'dollar index', 'USD weakness',

    # Interest Rates & Yields
    'Federal Reserve', 'Fed', 'interest rates',
    'rate hike', 'rate cut', 'monetary policy',
    'Treasury yields', '10-year yield', 'real yields',

    # Inflation & Economy
    'inflation', 'CPI', 'core CPI', 'PCE inflation',
    'stagflation', 'GDP slowdown', 'recession fears',

    # Risk & Sentiment
    'safe haven', 'risk-off', 'market uncertainty',
    'financial crisis', 'banking stress',

    # Central Banks & Institutions
    'central bank gold buying', 'gold reserves',
    'IMF', 'World Bank', 'ECB', 'BOJ', 'PBOC',

    # Geopolitics
    'geopolitical tensions', 'war', 'conflict',
    'sanctions', 'Middle East', 'Ukraine', 'Russia',

    # Commodities & Correlation
    'oil prices', 'energy crisis', 'commodity rally'
]


# News Impact
NEWS_IMPACT = {
    'high': ['FOMC', 'Fed rate decision', 'CPI', 'NFP', 'Powell speech'],
    'medium': ['Treasury yields', 'GDP', 'inflation expectations'],
    'low': ['market sentiment', 'analyst opinion']
}

#Tracked Events
TRACKED_EVENTS = [
    'FOMC meeting',
    'CPI release',
    'PCE inflation',
    'Non-Farm Payrolls',
    'Powell speech',
    'Treasury auction'
]



# API Rate Limits (calls per day)
RATE_LIMITS = {
    'alpha_vantage': 500,
    'news_api': 100,
    'newsdata_io': 200,
    'twelve_data': 800,
    'finnhub': 60,
    'gemini': 1500  # Free tier
}


# File paths
DATA_DIR = 'data'
ANALYSIS_LOG = f'{DATA_DIR}/analysis_log.json'
PRICE_CACHE = f'{DATA_DIR}/price_cache.json'
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


# AI Analysis Settings
AI_PROVIDER = 'gemini'  # 'gemini' or 'claude'
CONFIDENCE_THRESHOLD = 6  # Only alert on signals with confidence >= 6/10

# Analysis prompts
ANALYSIS_SYSTEM_PROMPT = """You are a senior professional forex and precious metals market analyst with over 20 years of experience, specializing in XAUUSD (Gold vs USD).

Your role is to analyze provided market data and produce disciplined, high-quality trading insights for BOTH:
- Scalping trades (short-term)
- Intraday / short-term swing trades

Your analysis must be realistic, risk-aware, and suitable for real trading decisions.

You must base your conclusions strictly on:
- XAUUSD price action
- Technical structure and momentum
- Market news and sentiment
- Macroeconomic and geopolitical drivers affecting gold and the US dollar

GENERAL PRINCIPLES
- Be concise, objective, and evidence-based.
- Never fabricate certainty.
- Capital preservation is more important than trade frequency.
- If conditions are unclear, recommend NO TRADE.
- Gold is volatile — risk control is mandatory.

--------------------------------------------------
TIMEFRAME MODES (MANDATORY)
--------------------------------------------------

The analysis will specify one of the following modes:

SCALPING MODE (M1–M15):
- Focus on short-term momentum, liquidity, and reactions.
- Prioritize:
  - Trend alignment on higher timeframe (M15–H1)
  - Key intraday support/resistance
  - Breakouts, rejections, and momentum continuation
- Ignore long-term macro narratives unless they are actively driving volatility.
- Be extremely selective during news releases.

INTRADAY MODE (H1–H4):
- Focus on structure, trend continuation or reversal.
- Incorporate macro, sentiment, and news drivers.
- Identify clear directional bias.

You must adapt your analysis style strictly to the selected mode.

--------------------------------------------------
VOLATILITY & NEWS RULES
--------------------------------------------------

- High-impact events (FOMC, CPI, PCE, NFP, Fed speeches) dramatically affect gold.
- During or immediately before high-impact events:
  - Scalping confidence must be downgraded
  - NO TRADE is often the correct recommendation
- Elevated volatility without structure = NO TRADE

--------------------------------------------------
CONFIDENCE SCORING (MANDATORY)
--------------------------------------------------

Assign a confidence score from 1 to 10 using this scale:

1–3  : Highly speculative, poor structure, conflicting signals  
4–5  : Weak bias, low-quality setup  
6–7  : Clear setup with aligned factors  
8–9  : Strong confluence, clean structure, favorable conditions  
10   : Exceptional alignment (rare, use sparingly)

For SCALPING MODE:
- Scores above 8 should be rare
- Precision matters more than conviction

--------------------------------------------------
TRADE DISCIPLINE
--------------------------------------------------

You must explicitly recommend one of:
- BUY
- SELL
- NO TRADE

NO TRADE is REQUIRED when:
- Structure is unclear
- Spread/liquidity conditions are unfavorable
- News risk is high
- Confidence is below acceptable levels

--------------------------------------------------
OUTPUT FORMAT (STRICT)
--------------------------------------------------

Respond using EXACTLY the following structure:

Timeframe Mode:
- Scalping (M1–M15) OR Intraday (H1–H4)

Market Bias:
- Bullish / Bearish / Neutral

Key Drivers:
- Bullet list of the main technical, momentum, or news factors

Technical Context:
- Trend or range state
- Key support and resistance levels
- Momentum or rejection signals

News & Volatility Impact:
- High / Medium / Low
- Brief justification

Trade Recommendation:
- BUY / SELL / NO TRADE

Confidence Score:
- X / 10

Risk Notes:
- Key invalidation levels
- Volatility warnings
- Event risk or execution cautions
"""

# Trading parameters
RISK_LEVELS = {
    'conservative': {'max_risk': 1, 'min_confidence': 8},
    'moderate': {'max_risk': 2, 'min_confidence': 6},
    'aggressive': {'max_risk': 3, 'min_confidence': 5}
}

TRADING_STYLE = 'moderate'  # Change based on your preference

# AI Analysis Mode
ANALYSIS_MODE = 'intraday'  # 'scalping' or 'intraday'

# Alert thresholds
CONFIDENCE_THRESHOLD = 6  # Minimum confidence for alerts
SCALPING_CONFIDENCE_THRESHOLD = 7  # Higher bar for scalping


# === SCHEDULING SETTINGS ===
UPDATE_INTERVAL_MINUTES = 15  # How often to analyze (15, 30, 60)
RUN_MODE = 'continuous'  # 'continuous' or 'once'

# Trading hours (24/5 forex market)
TRADING_ACTIVE = True  # Set to False to pause all analysis
TRADING_DAYS = [0, 1, 2, 3, 4]  # Monday=0 to Friday=4 (forex closed weekends)

# === ALERT SETTINGS ===
ALERT_METHODS = ['console', 'file']  # Options: 'console', 'file', 'email', 'telegram'


# === LOGGING SETTINGS ===
LOG_ALL_ANALYSES = True  # Log every analysis (not just alerts)
LOG_FILE = f'{DATA_DIR}/trading_log.json'
PERFORMANCE_LOG = f'{DATA_DIR}/performance_log.json'

# === DATA PERSISTENCE ===
SAVE_MARKET_DATA = True  # Save raw market data for review
MARKET_DATA_FILE = f'{DATA_DIR}/market_data_history.json'

# For Email
EMAIL_ENABLED = False
EMAIL_FROM = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"  # Use Gmail App Password
EMAIL_TO = "your_phone@carrier.com"  # For SMS via email

# Telegram alerts (if enabled)
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')



ALERT_METHODS = ['console', 'file', 'email', 'telegram']
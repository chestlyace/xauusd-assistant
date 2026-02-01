import json
import re
from datetime import datetime
import pytz
import google.generativeai as genai
from config import *
from google.api_core import exceptions

class EnhancedMarketAnalyzer:
    def __init__(self, analysis_mode='intraday', timeframe='M15', account_size=100, risk_percent=5):
        """Initialize the AI analyzer with enhanced entry and risk management
        
        Args:
            analysis_mode: 'scalping' (M1-M15) or 'intraday' (H1-H4)
            timeframe: 'M1', M3, 'M5', 'M15', M30, 'H1', 'H4', 'D1'
            account_size: Trading account size in USD (default: 100)
            risk_percent: Risk percentage per trade (default: 5% = $5 on $100 account)
        """
        # Setup API keys
        self.api_keys = globals().get('GEMINI_API_KEYS') or [GEMINI_API_KEY]
        self.current_key_index = 0
        
        # Configure first key
        if self.api_keys:
            genai.configure(api_key=self.api_keys[self.current_key_index])
            
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        self.analysis_count = 0
        self.timeframe = timeframe.upper()
        self.analysis_mode = self._determine_mode(analysis_mode, self.timeframe)
        
        # Risk management parameters
        self.account_size = account_size
        self.risk_percent = risk_percent
        self.max_risk_dollars = (account_size * risk_percent) / 100
        
        print(f"💰 Account: ${account_size} | Risk/Trade: {risk_percent}% (${self.max_risk_dollars:.2f})")
        
    def _determine_mode(self, mode, timeframe):
        if mode.lower() in ['ultra_scalping', 'scalping', 'intraday', 'swing']:
            return mode.lower()

        if timeframe in ['M1', 'M3', 'M5']:
            return 'ultra_scalping'
        elif timeframe in ['M15', 'M30']:
            return 'scalping'
        elif timeframe in ['H1', 'H4']:
            return 'intraday'
        elif timeframe in ['D1']:
            return 'swing'
        else:
            return 'intraday'
        
    def get_trading_session(self):
        """Determine current trading session"""
        utc_now = datetime.now(pytz.UTC)
        hour = utc_now.hour
        
        if 0 <= hour < 8:
            return "ASIA"
        elif 8 <= hour < 16:
            return "LONDON"
        elif 16 <= hour < 22:
            return "NEW_YORK"
        else:
            return "ASIA_LATE"
    
    def calculate_entry_zones(self, current_price, market_data):
        """Calculate optimal entry zones based on market structure"""
        indicators = market_data.get('technical_indicators', {})
        
        # Get support/resistance from price history
        history = market_data.get('price_history', {}).get('history', [])
        
        if not history or len(history) < 20:
            # Fallback: use simple zones around current price
            return self._simple_entry_zones(current_price)
        
        # Extract recent highs/lows
        recent_prices = [float(candle['close']) for candle in history[:20]]
        recent_highs = [float(candle['high']) for candle in history[:20]]
        recent_lows = [float(candle['low']) for candle in history[:20]]
        
        # Calculate structure levels
        structure = {
            'current': current_price,
            'sma_20': indicators.get('sma_20'),
            'recent_high': max(recent_highs) if recent_highs else current_price,
            'recent_low': min(recent_lows) if recent_lows else current_price,
            'avg_range': (max(recent_prices) - min(recent_prices)) / 20 if recent_prices else 0
        }
        
        # Calculate entry zones based on timeframe
        if self.timeframe in ['M1', 'M3', 'M5']:
            # Ultra scalping: very tight zones
            entry_buffer = structure['avg_range'] * 0.1  # 10% of avg range
        elif self.timeframe in ['M15', 'M30']:
            # Scalping: tight zones
            entry_buffer = structure['avg_range'] * 0.2  # 20% of avg range
        elif self.timeframe in ['H1', 'H4']:
            # Intraday: moderate zones
            entry_buffer = structure['avg_range'] * 0.3  # 30% of avg range
        else:
            # Swing: wider zones
            entry_buffer = structure['avg_range'] * 0.4  # 40% of avg range
        
        return {
            'structure': structure,
            'entry_buffer': entry_buffer,
            'buy_zone_high': current_price + entry_buffer,
            'buy_zone_low': current_price - (entry_buffer * 0.5),
            'sell_zone_high': current_price + (entry_buffer * 0.5),
            'sell_zone_low': current_price - entry_buffer
        }
    
    def _simple_entry_zones(self, current_price):
        """Fallback simple entry zones"""
        if self.timeframe in ['M1', 'M3', 'M5']:
            buffer = 2  # $2 buffer
        elif self.timeframe in ['M15', 'M30']:
            buffer = 5  # $5 buffer
        elif self.timeframe in ['H1', 'H4']:
            buffer = 10  # $10 buffer
        else:
            buffer = 20  # $20 buffer
        
        return {
            'entry_buffer': buffer,
            'buy_zone_high': current_price + buffer,
            'buy_zone_low': current_price - (buffer * 0.5),
            'sell_zone_high': current_price + (buffer * 0.5),
            'sell_zone_low': current_price - buffer
        }
    
    def calculate_position_size(self, entry_price, stop_loss):
        """Calculate position size based on risk management rules
        
        For gold (XAUUSD), 1 lot = 100 oz
        Pip value = $0.01 per 0.01 lot
        """
        if not entry_price or not stop_loss:
            return None
        
        # Calculate risk in dollars
        risk_in_price = abs(entry_price - stop_loss)
        
        # For XAUUSD: 
        # 1 standard lot = 100 oz
        # 1 micro lot = 0.01 lots
        # Price move of $1 = $1 per 0.01 lots
        
        # Calculate lots needed to risk max_risk_dollars
        # If risk is $10, and stop is $50 away:
        # lots = 10 / 50 = 0.2 lots (20 micro lots)
        
        lots = self.max_risk_dollars / risk_in_price
        
        # Round to 2 decimal places (0.01 = 1 micro lot)
        lots = round(lots, 2)
        
        # Minimum position size
        if lots < 0.01:
            lots = 0.01
        
        # Calculate actual risk with this position size
        actual_risk = lots * risk_in_price
        
        return {
            'lots': lots,
            'micro_lots': int(lots * 100),
            'risk_in_price': round(risk_in_price, 2),
            'actual_risk_dollars': round(actual_risk, 2),
            'max_risk_dollars': self.max_risk_dollars,
            'position_size_valid': actual_risk <= self.max_risk_dollars * 1.1  # 10% tolerance
        }
    
    def get_system_prompt(self):
        """Enhanced system prompt with entry and risk management focus"""
        
        base_prompt = f"""You are a professional XAUUSD (Gold/USD) trader with deep expertise in technical analysis, market structure, and risk management.

CRITICAL ACCOUNT PARAMETERS:
- Account Size: ${self.account_size}
- Risk Per Trade: {self.risk_percent}% = ${self.max_risk_dollars:.2f} MAX
- This is a STRICT LIMIT - stops must be positioned to risk ≤ ${self.max_risk_dollars:.2f}

Your task is to analyze market data and produce PRECISE trading setups with OPTIMAL ENTRIES and CONTROLLED RISK.

================ ANALYSIS FORMAT ================

---ANALYSIS START---

Market Bias: [BULLISH / BEARISH / NEUTRAL]
Bias Strength: [1-10]

Trade Recommendation: [BUY / SELL / NO TRADE]
Confidence Score: [1-10]

Entry Strategy:
Primary Entry: [specific price - NOT current price unless it's optimal]
Entry Zone: [low price] - [high price]
Entry Logic: [why this is the optimal entry point]

Risk Management:
Stop Loss: [specific price]
Risk in Dollars: [calculated from entry to stop]
Take Profit 1: [specific price, R:R 1.5+]
Take Profit 2: [specific price, R:R 2.5+]
Risk Level: [LOW / MEDIUM / HIGH]

Key Factors:
- Factor 1
- Factor 2
- Factor 3

Technical Setup:
[Concise explanation focusing on entry timing and structure]

Invalidation:
[Clear condition that would invalidate this setup]

---ANALYSIS END---

================ ENTRY POINT RULES ================

1. NEVER use current price as entry unless it's truly optimal
2. For BUY setups:
   - Primary Entry should be near support/pullback levels
   - Entry Zone should capture potential dips (not chasing)
   - If price already broke above resistance, recommend waiting for pullback
   
3. For SELL setups:
   - Primary Entry should be near resistance/rally levels
   - Entry Zone should capture potential bounces (not chasing)
   - If price already broke below support, recommend waiting for retest

4. Entry Quality Checklist:
   ✓ Is this entry better than current price?
   ✓ Does it improve risk/reward?
   ✓ Is there structural logic (support/resistance/moving average)?
   ✓ Would a patient trader wait for this level?

5. If NO better entry exists than current price:
   - State clearly: "Immediate entry at market"
   - Explain why waiting is not optimal
   - Must have strong momentum justification

================ RISK MANAGEMENT RULES ================

1. STOP LOSS PLACEMENT:
   - MUST result in risk ≤ ${self.max_risk_dollars:.2f}
   - Place at logical structure levels (not arbitrary)
   - For BUY: below recent swing low or support
   - For SELL: above recent swing high or resistance
   
2. If optimal stop would risk > ${self.max_risk_dollars:.2f}:
   - Recommend NO TRADE
   - Explain: "Stop too wide for account size"
   - NEVER compromise on stop placement to fit risk

3. TAKE PROFIT TARGETS:
   - TP1: Minimum R:R of 1.5:1
   - TP2: Minimum R:R of 2.5:1
   - Place at logical levels (resistance/support zones)
   
4. POSITION SIZING:
   - Will be calculated automatically
   - Focus on optimal stop placement

================ TIMEFRAME-SPECIFIC GUIDANCE ================
"""

        if self.analysis_mode == 'ultra_scalping':
            mode_specific = f"""
ULTRA SCALPING ({self.timeframe}):
- Entry precision is CRITICAL
- Look for micro pullbacks/bounces
- Entry should be within $0.50-$2 of current price
- Stop loss: $1-$5 max (must fit ${self.max_risk_dollars:.2f} risk)
- If stop needs to be wider, recommend NO TRADE
- Target quick moves: TP1 at 1.5:1, TP2 at 2:1
"""
        elif self.analysis_mode == 'scalping':
            mode_specific = f"""
SCALPING ({self.timeframe}):
- Look for clear entry opportunities within $2-$5
- Stops: $3-$10 typical (must fit ${self.max_risk_dollars:.2f} risk)
- Entry zones should be tight
- Target momentum: TP1 at 1.5:1, TP2 at 2.5:1
"""
        elif self.analysis_mode == 'intraday':
            mode_specific = f"""
INTRADAY ({self.timeframe}):
- Entry can be within $5-$15 of current price
- Stops: $10-$20 typical (must fit ${self.max_risk_dollars:.2f} risk)
- Look for pullbacks to moving averages or key levels
- Target larger moves: TP1 at 2:1, TP2 at 3:1
"""
        else:
            mode_specific = f"""
SWING ({self.timeframe}):
- Entry within $15-$40 of current price acceptable
- Stops: $20-$40 typical (must fit ${self.max_risk_dollars:.2f} risk)
- Focus on major structure levels
- Target swing ranges: TP1 at 2:1, TP2 at 4:1
"""

        return base_prompt + mode_specific + """

================ CRITICAL RULES ================

1. If no optimal entry exists → NO TRADE
2. If stop would risk > ${self.max_risk_dollars:.2f} → NO TRADE
3. If R:R < 1.5:1 → NO TRADE
4. If Confidence < 6 → NO TRADE
5. All prices must be EXACT numbers
6. Entry must have structural logic
7. Be conservative - preservation of capital is priority #1
"""
    
    def format_market_context(self, market_data):
        """Enhanced market context with structure levels"""
        current = market_data.get('current_price', {})
        indicators = market_data.get('technical_indicators', {})
        news = market_data.get('news', [])
        high_rel_news = market_data.get('high_relevance_news', [])
        
        if not current:
            return "ERROR: Price data unavailable"
        
        current_price = current['price']
        session = self.get_trading_session()
        spread = current.get('spread', self.estimate_spread(current_price))
        
        # Calculate entry zones
        entry_zones = self.calculate_entry_zones(current_price, market_data)
        
        context = f"""CURRENT MARKET CONTEXT

Current Price: ${current_price:.2f}
Session: {session}
Spread: ${spread:.2f}
Timestamp: {current['timestamp']}

ACCOUNT RISK PARAMETERS:
- Account Size: ${self.account_size}
- Max Risk: ${self.max_risk_dollars:.2f} ({self.risk_percent}%)
- Timeframe: {self.timeframe}

ENTRY ZONE GUIDANCE:
"""
        
        if 'structure' in entry_zones:
            struct = entry_zones['structure']
            context += f"- SMA 20: ${struct.get('sma_20', 'N/A')}\n"
            context += f"- Recent High: ${struct.get('recent_high', 'N/A'):.2f}\n"
            context += f"- Recent Low: ${struct.get('recent_low', 'N/A'):.2f}\n"
            context += f"- Avg Range: ${struct.get('avg_range', 'N/A'):.2f}\n"
        
        context += f"\nSUGGESTED ENTRY ZONES:\n"
        context += f"- BUY Zone: ${entry_zones.get('buy_zone_low', 0):.2f} - ${entry_zones.get('buy_zone_high', 0):.2f}\n"
        context += f"- SELL Zone: ${entry_zones.get('sell_zone_low', 0):.2f} - ${entry_zones.get('sell_zone_high', 0):.2f}\n"
        
        if 'change_percent' in current:
            context += f"\n24h Change: {current['change_percent']:+.2f}%\n"
        
        if 'high' in current and 'low' in current:
            context += f"Today High: ${current['high']:.2f}\n"
            context += f"Today Low: ${current['low']:.2f}\n"
            day_range = current['high'] - current['low']
            context += f"Daily Range: ${day_range:.2f}\n"
        
        if indicators:
            context += f"\nTechnical Indicators:\n"
            context += f"SMA 20: ${indicators.get('sma_20', 'N/A')}\n"
            if indicators.get('sma_50'):
                context += f"SMA 50: ${indicators.get('sma_50')}\n"
            context += f"Recent Trend: {indicators.get('recent_trend', 'N/A')}\n"
            context += f"Volatility: {indicators.get('volatility', 'N/A')}\n"
            context += f"Price vs SMA20: {indicators.get('current_vs_sma20', 'N/A')}%\n"
        
        # News
        if self.analysis_mode in ['scalping', 'ultra_scalping']:
            relevant_news = high_rel_news[:3]
            context += f"\nHigh-Impact News ({len(relevant_news)} items):\n"
        else:
            relevant_news = news[:8]
            context += f"\nRecent News ({len(news)} total):\n"
        
        for i, article in enumerate(relevant_news, 1):
            score = article.get('relevance_score', 0)
            context += f"{i}. [Rel: {score}] {article['title']}\n"
        
        return context
    
    def estimate_spread(self, current_price):
        """Estimate spread"""
        session = self.get_trading_session()
        if session in ['LONDON', 'NEW_YORK']:
            return 0.30
        else:
            return 0.60
    
    def _rotate_api_key(self):
        """Switch to next API key"""
        if not self.api_keys or len(self.api_keys) <= 1:
            return False
            
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_key_index]
        mask_key = f"...{new_key[-4:]}" if len(new_key) > 4 else "std"
        print(f"  ⟳ Rotating API Key to index {self.current_key_index} ({mask_key})")
        
        genai.configure(api_key=new_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        return True

    def analyze_market(self, market_data):
        """Enhanced market analysis with entry optimization"""
        self.analysis_count += 1
        analysis_id = f"{self.analysis_mode}_{self.analysis_count}_{int(datetime.now().timestamp())}"
        
        print(f"\n🔍 Analyzing (Mode: {self.analysis_mode.upper()}, TF: {self.timeframe}, Risk: ${self.max_risk_dollars:.2f})")
        
        system_prompt = self.get_system_prompt()
        market_context = self.format_market_context(market_data)
        
        full_prompt = f"{system_prompt}\n\n{market_context}"
        
        max_attempts = len(self.api_keys) if hasattr(self, 'api_keys') and self.api_keys else 1
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.model.generate_content(full_prompt)
                analysis_text = response.text
                
                structured = self.parse_enhanced_output(analysis_text, market_data, analysis_id)
                
                if structured.get('success'):
                    print(f"✅ Analysis complete - {structured['trade_recommendation']}")
                
                return structured
                
            except Exception as e:
                last_error = e
                is_rate_limit = isinstance(e, exceptions.ResourceExhausted) or "429" in str(e) or "quota" in str(e).lower()
                
                if is_rate_limit and attempt < max_attempts - 1:
                    if self._rotate_api_key():
                        print("  Retrying...")
                        continue
                
                print(f"Error: {e}")
                break

        return {
            'success': False,
            'error': str(last_error),
            'timestamp': datetime.now().isoformat(),
            'analysis_id': f"error_{self.analysis_count}"
        }
    
    def parse_enhanced_output(self, analysis_text, market_data, analysis_id):
        """Parse enhanced output with entry and position sizing"""
        
        try:
            current_price = market_data.get('current_price', {}).get('price', 0)
            
            # Extract all standard fields
            bias_match = re.search(r'Market Bias:\s*(BULLISH|BEARISH|NEUTRAL)', analysis_text, re.IGNORECASE)
            market_bias = bias_match.group(1).upper() if bias_match else 'NEUTRAL'
            
            strength_match = re.search(r'Bias Strength:\s*(\d+)', analysis_text)
            bias_strength = int(strength_match.group(1)) if strength_match else 5
            bias_strength = max(1, min(10, bias_strength))
            
            conf_match = re.search(r'Confidence Score:\s*(\d+)', analysis_text)
            confidence = int(conf_match.group(1)) if conf_match else 0
            confidence = max(0, min(10, confidence))
            
            trade_match = re.search(r'Trade Recommendation:\s*(BUY|SELL|NO TRADE)', analysis_text, re.IGNORECASE)
            trade_recommendation = trade_match.group(1).upper() if trade_match else 'NO TRADE'
            
            # ENHANCED: Extract entry information
            primary_entry_match = re.search(r'Primary Entry:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            primary_entry = float(primary_entry_match.group(1)) if primary_entry_match else current_price
            
            # Extract entry zone
            entry_zone_match = re.search(r'Entry Zone:\s*\$?(\d+(?:\.\d+)?)\s*-\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            if entry_zone_match:
                entry_zone_low = float(entry_zone_match.group(1))
                entry_zone_high = float(entry_zone_match.group(2))
            else:
                # Fallback: create zone around primary entry
                buffer = 2 if self.timeframe in ['M1', 'M3', 'M5'] else 5
                entry_zone_low = primary_entry - buffer
                entry_zone_high = primary_entry + buffer
            
            # Extract entry logic
            entry_logic_match = re.search(r'Entry Logic:(.*?)(?=Risk Management:|$)', analysis_text, re.DOTALL)
            entry_logic = entry_logic_match.group(1).strip() if entry_logic_match else "Market entry"
            
            # Extract risk management
            sl_match = re.search(r'Stop Loss:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            stop_loss = float(sl_match.group(1)) if sl_match else None
            
            tp1_match = re.search(r'Take Profit 1:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            tp2_match = re.search(r'Take Profit 2:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            take_profit_1 = float(tp1_match.group(1)) if tp1_match else None
            take_profit_2 = float(tp2_match.group(1)) if tp2_match else None
            
            risk_match = re.search(r'Risk Level:\s*(LOW|MEDIUM|HIGH)', analysis_text, re.IGNORECASE)
            risk_level = risk_match.group(1).upper() if risk_match else 'HIGH'
            
            # ENHANCED: Calculate position sizing
            position_info = None
            if trade_recommendation in ['BUY', 'SELL'] and stop_loss and primary_entry:
                position_info = self.calculate_position_size(primary_entry, stop_loss)
                
                # SAFETY: Validate risk
                if position_info and not position_info['position_size_valid']:
                    print(f"  ⚠️  Risk too high: ${position_info['actual_risk_dollars']:.2f} > ${self.max_risk_dollars:.2f}")
                    trade_recommendation = 'NO TRADE'
                    risk_level = 'HIGH'
            
            # SAFETY NETS
            if confidence < 6:
                trade_recommendation = 'NO TRADE'
                print(f"  Safety: Confidence {confidence} < 6")
            
            if self.analysis_mode in ['scalping', 'ultra_scalping'] and risk_level == 'HIGH':
                trade_recommendation = 'NO TRADE'
                print(f"  Safety: {self.analysis_mode} + HIGH risk")
            
            if trade_recommendation in ['BUY', 'SELL'] and not stop_loss:
                trade_recommendation = 'NO TRADE'
                print(f"  Safety: No stop loss defined")
            
            # Extract other fields
            factors_section = re.search(r'Key Factors:(.*?)(?=Technical Setup:|$)', analysis_text, re.DOTALL)
            key_factors = []
            if factors_section:
                factor_lines = factors_section.group(1).strip().split('\n')
                key_factors = [line.strip('- ').strip() for line in factor_lines if line.strip().startswith('-')]
            
            invalidation_match = re.search(r'Invalidation:(.*?)(?=---|$)', analysis_text, re.DOTALL)
            invalidation = invalidation_match.group(1).strip() if invalidation_match else "Not specified"
            
            session = self.get_trading_session()
            
            # Calculate R:R ratios
            rr1 = None
            rr2 = None
            if stop_loss and primary_entry:
                risk = abs(primary_entry - stop_loss)
                if take_profit_1:
                    reward1 = abs(take_profit_1 - primary_entry)
                    rr1 = round(reward1 / risk, 2) if risk > 0 else 0
                if take_profit_2:
                    reward2 = abs(take_profit_2 - primary_entry)
                    rr2 = round(reward2 / risk, 2) if risk > 0 else 0
            
            return {
                'success': True,
                'analysis_id': analysis_id,
                'timestamp': datetime.now().isoformat(),
                'analysis_mode': self.analysis_mode,
                'session': session,
                'current_price': current_price,
                
                # Core signals
                'market_bias': market_bias,
                'bias_strength': bias_strength,
                'trade_recommendation': trade_recommendation,
                'confidence': confidence,
                'risk_level': risk_level,
                
                # ENHANCED: Entry information
                'primary_entry': primary_entry,
                'entry_zone_low': entry_zone_low,
                'entry_zone_high': entry_zone_high,
                'entry_logic': entry_logic,
                'entry_better_than_current': abs(primary_entry - current_price) > 1,  # More than $1 difference
                
                # Trade levels
                'stop_loss': stop_loss,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                'risk_reward_1': rr1,
                'risk_reward_2': rr2,
                
                # ENHANCED: Position sizing
                'position_sizing': position_info,
                'account_size': self.account_size,
                'max_risk_dollars': self.max_risk_dollars,
                
                # Analysis details
                'key_factors': key_factors,
                'invalidation': invalidation,
                'full_analysis': analysis_text,
                
                # Metadata
                'market_data_summary': {
                    'price': current_price,
                    'trend': market_data.get('technical_indicators', {}).get('recent_trend'),
                    'news_count': len(market_data.get('news', [])),
                    'high_relevance_news': len(market_data.get('high_relevance_news', []))
                }
            }
            
        except Exception as e:
            print(f"Error parsing: {e}")
            return {
                'success': False,
                'error': f"Parsing failed: {e}",
                'raw_output': analysis_text,
                'timestamp': datetime.now().isoformat(),
                'analysis_id': analysis_id
            }
    
    def should_alert(self, analysis):
        """Enhanced alert logic"""
        if not analysis.get('success'):
            return False
        
        trade_rec = analysis.get('trade_recommendation', 'NO TRADE')
        confidence = analysis.get('confidence', 0)
        risk_level = analysis.get('risk_level', 'HIGH')
        
        if trade_rec == 'NO TRADE':
            return False
        
        if confidence < CONFIDENCE_THRESHOLD:
            return False
        
        if self.analysis_mode in ['scalping', 'ultra_scalping'] and confidence < 7:
            return False
        
        if self.analysis_mode in ['scalping', 'ultra_scalping'] and risk_level == 'HIGH':
            return False
        
        if not analysis.get('stop_loss'):
            return False
        
        # ENHANCED: Check position sizing validity
        position_info = analysis.get('position_sizing')
        if position_info and not position_info.get('position_size_valid'):
            return False
        
        return True
    
    def generate_summary(self, analysis):
        """Enhanced summary with entry and position info"""
        if not analysis.get('success'):
            return f"Analysis failed: {analysis.get('error', 'Unknown error')}"
        
        trade_rec = analysis['trade_recommendation']
        confidence = analysis['confidence']
        current_price = analysis.get('current_price', 0)
        primary_entry = analysis.get('primary_entry', current_price)
        
        if trade_rec == 'BUY':
            emoji = "📈"
        elif trade_rec == 'SELL':
            emoji = "📉"
        else:
            emoji = "⏸️"
        
        summary = f"""
{emoji} XAUUSD Analysis [{self.timeframe}] [{analysis['analysis_mode'].upper()}]
{'='*70}
ID: {analysis['analysis_id']}
Signal: {trade_rec}
Confidence: {confidence}/10
Bias: {analysis['market_bias']} (Strength: {analysis['bias_strength']}/10)
Risk: {analysis['risk_level']}
Session: {analysis.get('session', 'N/A')}

💰 ACCOUNT INFO:
Size: ${self.account_size} | Max Risk: ${self.max_risk_dollars:.2f}
"""
        
        if trade_rec != 'NO TRADE':
            summary += f"\n📊 ENTRY STRATEGY:"
            summary += f"\nCurrent Price: ${current_price:.2f}"
            summary += f"\n→ Primary Entry: ${primary_entry:.2f}"
            
            entry_diff = primary_entry - current_price
            if abs(entry_diff) > 1:
                direction = "above" if entry_diff > 0 else "below"
                summary += f" ({direction} current by ${abs(entry_diff):.2f})"
            else:
                summary += " (at market)"
            
            summary += f"\n→ Entry Zone: ${analysis['entry_zone_low']:.2f} - ${analysis['entry_zone_high']:.2f}"
            summary += f"\n→ Logic: {analysis.get('entry_logic', 'N/A')[:80]}..."
            
            if analysis.get('stop_loss'):
                sl = analysis['stop_loss']
                risk_price = abs(primary_entry - sl)
                summary += f"\n\n💵 RISK MANAGEMENT:"
                summary += f"\nStop Loss: ${sl:.2f}"
                summary += f"\nRisk (price): ${risk_price:.2f}"
                
                position_info = analysis.get('position_sizing')
                if position_info:
                    summary += f"\nPosition Size: {position_info['lots']} lots ({position_info['micro_lots']} micro)"
                    summary += f"\nActual Risk: ${position_info['actual_risk_dollars']:.2f}"
                    if not position_info['position_size_valid']:
                        summary += " ⚠️ EXCEEDS MAX RISK!"
            
            if analysis.get('take_profit_1'):
                tp1 = analysis['take_profit_1']
                reward1 = abs(tp1 - primary_entry)
                rr1 = analysis.get('risk_reward_1', 0)
                summary += f"\n\n🎯 TARGETS:"
                summary += f"\nTP1: ${tp1:.2f} (+${reward1:.2f}, R:R {rr1})"
                
            if analysis.get('take_profit_2'):
                tp2 = analysis['take_profit_2']
                reward2 = abs(tp2 - primary_entry)
                rr2 = analysis.get('risk_reward_2', 0)
                summary += f"\nTP2: ${tp2:.2f} (+${reward2:.2f}, R:R {rr2})"
        
        if analysis.get('key_factors'):
            summary += f"\n\n🔑 Key Factors:"
            for factor in analysis['key_factors'][:3]:
                summary += f"\n  • {factor}"
        
        summary += f"\n\n❌ Invalidation: {analysis.get('invalidation', 'N/A')[:80]}"
        summary += f"\nTimestamp: {analysis['timestamp']}"
        summary += "\n" + "="*70
        
        return summary


# Test
if __name__ == "__main__":
    from data_collector import DataCollector
    
    print("Testing Enhanced Analyzer with Entry Optimization & Position Sizing")
    print("="*70)
    
    # Test with $100 account, 5% risk ($5 per trade)
    collector = DataCollector()
    market_data = collector.get_market_data()
    
    # Test M15 scalping with small account
    print(f"\n{'='*70}")
    print("TEST: M15 Scalping with $100 account")
    print('='*70)
    
    analyzer = EnhancedMarketAnalyzer(
        timeframe='M15',
        account_size=100,
        risk_percent=5
    )
    
    analysis = analyzer.analyze_market(market_data)
    
    if analysis.get('success'):
        print("\n" + analyzer.generate_summary(analysis))
        
        if analyzer.should_alert(analysis):
            print("\n🔔 ALERT CRITERIA MET")
        else:
            print("\n⏸️  NO ALERT")
        
        # Show detailed breakdown
        print(f"\n{'='*70}")
        print("DETAILED BREAKDOWN:")
        print(f"{'='*70}")
        print(f"Current Price: ${analysis['current_price']:.2f}")
        print(f"Primary Entry: ${analysis['primary_entry']:.2f}")
        print(f"Entry Zone: ${analysis['entry_zone_low']:.2f} - ${analysis['entry_zone_high']:.2f}")
        
        if analysis.get('position_sizing'):
            ps = analysis['position_sizing']
            print(f"\nPosition Sizing:")
            print(f"  Lots: {ps['lots']}")
            print(f"  Micro Lots: {ps['micro_lots']}")
            print(f"  Risk in Price: ${ps['risk_in_price']:.2f}")
            print(f"  Actual Risk: ${ps['actual_risk_dollars']:.2f}")
            print(f"  Max Allowed: ${ps['max_risk_dollars']:.2f}")
            print(f"  Valid: {'✅' if ps['position_size_valid'] else '❌'}")
    else:
        print(f"\n❌ Analysis failed: {analysis.get('error')}")

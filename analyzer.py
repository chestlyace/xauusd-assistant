import json
import re
from datetime import datetime
import pytz
import google.generativeai as genai
from config import *

class MarketAnalyzer:
    def __init__(self, analysis_mode='intraday'):
        """Initialize the AI analyzer with Gemini
        
        Args:
            analysis_mode: 'scalping' (M1-M15) or 'intraday' (H1-H4)
        """
        genai.configure(api_key=GEMINI_API_KEY)
        # Use latest stable model - better structured output adherence
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        self.analysis_count = 0
        self.analysis_mode = analysis_mode.lower()
        
        if self.analysis_mode not in ['scalping', 'intraday']:
            raise ValueError("analysis_mode must be 'scalping' or 'intraday'")
    
    def get_trading_session(self):
        """Determine current trading session (Gold is session-sensitive)"""
        utc_now = datetime.now(pytz.UTC)
        hour = utc_now.hour
        
        # Trading sessions (UTC)
        if 0 <= hour < 8:
            return "ASIA"
        elif 8 <= hour < 16:
            return "LONDON"
        elif 16 <= hour < 22:
            return "NEW_YORK"
        else:
            return "ASIA_LATE"
    
    def get_system_prompt(self):
        """Get mode-specific system prompt with strict definitions"""
        
        base_prompt = """You are an expert XAUUSD (Gold/USD) trader specializing in technical analysis and risk management.

Your analysis MUST follow this EXACT structure with machine-readable fields:

---ANALYSIS START---

Market Bias: [BULLISH / BEARISH / NEUTRAL]
Bias Strength: [1-10]

Trade Recommendation: [BUY / SELL / NO TRADE]
Confidence Score: [1-10]

Key Factors:
- Factor 1
- Factor 2
- Factor 3

Technical Setup:
[Brief technical analysis]

Entry Strategy:
[Specific entry criteria or "N/A" if NO TRADE]

Risk Management:
Stop Loss: [price level or "N/A"]
Take Profit 1: [price level or "N/A"]
Take Profit 2: [price level or "N/A"]
Risk Level: [LOW / MEDIUM / HIGH]

Invalidation:
[What would invalidate this setup]

---ANALYSIS END---

FIELD DEFINITIONS (Read Carefully):
• Bias Strength measures directional conviction (how strong is the trend/momentum)
• Confidence Score measures trade execution quality and safety (how good is the setup)
• High bias does NOT guarantee high confidence
• Example: Strong uptrend (Bias 9) but choppy price action (Confidence 4) = NO TRADE

CRITICAL RULES:
1. If there is no clear edge, you MUST output "Trade Recommendation: NO TRADE"
2. If Confidence Score < 6, you MUST output "Trade Recommendation: NO TRADE"
3. Never guess or force a trade when conditions are unclear
4. All price levels must be specific numbers (e.g., "4475.50"), never ranges or "N/A" for active trades
5. Be brutally honest about uncertainty
6. NO TRADE is a valid and often correct recommendation
"""

        if self.analysis_mode == 'scalping':
            mode_specific = """
ANALYSIS MODE: SCALPING (M1-M15 timeframes)

Your focus:
- Immediate price structure (support/resistance within $5-10 range)
- Very short-term bias (next 15min - 2 hours max)
- Quick entries and exits
- Tight stop losses (typically 0.1-0.3% of price)
- DO NOT provide long-term predictions
- DO NOT reference macro news unless it's happening RIGHT NOW
- Focus on: order flow, micro structure, immediate momentum

Scalping-specific requirements:
- Entry levels must be within $2-5 of current price
- Stops must be tight (max 0.3% loss)
- Take profits should be 1:1.5 to 1:2 risk/reward minimum
- If price is ranging or choppy: NO TRADE
- If spread is elevated or liquidity is thin: NO TRADE
- Scalping is preferred during LONDON and NEW_YORK sessions
- During low-liquidity sessions (ASIA, ASIA_LATE), be extremely selective
- HIGH risk level in scalping mode should almost always = NO TRADE
"""
        else:  # intraday
            mode_specific = """
ANALYSIS MODE: INTRADAY (H1-H4 timeframes)

Your focus:
- Intraday price structure (support/resistance within $20-50 range)
- Session-based bias (next 4-24 hours)
- Holding through minor pullbacks
- Moderate stop losses (typically 0.5-1% of price)
- Consider news events within the day
- Focus on: daily levels, session trends, key economic data

Intraday-specific requirements:
- Entry levels within $10-20 of current price
- Stops at logical levels (0.5-1% loss typical)
- Take profits at daily highs/lows or key levels
- If major news pending within 2 hours: consider NO TRADE
- Session context matters but less critical than scalping
"""

        return base_prompt + mode_specific
    
    def estimate_spread(self, current_price):
        """Rough spread estimation for gold (real spread needs broker API)"""
        # Gold spread typically 0.2-0.5 during normal hours, wider during Asia
        session = self.get_trading_session()
        
        if session in ['LONDON', 'NEW_YORK']:
            return 0.30  # Tighter spread
        else:
            return 0.60  # Wider spread in Asia
    
    def format_market_context(self, market_data):
        """Format market data for AI - pure facts, no interpretation"""
        current = market_data.get('current_price', {})
        indicators = market_data.get('technical_indicators', {})
        news = market_data.get('news', [])
        high_rel_news = market_data.get('high_relevance_news', [])
        
        if not current:
            return "ERROR: Price data unavailable"
        
        current_price = current['price']
        session = self.get_trading_session()
        spread = current.get('spread', self.estimate_spread(current_price))
        
        # Price section - just facts
        context = f"""CURRENT MARKET CONTEXT

Current Price: ${current_price:.2f}
Session: {session}
Estimated Spread: ${spread:.2f}
Timestamp: {current['timestamp']}
"""
        
        if 'change_percent' in current:
            context += f"24h Change: {current['change_percent']:+.2f}%\n"
        
        if 'high' in current and 'low' in current:
            context += f"Today High: ${current['high']:.2f}\n"
            context += f"Today Low: ${current['low']:.2f}\n"
            day_range = current['high'] - current['low']
            context += f"Daily Range: ${day_range:.2f}\n"
        
        # Technical indicators - pure numbers
        if indicators:
            context += f"\nTechnical Indicators:\n"
            context += f"SMA 20: ${indicators.get('sma_20', 'N/A')}\n"
            if indicators.get('sma_50'):
                context += f"SMA 50: ${indicators.get('sma_50')}\n"
            context += f"Recent Trend: {indicators.get('recent_trend', 'N/A')}\n"
            context += f"Volatility Index: {indicators.get('volatility', 'N/A')}\n"
            context += f"Price vs SMA20: {indicators.get('current_vs_sma20', 'N/A')}%\n"
        
        # News - only high relevance if scalping
        if self.analysis_mode == 'scalping':
            relevant_news = high_rel_news[:3]  # Only top 3 for scalping
            context += f"\nImmediate High-Impact News ({len(relevant_news)} items):\n"
        else:
            relevant_news = news[:8]  # More news for intraday
            context += f"\nRecent News ({len(news)} total, {len(high_rel_news)} high relevance):\n"
        
        for i, article in enumerate(relevant_news, 1):
            score = article.get('relevance_score', 0)
            context += f"{i}. [Rel: {score}] {article['title']}\n"
            if article.get('description') and len(article['description']) > 20:
                context += f"   {article['description'][:120]}...\n"
        
        return context
    
    def analyze_market(self, market_data):
        """Send data to AI and get structured analysis"""
        import time
        
        self.analysis_count += 1
        analysis_id = f"{self.analysis_mode}_{self.analysis_count}_{int(datetime.now().timestamp())}"
        
        print(f"\nAnalyzing market (mode: {self.analysis_mode.upper()}, ID: {analysis_id})...")
        
        system_prompt = self.get_system_prompt()
        market_context = self.format_market_context(market_data)
        
        full_prompt = f"{system_prompt}\n\n{market_context}"
        
        # Retry logic for 429 / Quota limits
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                # Get AI response
                response = self.model.generate_content(full_prompt)
                analysis_text = response.text
                
                # Parse into structured format
                structured = self.parse_structured_output(analysis_text, market_data, analysis_id)
                
                if structured.get('success'):
                    print(f"Analysis complete - Recommendation: {structured['trade_recommendation']}")
                
                return structured
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Quota exceeded" in error_str:
                    if attempt < max_retries - 1:
                        wait = retry_delay * (2 ** attempt)  # Exponential backoff 5, 10, 20
                        print(f"  ⚠️ Rate limit hit (429). Retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                
                print(f"Error during AI analysis: {e}")
                return {
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'analysis_id': f"error_{self.analysis_count}"
                }
    
    def parse_structured_output(self, analysis_text, market_data, analysis_id):
        """Parse AI output with strict field extraction and safety nets"""
        
        try:
            # Extract market bias
            bias_match = re.search(r'Market Bias:\s*(BULLISH|BEARISH|NEUTRAL)', analysis_text, re.IGNORECASE)
            market_bias = bias_match.group(1).upper() if bias_match else 'NEUTRAL'
            
            # Extract bias strength
            strength_match = re.search(r'Bias Strength:\s*(\d+)', analysis_text)
            bias_strength = int(strength_match.group(1)) if strength_match else 5
            bias_strength = max(1, min(10, bias_strength))  # Clamp to 1-10
            
            # Extract confidence score - STRICT
            conf_match = re.search(r'Confidence Score:\s*(\d+)', analysis_text)
            confidence = int(conf_match.group(1)) if conf_match else 0
            confidence = max(0, min(10, confidence))  # Clamp to 0-10
            
            # Extract trade recommendation
            trade_match = re.search(r'Trade Recommendation:\s*(BUY|SELL|NO TRADE)', analysis_text, re.IGNORECASE)
            trade_recommendation = trade_match.group(1).upper() if trade_match else 'NO TRADE'
            
            # SAFETY NET: Force NO TRADE if confidence < 6
            if confidence < 6:
                trade_recommendation = 'NO TRADE'
                print(f"  Safety override: Confidence {confidence} < 6, forcing NO TRADE")
            
            # Extract risk level
            risk_match = re.search(r'Risk Level:\s*(LOW|MEDIUM|HIGH)', analysis_text, re.IGNORECASE)
            risk_level = risk_match.group(1).upper() if risk_match else 'HIGH'
            
            # SAFETY NET: Scalping + HIGH risk = NO TRADE
            if self.analysis_mode == 'scalping' and risk_level == 'HIGH':
                trade_recommendation = 'NO TRADE'
                print(f"  Safety override: Scalping mode + HIGH risk, forcing NO TRADE")
            
            # Extract stop loss - ROBUST regex
            sl_match = re.search(r'Stop Loss:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            stop_loss = float(sl_match.group(1)) if sl_match else None
            
            # Extract take profits - ROBUST regex
            tp1_match = re.search(r'Take Profit 1:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            tp2_match = re.search(r'Take Profit 2:\s*\$?(\d+(?:\.\d+)?)', analysis_text)
            take_profit_1 = float(tp1_match.group(1)) if tp1_match else None
            take_profit_2 = float(tp2_match.group(1)) if tp2_match else None
            
            # SAFETY NET: If BUY/SELL but no stop loss, force NO TRADE
            if trade_recommendation in ['BUY', 'SELL'] and not stop_loss:
                trade_recommendation = 'NO TRADE'
                print(f"  Safety override: {trade_recommendation} without stop loss, forcing NO TRADE")
            
            # Extract key factors
            factors_section = re.search(r'Key Factors:(.*?)(?=Technical Setup:|$)', analysis_text, re.DOTALL)
            key_factors = []
            if factors_section:
                factor_lines = factors_section.group(1).strip().split('\n')
                key_factors = [line.strip('- ').strip() for line in factor_lines if line.strip().startswith('-')]
            
            # Extract invalidation
            invalidation_match = re.search(r'Invalidation:(.*?)(?=---|$)', analysis_text, re.DOTALL)
            invalidation = invalidation_match.group(1).strip() if invalidation_match else "Not specified"
            
            current_price = market_data.get('current_price', {}).get('price')
            session = self.get_trading_session()
            
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
                
                # Trade levels
                'stop_loss': stop_loss,
                'take_profit_1': take_profit_1,
                'take_profit_2': take_profit_2,
                
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
            print(f"Error parsing analysis: {e}")
            return {
                'success': False,
                'error': f"Parsing failed: {e}",
                'raw_output': analysis_text,
                'timestamp': datetime.now().isoformat(),
                'analysis_id': analysis_id
            }
    
    def should_alert(self, analysis):
        """Strict gating - only alert on actionable, high-confidence trades"""
        if not analysis.get('success'):
            return False
        
        trade_rec = analysis.get('trade_recommendation', 'NO TRADE')
        confidence = analysis.get('confidence', 0)
        risk_level = analysis.get('risk_level', 'HIGH')
        
        # NEVER alert on NO TRADE
        if trade_rec == 'NO TRADE':
            return False
        
        # Must meet confidence threshold
        if confidence < CONFIDENCE_THRESHOLD:
            return False
        
        # For scalping, require higher confidence
        if self.analysis_mode == 'scalping' and confidence < 7:
            return False
        
        # Scalping + HIGH risk = no alert
        if self.analysis_mode == 'scalping' and risk_level == 'HIGH':
            return False
        
        # Must have proper stop loss
        if not analysis.get('stop_loss'):
            return False
        
        return True
    
    def generate_summary(self, analysis):
        """Generate clean summary - emojis only here, not in logs"""
        if not analysis.get('success'):
            return f"Analysis failed: {analysis.get('error', 'Unknown error')}"
        
        trade_rec = analysis['trade_recommendation']
        confidence = analysis['confidence']
        price = analysis.get('current_price', 0)
        
        # Emojis only in display
        if trade_rec == 'BUY':
            emoji = "📈"
        elif trade_rec == 'SELL':
            emoji = "📉"
        else:
            emoji = "⏸️"
        
        summary = f"""
{emoji} XAUUSD Analysis [{analysis['analysis_mode'].upper()}] | Session: {analysis.get('session', 'N/A')}
{'='*60}
ID: {analysis['analysis_id']}
Trade Signal: {trade_rec}
Confidence: {confidence}/10
Market Bias: {analysis['market_bias']} (Strength: {analysis['bias_strength']}/10)
Current Price: ${price:.2f}
Risk Level: {analysis['risk_level']}
"""
        
        if trade_rec != 'NO TRADE':
            summary += f"\nEntry Zone: ~${price:.2f}"
            if analysis.get('stop_loss'):
                risk_amount = abs(price - analysis['stop_loss'])
                summary += f"\nStop Loss: ${analysis['stop_loss']:.2f} (Risk: ${risk_amount:.2f})"
            if analysis.get('take_profit_1'):
                reward = abs(analysis['take_profit_1'] - price)
                rr_ratio = reward / risk_amount if risk_amount > 0 else 0
                summary += f"\nTarget 1: ${analysis['take_profit_1']:.2f} (R:R {rr_ratio:.2f})"
            if analysis.get('take_profit_2'):
                summary += f"\nTarget 2: ${analysis['take_profit_2']:.2f}"
        
        if analysis.get('key_factors'):
            summary += f"\n\nKey Factors:"
            for factor in analysis['key_factors'][:3]:
                summary += f"\n  • {factor}"
        
        summary += f"\n\nInvalidation: {analysis.get('invalidation', 'N/A')[:100]}"
        summary += f"\nTimestamp: {analysis['timestamp']}"
        
        return summary


# Test the analyzer
if __name__ == "__main__":
    from data_collector import DataCollector
    
    print("Testing Production-Grade AI Analyzer")
    print("="*70)
    
    # Test both modes
    import time
    for mode in ['intraday', 'scalping']:
        if mode == 'scalping':
            print("\nWaiting 15s to respect API rate limits...")
            time.sleep(15)
            
        print(f"\n{'='*70}")
        print(f"Testing {mode.upper()} mode")
        print('='*70)
        
        # Collect market data
        collector = DataCollector()
        market_data = collector.get_market_data()
        
        # Analyze with AI
        analyzer = MarketAnalyzer(analysis_mode=mode)
        analysis = analyzer.analyze_market(market_data)
        
        if analysis.get('success'):
            print("\n" + analyzer.generate_summary(analysis))
            
            print(f"\nParsed Fields (Verification):")
            print(f"  Analysis ID: {analysis['analysis_id']}")
            print(f"  Trade Recommendation: {analysis['trade_recommendation']}")
            print(f"  Confidence: {analysis['confidence']}/10")
            print(f"  Bias Strength: {analysis['bias_strength']}/10")
            print(f"  Market Bias: {analysis['market_bias']}")
            print(f"  Risk Level: {analysis['risk_level']}")
            print(f"  Stop Loss: ${analysis.get('stop_loss', 'N/A')}")
            print(f"  TP1: ${analysis.get('take_profit_1', 'N/A')}")
            print(f"  Session: {analysis['session']}")
            
            if analyzer.should_alert(analysis):
                print("\n🔔 ALERT: This signal meets threshold criteria")
            else:
                if analysis['trade_recommendation'] == 'NO TRADE':
                    reason = "NO TRADE recommendation"
                elif analysis['confidence'] < 6:
                    reason = f"Low confidence ({analysis['confidence']}/10)"
                elif mode == 'scalping' and analysis['risk_level'] == 'HIGH':
                    reason = "Scalping mode + HIGH risk"
                else:
                    reason = f"Below threshold (conf: {analysis['confidence']}, threshold: {CONFIDENCE_THRESHOLD})"
                print(f"\n⏸️  NO ALERT: {reason}")
        else:
            print(f"\nAnalysis failed: {analysis.get('error')}")
        
        print("\n" + "="*70)
#!/usr/bin/env python3
"""
VISUAL SIGNAL BOT  –  COMPLETE SYSTEM
══════════════════════════════════════
Integrates:
  1. Precise timeframe-specific chart generation
  2. Candlestick Trading Bible pattern detection
  3. Gemini Vision AI analysis (chart image + data)
  4. Future entry prediction (when no current setup exists)
  5. Telegram signal with chart image attached

Usage:
  python3 visual_signal_bot.py

pip3 install --user google-generativeai python-telegram-bot mplfinance Pillow pandas numpy
"""

import asyncio
import json
import re
import os
from datetime import datetime, timedelta
from PIL import Image

import google.generativeai as genai
from google.api_core import exceptions
from telegram import Bot

# ── Your own modules ──────────────────────────────────────────
from chart_generator          import ChartGenerator
from candlestick_bible_detector import CandlestickBibleDetector
from data_collector           import DataCollector     # your existing collector
from config                   import GEMINI_API_KEY, GEMINI_API_KEYS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# ─────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────

TIMEFRAME          = 'M15'     # Change to M5, H1, H4, etc.
SYMBOL             = 'XAUUSD'
CHECK_INTERVAL_SEC = 900       # How often to scan
MIN_SIGNAL_QUALITY = 7         # Only send signals scoring 7+ / 10
RISK_PERCENT       = 5         # % of account risked per trade
ACCOUNT_SIZE       = 100       # Account size in USD

# ─────────────────────────────────────────────────────────────


class VisualSignalBot:
    """
    The complete XAUUSD signal bot with visual AI analysis.
    """

    def __init__(self):
        # ── Setup API keys and remove duplicates ────────────────
        raw_keys = GEMINI_API_KEYS if GEMINI_API_KEYS else [GEMINI_API_KEY]
        self.api_keys = []
        for k in raw_keys:
            if k and k not in self.api_keys:
                clean_k = k.strip().rstrip('>')
                if clean_k:
                    self.api_keys.append(clean_k)
        
        self.current_key_index = 0
        
        # Configure first key
        if self.api_keys:
            genai.configure(api_key=self.api_keys[self.current_key_index])
            
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

        # ── Sub-components ────────────────────
        self.collector  = DataCollector()
        self.chart_gen  = ChartGenerator(output_dir='/tmp/charts')
        self.detector   = CandlestickBibleDetector()
        self.telegram   = Bot(token=TELEGRAM_BOT_TOKEN)

        # ── State ─────────────────────────────
        self.last_signal_time  = None
        self.active_setups     = {}
        self.daily_signals     = 0
        self.daily_pnl         = 0.0

        os.makedirs('/tmp/charts', exist_ok=True)

        print('═' * 60)
        print(' VISUAL SIGNAL BOT  –  XAUUSD Trading Bible System')
        print('═' * 60)
        print(f' Timeframe : {TIMEFRAME}')
        print(f' Symbol    : {SYMBOL}')
        print(f' Interval  : {CHECK_INTERVAL_SEC}s')
        print(f' Min Score : {MIN_SIGNAL_QUALITY}/10')
        print(f' API Keys  : {len(self.api_keys)} loaded')
        print('═' * 60)

    # ─────────────────────────────────────────────────────────
    #  MAIN LOOP
    # ─────────────────────────────────────────────────────────

    async def run(self):
        """Continuous scanning loop."""
        await self._send_telegram_text('🤖 *Visual Signal Bot started*\nXAUUSD | Trading Bible System', parse_mode='Markdown')

        while True:
            try:
                print(f'\n[{datetime.now().strftime("%H:%M:%S")}] Scanning market...')
                await self._scan()
            except Exception as e:
                print(f'❌ Scan error: {e}')
            await asyncio.sleep(CHECK_INTERVAL_SEC)

    # ─────────────────────────────────────────────────────────
    #  SCAN
    # ─────────────────────────────────────────────────────────

    async def _scan(self):
        # 1. Collect data
        data = self.collector.get_market_data()
        if not data or not data.get('price_history'):
            print('  ⚠️  No market data received')
            return

        price_data    = data['price_history']
        current_price = data['current_price']['price']
        print(f'  Price: ${current_price:.2f}')

        # 2. Detect Bible patterns
        bible = self.detector.analyze(price_data)
        patterns      = bible.get('patterns', [])
        market_type   = bible.get('market_type', 'unknown')
        trend         = bible.get('trend_direction', 'neutral')
        supports      = bible.get('supports', [])
        resistances   = bible.get('resistances', [])
        last_atr      = bible.get('last_atr', 5)

        print(f'  Market: {market_type}  |  Trend: {trend}')
        if patterns:
            print(f'  Patterns: {[p.name for p in patterns]}')

        # 3. Generate chart (with detected patterns highlighted)
        key_levels = {'support': supports, 'resistance': resistances}
        chart_path = self.chart_gen.generate(
            price_data      = price_data,
            timeframe       = TIMEFRAME,
            symbol          = SYMBOL,
            detected_patterns = [
                {'name': p.name, 'direction': p.direction,
                 'bar_index': p.bar_index, 'price': p.price,
                 'atr': p.atr}
                for p in patterns
            ],
            key_levels  = key_levels,
            future_zone = None   # will add after AI analysis
        )

        if not chart_path:
            print('  ⚠️  Chart generation failed')
            return

        # 4. Vision AI analysis (data + chart image + Bible knowledge)
        analysis = await self._ai_analyze(
            data, bible, chart_path, current_price
        )

        if not analysis:
            print('  ⚠️  AI analysis failed')
            return

        signal_type = analysis.get('signal_type', 'NONE')
        quality     = analysis.get('quality_score', 0)

        print(f'  AI Signal: {signal_type}  |  Quality: {quality}/10')

        # 5a. IMMEDIATE entry signal
        if signal_type in ('BUY', 'SELL') and quality >= MIN_SIGNAL_QUALITY:
            print(f'  🟢 SIGNAL FOUND → sending...')
            await self._send_signal(analysis, chart_path, current_price)

        # 5b. FUTURE setup prediction (no immediate entry but setup forming)
        elif signal_type == 'WATCH' or (quality >= 5 and signal_type not in ('NONE',)):
            print(f'  ⏳ Future setup predicted → updating chart & sending...')

            # Re-generate chart with the future zone highlighted
            future_zone = analysis.get('future_zone')
            if future_zone:
                chart_path = self.chart_gen.generate(
                    price_data      = price_data,
                    timeframe       = TIMEFRAME,
                    symbol          = SYMBOL,
                    detected_patterns = [
                        {'name': p.name, 'direction': p.direction,
                         'bar_index': p.bar_index, 'price': p.price,
                         'atr': p.atr}
                        for p in patterns
                    ],
                    key_levels  = key_levels,
                    future_zone = future_zone
                )
            await self._send_future_setup(analysis, chart_path, current_price)

        else:
            print(f'  ⏸  No signal (quality too low or neutral)')

    # ─────────────────────────────────────────────────────────
    #  VISION AI ANALYSIS
    # ─────────────────────────────────────────────────────────

    async def _ai_analyze(self, market_data, bible, chart_path, current_price) -> dict:
        """
        Send chart image + structured data to Gemini (with API rotation).
        """
        try:
            chart_image = Image.open(chart_path)
            prompt      = self._build_prompt(market_data, bible, current_price)
            
            max_attempts = len(self.api_keys)
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    response = self.model.generate_content([prompt, chart_image])
                    return self._parse_response(response.text, current_price, bible)
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Check for rate limit, quota, invalid keys, or credential fallbacks
                    is_rotatable_error = (
                        isinstance(e, exceptions.ResourceExhausted) or 
                        isinstance(e, exceptions.InvalidArgument) or
                        isinstance(e, exceptions.Unauthenticated) or
                        "429" in error_msg or 
                        "quota" in error_msg or 
                        "credentials" in error_msg or
                        "api key not valid" in error_msg or
                        "invalid" in error_msg
                    )
                    
                    if is_rotatable_error and attempt < max_attempts - 1:
                        print(f"  ⚠️  API Key {self.current_key_index} failure. Rotating...")
                        if self._rotate_api_key():
                            continue
                    
                    print(f"  ❌ AI Vision Error: {e}")
                    break
            
            return None

        except Exception as e:
            print(f'  AI fatal error: {e}')
            return None

    def _rotate_api_key(self):
        """Switch to the next available API key"""
        if not self.api_keys or len(self.api_keys) <= 1:
            return False
            
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_key_index]
        
        mask_key = f"...{new_key[-4:]}" if len(new_key) > 4 else "****"
        print(f"  ⟳ Rotated to API Key index {self.current_key_index} ({mask_key})")
        
        genai.configure(api_key=new_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
        return True

    def _build_prompt(self, market_data, bible, price) -> str:
        """
        Comprehensive prompt embedding full Trading Bible knowledge.
        """
        patterns_text = '\n'.join(
            f"  • {p.name} ({p.direction}, quality {p.quality}/10) – "
            f"confluence: {', '.join(p.confluence) if p.confluence else 'none'}"
            for p in bible.get('patterns', [])
        ) or '  None detected yet'

        return f"""
You are a professional XAUUSD trader trained in The Candlestick Trading Bible methodology.
Analyze the chart image together with the data below.

━━━━ MARKET DATA ━━━━
Symbol       : XAUUSD
Timeframe    : {TIMEFRAME}
Current Price: ${price:.2f}
Market Type  : {bible.get('market_type','unknown')}
Trend        : {bible.get('trend_direction','neutral')}
Supports     : {bible.get('supports',[])}
Resistances  : {bible.get('resistances',[])}
ATR          : {bible.get('last_atr',0):.2f}

━━━━ DETECTED PATTERNS (from code) ━━━━
{patterns_text}

━━━━ TRADING BIBLE RULES TO APPLY ━━━━
1. TREND: Identify if market is trending up/down, ranging, or choppy.
   - Higher highs + higher lows = uptrend
   - Lower highs + lower lows = downtrend
   - Horizontal S/R = ranging

2. LEVEL: Find the key level the signal is at:
   - Previous swing points (support/resistance)
   - 21 EMA as dynamic S/R
   - 50% / 61% Fibonacci retracement areas

3. SIGNAL: Confirm one of these patterns from the book:
   - Pin Bar: long tail rejection at key level (p.81)
   - Bullish/Bearish Engulfing at S/R (p.109)
   - Inside Bar: consolidation → breakout direction (p.137)
   - Inside Bar False Breakout: stop-hunt reversal (p.148)
   - Doji at extremes: indecision / reversal (p.20)
   - Morning/Evening Star: 3-candle reversal (p.28/31)
   - Tweezers: double-level rejection (p.43)

4. CONFLUENCE: Rate how many factors align:
   - With trend (most important)
   - At clear S/R level
   - At 21 EMA
   - Pin bar tail points away from S/R
   - R:R must be minimum 2:1

5. ENTRY OPTIONS:
   - Aggressive: enter at close of signal candle
   - Conservative: wait for 50% retracement of signal candle

━━━━ YOUR TASK ━━━━
Looking at BOTH the chart image AND the data above:

A) If there is a HIGH PROBABILITY setup RIGHT NOW (quality ≥ 7/10):
   → signal_type = "BUY" or "SELL"
   → Provide entry, stop loss, take profit 1, take profit 2

B) If NO immediate entry but a setup is forming / price approaching a key level:
   → signal_type = "WATCH"
   → Describe the setup that will trigger, the condition needed, and the zone to watch
   → future_zone: {{"direction":"BUY/SELL", "zone_low":float, "zone_high":float, "label":"short text"}}

C) If market is choppy or no clear setup:
   → signal_type = "NONE"

━━━━ RESPOND IN THIS JSON FORMAT ONLY ━━━━
{{
  "signal_type": "BUY" | "SELL" | "WATCH" | "NONE",
  "quality_score": 1-10,
  "direction": "BUY" | "SELL" | "NEUTRAL",
  "market_assessment": "one sentence about market structure",
  "pattern_found": "name of main pattern or 'none'",
  "pattern_description": "what you see on the chart",
  "entry_price": float_or_null,
  "stop_loss": float_or_null,
  "take_profit_1": float_or_null,
  "take_profit_2": float_or_null,
  "risk_reward": float_or_null,
  "entry_type": "aggressive" | "conservative" | null,
  "confluence_factors": ["list", "of", "factors"],
  "future_zone": {{
    "direction": "BUY" | "SELL",
    "zone_low": float,
    "zone_high": float,
    "label": "short label"
  }} or null,
  "watch_condition": "what must happen for the setup to trigger (if WATCH)",
  "key_insight": "most important observation from the chart",
  "warnings": ["any red flags"]
}}
"""

    def _parse_response(self, text, current_price, bible) -> dict:
        """Extract JSON from AI response."""
        try:
            text  = re.sub(r'```json|```', '', text).strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass

        # Fallback minimal dict
        return {
            'signal_type': 'NONE',
            'quality_score': 0,
            'direction': 'NEUTRAL',
            'market_assessment': text[:200],
            'pattern_found': 'unknown',
        }

    # ─────────────────────────────────────────────────────────
    #  TELEGRAM  –  IMMEDIATE SIGNAL
    # ─────────────────────────────────────────────────────────

    async def _send_signal(self, a, chart_path, price):
        """Send a live entry signal with chart image."""

        direction = a.get('direction', '?')
        emoji     = '🟢' if direction == 'BUY' else '🔴'
        entry     = a.get('entry_price')   or price
        sl        = a.get('stop_loss')
        tp1       = a.get('take_profit_1')
        tp2       = a.get('take_profit_2')
        rr        = a.get('risk_reward')
        quality   = a.get('quality_score', 0)
        pattern   = a.get('pattern_found', 'Pattern')
        entry_type = (a.get('entry_type') or 'aggressive').upper()

        # Risk calc
        risk_usd  = round(ACCOUNT_SIZE * RISK_PERCENT / 100, 2)
        sl_dist   = abs(entry - sl) if sl else 0
        reward    = sl_dist * (rr or 2)

        caption = (
            f"{emoji} *{direction} SIGNAL  –  {SYMBOL}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📐 *Pattern*  : {pattern}\n"
            f"📊 *Quality*  : {quality}/10\n"
            f"⏱ *Timeframe*: {TIMEFRAME}  |  {entry_type}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎯 *Entry*    : `${entry:.2f}`\n"
            f"🛡 *Stop Loss*: `${sl:.2f}`\n"
        )
        if tp1:
            caption += f"✅ *TP 1*     : `${tp1:.2f}`\n"
        if tp2:
            caption += f"✅ *TP 2*     : `${tp2:.2f}`\n"
        if rr:
            caption += f"⚖️ *R:R*      : `{rr:.1f}:1`\n"
        caption += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Insight* : {a.get('key_insight','')}\n"
            f"📈 *Market*  : {a.get('market_assessment','')}\n"
        )
        conf = a.get('confluence_factors', [])
        if conf:
            caption += f"🔗 *Confluence*:\n" + '\n'.join(f'  {c}' for c in conf) + '\n'
        warnings = a.get('warnings', [])
        if warnings:
            caption += '⚠️ *Warnings*:\n' + '\n'.join(f'  • {w}' for w in warnings) + '\n'

        await self._send_photo_signal(chart_path, caption)
        self.last_signal_time = datetime.now()
        self.daily_signals   += 1
        print(f'  ✅ Signal sent: {direction} at ${entry:.2f}')

    # ─────────────────────────────────────────────────────────
    #  TELEGRAM  –  FUTURE SETUP
    # ─────────────────────────────────────────────────────────

    async def _send_future_setup(self, a, chart_path, price):
        """Send a 'watch for this setup' alert with chart image."""

        direction = a.get('direction', a.get('future_zone', {}).get('direction', '?'))
        emoji     = '⏳'
        fz        = a.get('future_zone', {})
        quality   = a.get('quality_score', 0)
        pattern   = a.get('pattern_found', 'Setup forming')

        caption = (
            f"{emoji} *SETUP FORMING  –  {SYMBOL}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📐 *Pattern*   : {pattern}\n"
            f"📊 *Quality*   : {quality}/10  (watch, not entry yet)\n"
            f"⏱ *Timeframe* : {TIMEFRAME}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📍 *Watch Zone* : {direction}\n"
        )
        if fz:
            caption += (
                f"   Zone Low  : `${fz.get('zone_low', 0):.2f}`\n"
                f"   Zone High : `${fz.get('zone_high', 0):.2f}`\n"
            )

        condition = a.get('watch_condition', '')
        if condition:
            caption += (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔔 *Trigger Condition*:\n"
                f"_{condition}_\n"
            )

        caption += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Insight* : {a.get('key_insight','')}\n"
            f"📈 *Market*  : {a.get('market_assessment','')}\n"
        )
        conf = a.get('confluence_factors', [])
        if conf:
            caption += '🔗 *Building confluence*:\n' + '\n'.join(f'  {c}' for c in conf) + '\n'

        await self._send_photo_signal(chart_path, caption)
        print(f'  ⏳ Future setup sent')

    # ─────────────────────────────────────────────────────────
    #  TELEGRAM HELPERS
    # ─────────────────────────────────────────────────────────

    async def _send_photo_signal(self, chart_path, caption):
        """Send photo + caption to Telegram, fall back to text if photo fails."""
        try:
            # Telegram captions max 1024 chars
            if len(caption) > 1024:
                caption = caption[:1020] + '...'

            with open(chart_path, 'rb') as f:
                await self.telegram.send_photo(
                    chat_id   = TELEGRAM_CHAT_ID,
                    photo     = f,
                    caption   = caption,
                    parse_mode = 'Markdown'
                )
        except Exception as e:
            print(f'  ⚠️  Photo send failed ({e}), sending text only')
            await self._send_telegram_text(caption, parse_mode='Markdown')

    async def _send_telegram_text(self, text, parse_mode=None):
        try:
            await self.telegram.send_message(
                chat_id    = TELEGRAM_CHAT_ID,
                text       = text,
                parse_mode = parse_mode
            )
        except Exception as e:
            print(f'  Telegram error: {e}')


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    bot = VisualSignalBot()
    asyncio.run(bot.run())

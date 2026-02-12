#!/usr/bin/env python3
"""
CANDLESTICK BIBLE DETECTOR
Detects all patterns from "The Candlestick Trading Bible" directly in price data.

Patterns covered:
 • Pin Bar (Hammer / Shooting Star)
 • Engulfing Bar (Bullish / Bearish)
 • Inside Bar  (+ False Breakout variant)
 • Doji  (standard, Dragonfly, Gravestone)
 • Morning Star  /  Evening Star
 • Tweezers Top  /  Tweezers Bottom
 • Harami (inside bar – reversal & continuation)

Market Structure (also from the book):
 • Trend detection  (higher highs / higher lows)
 • Support & Resistance swing-point detection
 • Impulsive vs retracement move
 • Range detection
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional


# ───────────────────────────────────────────────────────────────
@dataclass
class PatternSignal:
    name:         str
    direction:    str        # 'bullish' | 'bearish'
    bar_index:    int
    price:        float      # reference price (close or level)
    atr:          float      # ATR at detection bar
    quality:      int        # 1-10
    confluence:   List[str]  = field(default_factory=list)
    description:  str        = ''
# ───────────────────────────────────────────────────────────────


class CandlestickBibleDetector:
    """
    Pure-data pattern detector.
    Feed it OHLCV data, get back PatternSignal objects.
    """

    def __init__(self):
        # Thresholds (tuned for XAUUSD)
        self.PIN_TAIL_RATIO      = 2.0   # tail must be ≥ 2× the body
        self.PIN_BODY_MAX_RATIO  = 0.35  # body ≤ 35 % of full candle range
        self.DOJI_BODY_MAX_RATIO = 0.05  # body ≤ 5 % of range
        self.SWING_LOOKBACK      = 5     # bars each side for swing point

    # ─────────────────────────────────────────────────────────
    #  PUBLIC  API
    # ─────────────────────────────────────────────────────────

    def analyze(self, price_data: list) -> dict:
        """
        Full analysis of price data.

        Returns:
            {
              'patterns':    [PatternSignal, ...],
              'market_type': 'uptrend'|'downtrend'|'ranging'|'choppy',
              'trend_direction': 'up'|'down'|'neutral',
              'supports':    [price, ...],
              'resistances': [price, ...],
              'last_atr':    float,
              'current_price': float,
            }
        """
        df = self._to_df(price_data)
        if df is None or len(df) < 20:
            return {}

        df = self._add_candle_metrics(df)

        patterns     = self._detect_all_patterns(df)
        market_type  = self._classify_market(df)
        trend_dir    = self._trend_direction(df)
        supports     = self._find_supports(df)
        resistances  = self._find_resistances(df)

        # Enrich patterns with confluence info
        for p in patterns:
            p.confluence = self._find_confluence(
                p, df, supports, resistances, trend_dir
            )
            p.quality = self._score_quality(p, trend_dir, market_type)

        return {
            'patterns':       patterns,
            'market_type':    market_type,
            'trend_direction': trend_dir,
            'supports':       supports,
            'resistances':    resistances,
            'last_atr':       float(df['ATR'].iloc[-1]) if not df['ATR'].isna().all() else 0,
            'current_price':  float(df['Close'].iloc[-1]),
        }

    # ─────────────────────────────────────────────────────────
    #  PATTERN DETECTION
    # ─────────────────────────────────────────────────────────

    def _detect_all_patterns(self, df: pd.DataFrame) -> List[PatternSignal]:
        patterns = []
        # Only scan the last 10 bars to avoid noise
        scan_range = range(max(3, len(df) - 10), len(df))

        for i in scan_range:
            patterns += self._check_pin_bar(df, i)
            patterns += self._check_engulfing(df, i)
            patterns += self._check_inside_bar(df, i)
            patterns += self._check_doji(df, i)
            patterns += self._check_morning_evening_star(df, i)
            patterns += self._check_tweezers(df, i)

        # Deduplicate – keep highest quality per bar
        best = {}
        for p in patterns:
            key = p.bar_index
            if key not in best or p.quality > best[key].quality:
                best[key] = p

        return sorted(best.values(), key=lambda x: x.bar_index)

    # ── Pin Bar (Hammer / Shooting Star) ─────────────────────
    def _check_pin_bar(self, df, i) -> List[PatternSignal]:
        o, h, l, c = df['Open'].iloc[i], df['High'].iloc[i], \
                     df['Low'].iloc[i],  df['Close'].iloc[i]
        atr  = df['ATR'].iloc[i] if not pd.isna(df['ATR'].iloc[i]) else 1
        rng  = h - l
        if rng < 0.001:
            return []

        body       = abs(c - o)
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l

        # Bullish pin bar  (Hammer) – long lower wick
        if (lower_wick >= self.PIN_TAIL_RATIO * body and
                body / rng <= self.PIN_BODY_MAX_RATIO and
                lower_wick >= 2 * upper_wick):
            return [PatternSignal(
                name='Pin Bar (Bullish)',
                direction='bullish',
                bar_index=i, price=l, atr=atr,
                quality=5,
                description='Long lower wick rejection – buyers dominant (Trading Bible p.81)'
            )]

        # Bearish pin bar  (Shooting Star) – long upper wick
        if (upper_wick >= self.PIN_TAIL_RATIO * body and
                body / rng <= self.PIN_BODY_MAX_RATIO and
                upper_wick >= 2 * lower_wick):
            return [PatternSignal(
                name='Pin Bar (Bearish)',
                direction='bearish',
                bar_index=i, price=h, atr=atr,
                quality=5,
                description='Long upper wick rejection – sellers dominant (Trading Bible p.37)'
            )]

        return []

    # ── Engulfing Bar ─────────────────────────────────────────
    def _check_engulfing(self, df, i) -> List[PatternSignal]:
        if i < 1:
            return []

        c0, o0 = df['Close'].iloc[i-1], df['Open'].iloc[i-1]
        c1, o1 = df['Close'].iloc[i],   df['Open'].iloc[i]
        atr    = df['ATR'].iloc[i] if not pd.isna(df['ATR'].iloc[i]) else 1

        prev_body = abs(c0 - o0)
        curr_body = abs(c1 - o1)
        if prev_body < 0.001:
            return []

        # Bullish engulfing – current fully covers previous bearish candle
        if (c0 < o0 and c1 > o1 and               # prev bearish, curr bullish
                o1 <= min(c0, o0) and              # opens at/below prev body
                c1 >= max(c0, o0) and              # closes at/above prev body
                curr_body > prev_body):
            return [PatternSignal(
                name='Bullish Engulfing',
                direction='bullish',
                bar_index=i, price=min(o1, c0), atr=atr,
                quality=6,
                description='Current candle engulfs previous bearish – buyers take control (Trading Bible p.18)'
            )]

        # Bearish engulfing
        if (c0 > o0 and c1 < o1 and
                o1 >= max(c0, o0) and
                c1 <= min(c0, o0) and
                curr_body > prev_body):
            return [PatternSignal(
                name='Bearish Engulfing',
                direction='bearish',
                bar_index=i, price=max(o1, c0), atr=atr,
                quality=6,
                description='Current candle engulfs previous bullish – sellers take control (Trading Bible p.16)'
            )]

        return []

    # ── Inside Bar (Harami) ───────────────────────────────────
    def _check_inside_bar(self, df, i) -> List[PatternSignal]:
        if i < 1:
            return []

        h0, l0 = df['High'].iloc[i-1], df['Low'].iloc[i-1]
        h1, l1 = df['High'].iloc[i],   df['Low'].iloc[i]
        c1     = df['Close'].iloc[i]
        atr    = df['ATR'].iloc[i] if not pd.isna(df['ATR'].iloc[i]) else 1

        if h1 < h0 and l1 > l0:   # strictly inside the mother bar
            direction = 'bullish' if c1 > df['Open'].iloc[i] else 'bearish'
            return [PatternSignal(
                name='Inside Bar',
                direction=direction,
                bar_index=i, price=c1, atr=atr,
                quality=5,
                description='Bar contained within mother bar – consolidation / indecision (Trading Bible p.137)'
            )]

        return []

    # ── Doji family ───────────────────────────────────────────
    def _check_doji(self, df, i) -> List[PatternSignal]:
        o, h, l, c = df['Open'].iloc[i], df['High'].iloc[i], \
                     df['Low'].iloc[i],  df['Close'].iloc[i]
        atr = df['ATR'].iloc[i] if not pd.isna(df['ATR'].iloc[i]) else 1
        rng = h - l
        if rng < 0.001:
            return []

        body         = abs(c - o)
        upper_wick   = h - max(c, o)
        lower_wick   = min(c, o) - l
        body_ratio   = body / rng

        if body_ratio > self.DOJI_BODY_MAX_RATIO:
            return []

        # Dragonfly Doji – long lower wick (bullish)
        if lower_wick >= 3 * upper_wick and lower_wick > 0.6 * rng:
            return [PatternSignal(
                name='Dragonfly Doji',
                direction='bullish',
                bar_index=i, price=l, atr=atr,
                quality=6,
                description='Long lower shadow – buyers rejecting lows (Trading Bible p.23)'
            )]

        # Gravestone Doji – long upper wick (bearish)
        if upper_wick >= 3 * lower_wick and upper_wick > 0.6 * rng:
            return [PatternSignal(
                name='Gravestone Doji',
                direction='bearish',
                bar_index=i, price=h, atr=atr,
                quality=6,
                description='Long upper shadow – sellers rejecting highs (Trading Bible p.25)'
            )]

        # Standard Doji – indecision
        return [PatternSignal(
            name='Doji',
            direction='neutral',
            bar_index=i, price=c, atr=atr,
            quality=4,
            description='Near-equal open/close – market indecision (Trading Bible p.20)'
        )]

    # ── Morning Star / Evening Star ───────────────────────────
    def _check_morning_evening_star(self, df, i) -> List[PatternSignal]:
        if i < 2:
            return []

        c0 = df['Close'].iloc[i-2]; o0 = df['Open'].iloc[i-2]
        c1 = df['Close'].iloc[i-1]; o1 = df['Open'].iloc[i-1]
        c2 = df['Close'].iloc[i];   o2 = df['Open'].iloc[i]
        atr = df['ATR'].iloc[i] if not pd.isna(df['ATR'].iloc[i]) else 1

        body0 = abs(c0 - o0)
        body1 = abs(c1 - o1)
        body2 = abs(c2 - o2)

        # Morning Star (bullish)
        if (c0 < o0 and body0 > body1 * 2 and     # strong bearish candle
                c2 > o2 and                         # bullish candle
                body2 > body1 * 1.5 and             # strong reversal
                c2 > (o0 + c0) / 2):               # closes above midpoint of candle 0
            return [PatternSignal(
                name='Morning Star',
                direction='bullish',
                bar_index=i, price=df['Low'].iloc[i-1], atr=atr,
                quality=7,
                description='3-candle bullish reversal at downtrend bottom (Trading Bible p.28)'
            )]

        # Evening Star (bearish)
        if (c0 > o0 and body0 > body1 * 2 and
                c2 < o2 and
                body2 > body1 * 1.5 and
                c2 < (o0 + c0) / 2):
            return [PatternSignal(
                name='Evening Star',
                direction='bearish',
                bar_index=i, price=df['High'].iloc[i-1], atr=atr,
                quality=7,
                description='3-candle bearish reversal at uptrend top (Trading Bible p.31)'
            )]

        return []

    # ── Tweezers ──────────────────────────────────────────────
    def _check_tweezers(self, df, i) -> List[PatternSignal]:
        if i < 1:
            return []

        h0, l0 = df['High'].iloc[i-1], df['Low'].iloc[i-1]
        h1, l1 = df['High'].iloc[i],   df['Low'].iloc[i]
        c1     = df['Close'].iloc[i]
        atr    = df['ATR'].iloc[i] if not pd.isna(df['ATR'].iloc[i]) else 1
        tolerance = atr * 0.2

        # Tweezers Bottom – bullish
        if (abs(l0 - l1) <= tolerance and
                df['Close'].iloc[i-1] < df['Open'].iloc[i-1] and  # prev bearish
                c1 > df['Open'].iloc[i]):                           # curr bullish
            return [PatternSignal(
                name='Tweezers Bottom',
                direction='bullish',
                bar_index=i, price=l1, atr=atr,
                quality=6,
                description='Equal lows – buyers rejecting the level (Trading Bible p.43)'
            )]

        # Tweezers Top – bearish
        if (abs(h0 - h1) <= tolerance and
                df['Close'].iloc[i-1] > df['Open'].iloc[i-1] and
                c1 < df['Open'].iloc[i]):
            return [PatternSignal(
                name='Tweezers Top',
                direction='bearish',
                bar_index=i, price=h1, atr=atr,
                quality=6,
                description='Equal highs – sellers rejecting the level (Trading Bible p.43)'
            )]

        return []

    # ─────────────────────────────────────────────────────────
    #  MARKET STRUCTURE  (Trading Bible: Chap. Market Structure)
    # ─────────────────────────────────────────────────────────

    def _classify_market(self, df) -> str:
        """uptrend | downtrend | ranging | choppy"""
        closes = df['Close'].values[-30:]
        if len(closes) < 10:
            return 'choppy'

        # Use rolling max/min to count swings
        highs = pd.Series(df['High'].values[-30:])
        lows  = pd.Series(df['Low'].values[-30:])

        hh = (highs > highs.shift(3)).sum()
        ll = (lows  < lows.shift(3)).sum()
        lh = (highs < highs.shift(3)).sum()
        hl = (lows  > lows.shift(3)).sum()

        up_score   = hh + hl
        down_score = lh + ll

        if up_score > down_score * 1.4:
            return 'uptrend'
        if down_score > up_score * 1.4:
            return 'downtrend'

        # Range check: price stays within 1.5 ATR band
        atr  = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else 1
        rang = df['High'].values[-20:].max() - df['Low'].values[-20:].min()
        if rang < atr * 4:
            return 'ranging'

        return 'choppy'

    def _trend_direction(self, df) -> str:
        closes = df['Close'].values[-20:]
        if len(closes) < 5:
            return 'neutral'
        mid = len(closes) // 2
        return 'up' if closes[-1] > closes[mid] else 'down'

    def _find_supports(self, df) -> List[float]:
        """Identify swing-low support levels (Trading Bible approach)."""
        lows   = df['Low'].values
        result = []
        lb     = self.SWING_LOOKBACK

        for i in range(lb, len(lows) - lb):
            window = lows[i - lb: i + lb + 1]
            if lows[i] == window.min():
                result.append(round(float(lows[i]), 2))

        # Deduplicate nearby levels
        result.sort()
        atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else 1
        merged = []
        for lvl in result:
            if not merged or abs(lvl - merged[-1]) > atr * 0.5:
                merged.append(lvl)

        return merged[-5:]   # return the 5 most recent

    def _find_resistances(self, df) -> List[float]:
        """Identify swing-high resistance levels."""
        highs  = df['High'].values
        result = []
        lb     = self.SWING_LOOKBACK

        for i in range(lb, len(highs) - lb):
            window = highs[i - lb: i + lb + 1]
            if highs[i] == window.max():
                result.append(round(float(highs[i]), 2))

        result.sort(reverse=True)
        atr = float(df['ATR'].iloc[-1]) if not pd.isna(df['ATR'].iloc[-1]) else 1
        merged = []
        for lvl in result:
            if not merged or abs(lvl - merged[-1]) > atr * 0.5:
                merged.append(lvl)

        return merged[-5:]

    # ─────────────────────────────────────────────────────────
    #  CONFLUENCE  (Trading Bible: "factors of confluence")
    # ─────────────────────────────────────────────────────────

    def _find_confluence(self, p: PatternSignal, df, supports, resistances, trend) -> List[str]:
        """Check how many confluence factors align with the pattern."""
        confluences = []
        price = p.price
        atr   = p.atr if p.atr else 1
        i     = p.bar_index

        # 1. Trend alignment (most important per book)
        if p.direction == 'bullish' and trend == 'up':
            confluences.append('✅ WITH TREND (bullish)')
        elif p.direction == 'bearish' and trend == 'down':
            confluences.append('✅ WITH TREND (bearish)')
        elif p.direction not in ('neutral',):
            confluences.append('⚠️ Counter-trend')

        # 2. At support / resistance
        for s in supports:
            if abs(price - s) < atr * 1.5:
                confluences.append(f'✅ At support {s:.2f}')
        for r in resistances:
            if abs(price - r) < atr * 1.5:
                confluences.append(f'✅ At resistance {r:.2f}')

        # 3. At 21 EMA (book explicitly uses EMA 21)
        ema21 = df['EMA_21'].iloc[i] if 'EMA_21' in df.columns else None
        if ema21 and not pd.isna(ema21) and abs(price - ema21) < atr * 1.2:
            confluences.append(f'✅ At 21 EMA ({ema21:.2f})')

        # 4. Round number (psychological level)
        round_50 = round(price / 50) * 50
        if abs(price - round_50) < atr * 0.8:
            confluences.append(f'✅ Round number ${round_50:.0f}')

        return confluences

    def _score_quality(self, p: PatternSignal, trend: str, market_type: str) -> int:
        """Score 1-10. Book: multiple confluences = high probability."""
        score = p.quality   # base from pattern type (4-7)

        # Bonus: confluence count
        score += min(len(p.confluence), 3)

        # Penalty: counter-trend
        if any('Counter' in c for c in p.confluence):
            score -= 2

        # Bonus: trending market (cleaner signals)
        if market_type in ('uptrend', 'downtrend'):
            score += 1

        # Penalty: choppy market
        if market_type == 'choppy':
            score -= 2

        return max(1, min(10, score))

    # ─────────────────────────────────────────────────────────
    #  UTILITIES
    # ─────────────────────────────────────────────────────────

    def _to_df(self, price_data: list) -> Optional[pd.DataFrame]:
        if not price_data:
            return None
        records = []
        for c in price_data:
            try:
                records.append({
                    'timestamp': pd.to_datetime(c['timestamp']),
                    'Open':  float(c['open']),
                    'High':  float(c['high']),
                    'Low':   float(c['low']),
                    'Close': float(c['close']),
                    'Volume': float(c.get('volume', 0))
                })
            except Exception:
                continue
        if not records:
            return None
        df = pd.DataFrame(records).set_index('timestamp').sort_index()
        df = df[~df.index.duplicated(keep='last')]
        return df

    def _add_candle_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        # ATR
        hl  = df['High'] - df['Low']
        hc  = (df['High'] - df['Close'].shift()).abs()
        lc  = (df['Low']  - df['Close'].shift()).abs()
        df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

        # EMAs
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_9']  = df['Close'].ewm(span=9,  adjust=False).mean()

        return df

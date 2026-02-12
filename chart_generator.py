#!/usr/bin/env python3
"""
PRECISE CHART GENERATOR
Generates professional trading charts per timeframe
Integrates with the bot's data and adds Trading Bible indicators

Install:
pip3 install --user mplfinance Pillow pandas numpy matplotlib
"""

import mplfinance as mpf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from datetime import datetime
import os


# ─────────────────────────────────────────────
#  TIMEFRAME CONFIGURATION
#  Controls how many candles to show and indicator
#  periods for each timeframe
# ─────────────────────────────────────────────

TIMEFRAME_CONFIG = {
    'M1':  {'candles': 80,  'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 50,  'label': '1 Minute'},
    'M5':  {'candles': 80,  'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 50,  'label': '5 Minutes'},
    'M15': {'candles': 80,  'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 50,  'label': '15 Minutes'},
    'M30': {'candles': 80,  'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 50,  'label': '30 Minutes'},
    'H1':  {'candles': 80,  'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 50,  'label': '1 Hour'},
    'H4':  {'candles': 100, 'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 200, 'label': '4 Hours'},
    'D1':  {'candles': 120, 'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 200, 'label': 'Daily'},
    'W1':  {'candles': 60,  'ema_fast': 9,  'ema_slow': 21, 'sma_trend': 50,  'label': 'Weekly'},
}


class ChartGenerator:
    """
    Generates precise, professional charts for any timeframe.
    Highlights key patterns from the Trading Bible.
    """

    def __init__(self, output_dir='/tmp'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ─────────────────────────────────────────
    #  MAIN ENTRY POINT
    # ─────────────────────────────────────────

    def generate(self, price_data, timeframe='M15',
                 symbol='XAUUSD', detected_patterns=None,
                 key_levels=None, future_zone=None):
        """
        Generate a full chart image.

        Args:
            price_data    : list of dicts  {timestamp, open, high, low, close, volume}
            timeframe     : 'M1','M5','M15','M30','H1','H4','D1','W1'
            symbol        : e.g. 'XAUUSD'
            detected_patterns: list of pattern dicts from CandlestickDetector
            key_levels    : dict  {support:[prices], resistance:[prices]}
            future_zone   : dict  {direction, zone_low, zone_high, label}
                            – drawn as a shaded "watch zone" for future entries

        Returns:
            str  –  absolute path to saved PNG
        """
        cfg = TIMEFRAME_CONFIG.get(timeframe, TIMEFRAME_CONFIG['M15'])

        # ── 1. Build DataFrame ──────────────────
        df = self._build_dataframe(price_data, cfg['candles'])
        if df is None or len(df) < 20:
            print(f"  ⚠️ Chart Data Error: df is {'None' if df is None else f'too short ({len(df)} candles)'}")
            return None

        # ── 2. Compute indicators ───────────────
        df = self._add_indicators(df, cfg)

        # ── 3. Draw chart ───────────────────────
        path = self._draw_chart(
            df, timeframe, symbol, cfg,
            detected_patterns or [],
            key_levels or {},
            future_zone
        )

        return path

    # ─────────────────────────────────────────
    #  DATA PREP
    # ─────────────────────────────────────────

    def _build_dataframe(self, price_data, max_candles):
        """Convert raw data list → cleaned DataFrame."""
        if not price_data:
            return None

        records = []
        for c in price_data[-max_candles:]:
            try:
                # Twelve Data uses 'datetime', Alpha Vantage uses 'timestamp'
                ts = c.get('timestamp') or c.get('datetime')
                if not ts: continue
                
                records.append({
                    'timestamp': pd.to_datetime(ts),
                    'Open':      float(c.get('open') or c.get('Open', 0)),
                    'High':      float(c.get('high') or c.get('High', 0)),
                    'Low':       float(c.get('low') or c.get('Low', 0)),
                    'Close':     float(c.get('close') or c.get('Close', 0)),
                    'Volume':    float(c.get('volume') or c.get('Volume', 0))
                })
            except Exception:
                continue

        if not records:
            return None

        df = pd.DataFrame(records)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

        # Remove duplicates & NaN rows
        df = df[~df.index.duplicated(keep='last')]
        df.dropna(subset=['Open', 'High', 'Low', 'Close'], inplace=True)

        return df

    def _add_indicators(self, df, cfg):
        """Add all indicators used by the Trading Bible."""
        # EMAs (dynamic S/R per Trading Bible)
        df['EMA_fast'] = df['Close'].ewm(span=cfg['ema_fast'], adjust=False).mean()
        df['EMA_slow'] = df['Close'].ewm(span=cfg['ema_slow'], adjust=False).mean()

        # SMA trend filter (200 for H4/D1, 50 for smaller TFs)
        df['SMA_trend'] = df['Close'].rolling(cfg['sma_trend']).mean()

        # 21 EMA  – explicitly used in the Trading Bible for pin-bar / engulfing entries
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()

        # ATR  (14-period) – used internally for dynamic levels
        high_low   = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close  = (df['Low']  - df['Close'].shift()).abs()
        df['ATR']  = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()

        return df

    # ─────────────────────────────────────────
    #  CHART DRAWING
    # ─────────────────────────────────────────

    def _draw_chart(self, df, timeframe, symbol, cfg,
                    patterns, key_levels, future_zone):
        """Create and save the full chart."""

        # ── Colours ──────────────────────────
        BG          = '#0d1117'
        GRID        = '#21262d'
        BULL_CANDLE = '#26a69a'
        BEAR_CANDLE = '#ef5350'
        EMA_FAST    = '#f0b429'   # yellow – fast EMA
        EMA_SLOW    = '#60a5fa'   # blue   – slow EMA (= 21-EMA, key in bible)
        SMA_TREND   = '#a78bfa'   # purple – trend SMA
        TEXT_COLOR  = '#e6edf3'

        mc = mpf.make_marketcolors(
            up=BULL_CANDLE, down=BEAR_CANDLE,
            edge={'up': BULL_CANDLE, 'down': BEAR_CANDLE},
            wick={'up': BULL_CANDLE, 'down': BEAR_CANDLE},
            volume={'up': BULL_CANDLE, 'down': BEAR_CANDLE},
            alpha=0.95
        )

        style = mpf.make_mpf_style(
            marketcolors=mc,
            facecolor=BG,
            figcolor=BG,
            gridstyle='--',
            gridcolor=GRID,
            y_on_right=True,
            rc={
                'axes.labelcolor':  TEXT_COLOR,
                'xtick.color':      TEXT_COLOR,
                'ytick.color':      TEXT_COLOR,
                'axes.titlecolor':  TEXT_COLOR,
                'text.color':       TEXT_COLOR,
            }
        )

        # ── Additional plot lines ─────────────
        add_plots = []

        if df['EMA_fast'].notna().sum() >= 5:
            add_plots.append(
                mpf.make_addplot(df['EMA_fast'], color=EMA_FAST,
                                 width=1.5, linestyle='-', panel=0)
            )
        if df['EMA_21'].notna().sum() >= 5:
            add_plots.append(
                mpf.make_addplot(df['EMA_21'], color=EMA_SLOW,
                                 width=1.8, linestyle='-', panel=0)
            )
        if df['SMA_trend'].notna().sum() >= 5:
            add_plots.append(
                mpf.make_addplot(df['SMA_trend'], color=SMA_TREND,
                                 width=1.2, linestyle='--', panel=0)
            )

        # ── Render base chart ─────────────────
        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        path    = os.path.join(self.output_dir, f'chart_{symbol}_{timeframe}_{now_str}.png')

        title = (f'{symbol}  –  {cfg["label"]}  '
                 f'| {datetime.now().strftime("%Y-%m-%d %H:%M")} UTC')

        fig, axes = mpf.plot(
            df,
            type='candle',
            style=style,
            title=title,
            volume=True,
            addplot=add_plots if add_plots else None,
            figsize=(16, 10),
            panel_ratios=(4, 1),
            tight_layout=True,
            returnfig=True,
            warn_too_much_data=500,
        )

        ax = axes[0]   # main price axis
        ax_vol = axes[2]  # volume axis

        # ── Key support / resistance lines ────
        self._draw_key_levels(ax, df, key_levels)

        # ── Pattern annotations ───────────────
        self._annotate_patterns(ax, df, patterns)

        # ── Future entry zone ─────────────────
        if future_zone:
            self._draw_future_zone(ax, df, future_zone)

        # ── Legend ────────────────────────────
        self._draw_legend(ax, cfg, EMA_FAST, EMA_SLOW, SMA_TREND,
                          TEXT_COLOR, patterns, future_zone)

        # ── Watermark ─────────────────────────
        ax.text(0.01, 0.02, 'XAUUSD Bot  |  Trading Bible System',
                transform=ax.transAxes, fontsize=8,
                color='#444d56', alpha=0.8, va='bottom')

        fig.savefig(path, dpi=150, bbox_inches='tight',
                    facecolor=BG, edgecolor='none')
        plt.close(fig)

        print(f"📊 Chart saved → {path}")
        return path

    # ─────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────

    def _draw_key_levels(self, ax, df, key_levels):
        """Draw horizontal support / resistance lines."""
        xmax = len(df)

        for price in key_levels.get('support', []):
            ax.axhline(y=price, color='#26a69a', linewidth=1.2,
                       linestyle='--', alpha=0.7)
            ax.text(xmax * 0.01, price,
                    f'S  {price:.2f}',
                    color='#26a69a', fontsize=8, va='bottom', alpha=0.9)

        for price in key_levels.get('resistance', []):
            ax.axhline(y=price, color='#ef5350', linewidth=1.2,
                       linestyle='--', alpha=0.7)
            ax.text(xmax * 0.01, price,
                    f'R  {price:.2f}',
                    color='#ef5350', fontsize=8, va='top', alpha=0.9)

    def _annotate_patterns(self, ax, df, patterns):
        """Mark detected candlestick patterns on the chart."""
        for p in patterns:
            idx   = p.get('bar_index')    # integer position in df
            price = p.get('price')
            name  = p.get('name', '')
            direction = p.get('direction', 'bullish')

            if idx is None or price is None:
                continue
            if idx < 0 or idx >= len(df):
                continue

            color  = '#26a69a' if direction == 'bullish' else '#ef5350'
            marker = '^'       if direction == 'bullish' else 'v'
            offset = -p.get('atr', 5) * 1.5 if direction == 'bullish' else p.get('atr', 5) * 1.5

            ax.plot(idx, price + offset, marker=marker,
                    color=color, markersize=10, zorder=5)
            ax.text(idx, price + offset * 1.8, name,
                    color=color, fontsize=7.5, ha='center',
                    fontweight='bold', zorder=5)

    def _draw_future_zone(self, ax, df, fz):
        """Shade the predicted future entry zone."""
        color = '#26a69a' if fz.get('direction') == 'BUY' else '#ef5350'
        xmin, xmax = 0, len(df) - 1

        ax.axhspan(fz['zone_low'], fz['zone_high'],
                   xmin=0.6, xmax=1.0,
                   color=color, alpha=0.12, zorder=2)

        # Dashed boundary lines
        ax.axhline(fz['zone_low'],  xmin=0.6, color=color, linewidth=1,
                   linestyle=':', alpha=0.8)
        ax.axhline(fz['zone_high'], xmin=0.6, color=color, linewidth=1,
                   linestyle=':', alpha=0.8)

        mid = (fz['zone_low'] + fz['zone_high']) / 2
        ax.text(xmax * 0.97, mid,
                f"⏳ {fz.get('label', 'WATCH ZONE')}",
                color=color, fontsize=8.5, ha='right',
                fontweight='bold', alpha=0.9)

    def _draw_legend(self, ax, cfg, c_fast, c_slow, c_trend,
                     text_col, patterns, future_zone):
        """Add a legend explaining indicators and signals."""
        handles = [
            Line2D([0], [0], color=c_fast,  linewidth=2,
                   label=f'EMA {cfg["ema_fast"]}'),
            Line2D([0], [0], color=c_slow,  linewidth=2,
                   label='EMA 21 (Bible)'),
            Line2D([0], [0], color=c_trend, linewidth=1.5, linestyle='--',
                   label=f'SMA {cfg["sma_trend"]}'),
        ]

        if patterns:
            handles.append(
                Line2D([0], [0], marker='^', color='#26a69a',
                       linestyle='None', markersize=8, label='Pattern ↑')
            )
            handles.append(
                Line2D([0], [0], marker='v', color='#ef5350',
                       linestyle='None', markersize=8, label='Pattern ↓')
            )

        if future_zone:
            color = '#26a69a' if future_zone.get('direction') == 'BUY' else '#ef5350'
            handles.append(
                mpatches.Patch(color=color, alpha=0.3,
                               label=f'Watch Zone ({future_zone["direction"]})')
            )

        leg = ax.legend(handles=handles, loc='upper left',
                        facecolor='#161b22', edgecolor='#30363d',
                        labelcolor=text_col, fontsize=8, framealpha=0.85)

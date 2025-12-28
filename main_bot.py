#!/usr/bin/env python3
"""
Unified XAUUSD Trading Bot - Automatic + Interactive

Features:
- Automatic analysis every N minutes (configurable)
- Sends Telegram alerts when signals meet threshold
- Interactive commands for on-demand analysis
- Any timeframe: M1, M3, M5, M15, M30, H1, H4, D1
- Cloud-ready (runs 24/7)
"""

import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from data_collector import DataCollector
from analyzer import MarketAnalyzer
from logger import TradingLogger
from config import *

class UnifiedTradingBot:
    def __init__(self):
        self.collector = DataCollector()
        self.logger = TradingLogger()
        self.is_analyzing = False
        self.auto_analysis_enabled = True
        self.default_timeframe = 'M15'  # Default for automatic updates
        self.application = None
        
        # Statistics
        self.total_auto_runs = 0
        self.total_manual_runs = 0
        self.last_auto_run = None
        self.last_signal = None
        
        print("="*70)
        print("UNIFIED XAUUSD TRADING BOT")
        print("="*70)
        print(f"✅ Automatic monitoring: Every {UPDATE_INTERVAL_MINUTES} minutes")
        print(f"✅ Default timeframe: {self.default_timeframe}")
        print(f"✅ Interactive commands: Available")
        print(f"✅ Trading hours: {'Mon-Fri' if TRADING_DAYS == [0,1,2,3,4] else 'Custom'}")
        print("="*70 + "\n")
    
    def is_trading_hours(self):
        """Check if we're in active trading hours"""
        if not TRADING_ACTIVE:
            return False
        
        now = datetime.now()
        
        # Check if it's a trading day
        if now.weekday() not in TRADING_DAYS:
            return False
        
        return True
    
    async def automatic_analysis(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled automatic analysis - runs every N minutes"""
        if not self.auto_analysis_enabled:
            return
        
        if not self.is_trading_hours():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Outside trading hours - skipping auto analysis")
            return
        
        if self.is_analyzing:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Analysis already in progress - skipping")
            return
        
        self.is_analyzing = True
        self.total_auto_runs += 1
        self.last_auto_run = datetime.now()
        
        try:
            print(f"\n{'='*70}")
            print(f"AUTO ANALYSIS #{self.total_auto_runs}")
            print(f"Time: {self.last_auto_run.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Timeframe: {self.default_timeframe}")
            print("="*70)
            
            # Collect data
            print("[1/3] Collecting market data...")
            market_data = self.collector.get_market_data()
            
            if not market_data or not market_data.get('current_price'):
                print("❌ Failed to collect market data")
                return
            
            price = market_data['current_price']['price']
            print(f"  ✓ Price: ${price:.2f}")
            
            # Analyze
            print("[2/3] Analyzing with AI...")
            analyzer = MarketAnalyzer(timeframe=self.default_timeframe)
            analysis = analyzer.analyze_market(market_data)
            
            if not analysis.get('success'):
                print(f"❌ Analysis failed: {analysis.get('error')}")
                return
            
            trade_rec = analysis['trade_recommendation']
            confidence = analysis['confidence']
            
            print(f"  ✓ Signal: {trade_rec}")
            print(f"  ✓ Confidence: {confidence}/10")
            
            # Log it
            self.logger.log_analysis(analysis, market_data)
            if SAVE_MARKET_DATA:
                self.logger.save_market_data(market_data)
            
            # Check if we should send alert
            print("[3/3] Checking alert criteria...")
            should_alert = analyzer.should_alert(analysis)
            
            if should_alert:
                print("  🔔 ALERT TRIGGERED - Sending to Telegram...")
                self.last_signal = analysis
                
                # Send to Telegram
                await self.send_telegram_alert(analysis, is_auto=True)
                
                # Log as potential trade
                self.logger.log_performance(analysis, outcome='pending')
            else:
                if trade_rec == 'NO TRADE':
                    print("  ⏸️  NO TRADE - No alert sent")
                else:
                    print(f"  ⏸️  Signal doesn't meet threshold (conf: {confidence})")
            
            print(f"{'='*70}")
            print(f"Next auto analysis in {UPDATE_INTERVAL_MINUTES} minutes")
            print(f"Total: {self.total_auto_runs} auto | {self.total_manual_runs} manual")
            print("="*70 + "\n")
            
            # Show stats every 10 runs
            if self.total_auto_runs % 10 == 0:
                self.logger.print_statistics()
            
        except Exception as e:
            print(f"❌ Error in automatic analysis: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_analyzing = False
    
    async def send_telegram_alert(self, analysis, is_auto=False):
        """Send trading alert via Telegram"""
        try:
            message = self.format_alert(analysis, is_auto)
            
            # Add action buttons
            keyboard = [
                [
                    InlineKeyboardButton("📊 Status", callback_data='status'),
                    InlineKeyboardButton("🔄 Re-analyze", callback_data=f'analyze_{self.default_timeframe}'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.application.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            print("  ✅ Telegram alert sent")
            
        except Exception as e:
            print(f"  ❌ Failed to send Telegram alert: {e}")
    
    def format_alert(self, analysis, is_auto=False):
        """Format trading alert for Telegram"""
        signal = analysis['trade_recommendation']
        confidence = analysis['confidence']
        price = analysis['current_price']
        timeframe = self.default_timeframe
        
        # Emoji
        if signal == 'BUY':
            emoji = '🟢'
            signal_emoji = '📈'
        elif signal == 'SELL':
            emoji = '🔴'
            signal_emoji = '📉'
        else:
            emoji = '⚪'
            signal_emoji = '⏸️'
        
        source = "🤖 <b>AUTO ALERT</b>" if is_auto else "📱 <b>MANUAL REQUEST</b>"
        
        msg = f"""
{source}

{emoji} <b>{signal_emoji} {signal} SIGNAL</b>

<b>⏱ Timeframe:</b> {timeframe}
<b>💰 Price:</b> ${price:.2f}
<b>🎯 Confidence:</b> {confidence}/10
<b>📊 Bias:</b> {analysis['market_bias']} ({analysis['bias_strength']}/10)
<b>⚠️ Risk:</b> {analysis['risk_level']}
<b>🌍 Session:</b> {analysis.get('session', 'N/A')}
"""
        
        if signal != 'NO TRADE':
            msg += f"\n<b>📋 TRADE SETUP:</b>\n"
            msg += f"├ Entry: ~${price:.2f}\n"
            
            if analysis.get('stop_loss'):
                sl = analysis['stop_loss']
                risk = abs(price - sl)
                msg += f"├ Stop: ${sl:.2f} (-${risk:.2f})\n"
            
            if analysis.get('take_profit_1'):
                tp1 = analysis['take_profit_1']
                reward = abs(tp1 - price)
                if analysis.get('stop_loss'):
                    risk = abs(price - analysis['stop_loss'])
                    rr = reward / risk if risk > 0 else 0
                    msg += f"├ TP1: ${tp1:.2f} (+${reward:.2f}, R:R {rr:.1f})\n"
                else:
                    msg += f"├ TP1: ${tp1:.2f} (+${reward:.2f})\n"
            
            if analysis.get('take_profit_2'):
                tp2 = analysis['take_profit_2']
                reward2 = abs(tp2 - price)
                msg += f"└ TP2: ${tp2:.2f} (+${reward2:.2f})\n"
        
        if analysis.get('key_factors'):
            msg += f"\n<b>🔑 Key Factors:</b>\n"
            for i, factor in enumerate(analysis['key_factors'][:2], 1):
                factor_text = factor if len(factor) <= 80 else factor[:77] + "..."
                msg += f"{i}. {factor_text}\n"
        
        msg += f"\n<code>{analysis['analysis_id']}</code>"
        msg += f"\n<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        
        return msg
    
    # ===== INTERACTIVE COMMANDS =====
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message"""
        keyboard = [
            [
                InlineKeyboardButton("M3 📊", callback_data='analyze_M3'),
                InlineKeyboardButton("M5 📊", callback_data='analyze_M5'),
                InlineKeyboardButton("M15 📊", callback_data='analyze_M15'),
            ],
            [
                InlineKeyboardButton("H1 📈", callback_data='analyze_H1'),
                InlineKeyboardButton("H4 📈", callback_data='analyze_H4'),
                InlineKeyboardButton("D1 📈", callback_data='analyze_D1'),
            ],
            [
                InlineKeyboardButton("📊 Status", callback_data='status'),
                InlineKeyboardButton("🕐 Latest", callback_data='latest'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        status = "✅ ACTIVE" if self.auto_analysis_enabled else "⏸️ PAUSED"
        last_run = self.last_auto_run.strftime('%H:%M:%S') if self.last_auto_run else "Never"
        
        welcome_msg = f"""
🤖 <b>UNIFIED TRADING ASSISTANT</b>

<b>Auto-Monitoring:</b> {status}
<b>Default TF:</b> {self.default_timeframe}
<b>Interval:</b> {UPDATE_INTERVAL_MINUTES} min
<b>Last Run:</b> {last_run}

<b>📊 Auto Runs:</b> {self.total_auto_runs}
<b>📱 Manual Runs:</b> {self.total_manual_runs}

<b>Commands:</b>
/analyze [TF] - Custom analysis
/m3, /m5, /m15, /h1, /h4, /d1 - Quick TF
/status - Statistics
/latest - Last signal
/pause - Pause auto-monitoring
/resume - Resume auto-monitoring

<b>Tap a button for instant analysis:</b>
        """
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def manual_analysis(self, update: Update, timeframe: str, is_callback: bool = False):
        """Run on-demand analysis"""
        if self.is_analyzing:
            msg = "⏳ Analysis in progress. Please wait..."
            if is_callback:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        self.is_analyzing = True
        self.total_manual_runs += 1
        
        try:
            # Send status message
            status_msg = f"🔄 Analyzing {timeframe}...\n⏳ Please wait..."
            
            if is_callback:
                message = await update.callback_query.edit_message_text(status_msg)
            else:
                message = await update.message.reply_text(status_msg)
            
            # Collect and analyze
            market_data = self.collector.get_market_data()
            
            if not market_data or not market_data.get('current_price'):
                await message.edit_text("❌ Failed to collect market data")
                return
            
            analyzer = MarketAnalyzer(timeframe=timeframe)
            analysis = analyzer.analyze_market(market_data)
            
            if not analysis.get('success'):
                await message.edit_text(f"❌ Analysis failed: {analysis.get('error')}")
                return
            
            # Format result
            response = self.format_analysis(analysis, timeframe)
            
            # Add buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Again", callback_data=f'analyze_{timeframe}'),
                    InlineKeyboardButton("📊 Status", callback_data='status'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.edit_text(response, parse_mode='HTML', reply_markup=reply_markup)
            
            # Log it
            self.logger.log_analysis(analysis, market_data)
            
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            try:
                if is_callback:
                    await update.callback_query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
            except:
                pass
        finally:
            self.is_analyzing = False
    
    def format_analysis(self, analysis, timeframe):
        """Format analysis for Telegram"""
        signal = analysis['trade_recommendation']
        confidence = analysis['confidence']
        price = analysis['current_price']
        
        if signal == 'BUY':
            emoji = '🟢📈'
        elif signal == 'SELL':
            emoji = '🔴📉'
        else:
            emoji = '⚪⏸️'
        
        msg = f"""
{emoji} <b>{signal}</b>

<b>⏱ TF:</b> {timeframe} | <b>🎯 Conf:</b> {confidence}/10
<b>💰 Price:</b> ${price:.2f}
<b>📊 Bias:</b> {analysis['market_bias']} ({analysis['bias_strength']}/10)
<b>⚠️ Risk:</b> {analysis['risk_level']}
"""
        
        if signal != 'NO TRADE' and confidence >= 6:
            if analysis.get('stop_loss') and analysis.get('take_profit_1'):
                sl = analysis['stop_loss']
                tp1 = analysis['take_profit_1']
                risk = abs(price - sl)
                reward = abs(tp1 - price)
                rr = reward / risk if risk > 0 else 0
                
                msg += f"\n<b>Setup:</b> Entry ${price:.2f} | Stop ${sl:.2f} | TP ${tp1:.2f}\n"
                msg += f"<b>R:R:</b> {rr:.2f} | <b>Risk:</b> ${risk:.2f}\n"
        
        if analysis.get('key_factors'):
            msg += f"\n<b>Factors:</b> {analysis['key_factors'][0][:60]}...\n"
        
        return msg
    
    async def show_status(self, update: Update, is_callback: bool = False):
        """Show system status"""
        stats = self.logger.get_statistics()
        
        auto_status = "✅ RUNNING" if self.auto_analysis_enabled else "⏸️ PAUSED"
        last_run = self.last_auto_run.strftime('%H:%M') if self.last_auto_run else "Never"
        
        if stats:
            msg = f"""
📊 <b>SYSTEM STATUS</b>

<b>Auto-Monitor:</b> {auto_status}
<b>Last Auto Run:</b> {last_run}
<b>Auto Runs:</b> {self.total_auto_runs}
<b>Manual Runs:</b> {self.total_manual_runs}

<b>📈 Analysis Stats:</b>
├ Total: {stats['total_analyses']}
├ Avg Conf: {stats['average_confidence']}/10
├ BUY: {stats['buy_signals']}
├ SELL: {stats['sell_signals']}
└ NO TRADE: {stats['no_trade_signals']}

<b>Signal Rate:</b> {stats['trade_signal_rate']:.1f}%
            """
            
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data='status')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            msg = "No data yet. Run an analysis first!"
            reply_markup = None
        
        if is_callback:
            await update.callback_query.edit_message_text(msg, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)
    
    async def show_latest(self, update: Update, is_callback: bool = False):
        """Show last signal"""
        if not self.last_signal:
            msg = "No signals yet. Waiting for first auto analysis..."
        else:
            msg = self.format_alert(self.last_signal, is_auto=True)
        
        if is_callback:
            await update.callback_query.edit_message_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text(msg, parse_mode='HTML')
    
    async def pause_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause automatic monitoring"""
        self.auto_analysis_enabled = False
        await update.message.reply_text("⏸️ Automatic monitoring paused.\n\nSend /resume to restart.")
    
    async def resume_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume automatic monitoring"""
        self.auto_analysis_enabled = True
        await update.message.reply_text(f"✅ Automatic monitoring resumed.\n\nNext run in {UPDATE_INTERVAL_MINUTES} minutes.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('analyze_'):
            timeframe = query.data.replace('analyze_', '')
            await self.manual_analysis(update, timeframe, is_callback=True)
        elif query.data == 'status':
            await self.show_status(update, is_callback=True)
        elif query.data == 'latest':
            await self.show_latest(update, is_callback=True)
    
    # Quick timeframe commands
    async def cmd_m1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M1')
    
    async def cmd_m3(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M3')
    
    async def cmd_m5(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M5')
    
    async def cmd_m15(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M15')
    
    async def cmd_m30(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M30')
    
    async def cmd_h1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'H1')
    
    async def cmd_h4(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'H4')
    
    async def cmd_d1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'D1')
    
    def run(self):
        """Start the unified bot"""
        # Create application
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.start))
        self.application.add_handler(CommandHandler("status", self.show_status))
        self.application.add_handler(CommandHandler("latest", self.show_latest))
        self.application.add_handler(CommandHandler("pause", self.pause_auto))
        self.application.add_handler(CommandHandler("resume", self.resume_auto))
        
        # Quick timeframe commands
        self.application.add_handler(CommandHandler("m1", self.cmd_m1))
        self.application.add_handler(CommandHandler("m3", self.cmd_m3))
        self.application.add_handler(CommandHandler("m5", self.cmd_m5))
        self.application.add_handler(CommandHandler("m15", self.cmd_m15))
        self.application.add_handler(CommandHandler("m30", self.cmd_m30))
        self.application.add_handler(CommandHandler("h1", self.cmd_h1))
        self.application.add_handler(CommandHandler("h4", self.cmd_h4))
        self.application.add_handler(CommandHandler("d1", self.cmd_d1))
        
        # Button callbacks
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Schedule automatic analysis
        job_queue = self.application.job_queue
        job_queue.run_repeating(
            self.automatic_analysis,
            interval=UPDATE_INTERVAL_MINUTES * 60,  # Convert to seconds
            first=10  # First run after 10 seconds
        )
        
        print("✅ Unified bot starting...")
        print(f"🤖 Automatic analysis every {UPDATE_INTERVAL_MINUTES} minutes")
        print(f"📱 Interactive commands enabled")
        print("Press Ctrl+C to stop\n")
        
        # Run bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Run the unified bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n❌ ERROR: Missing Telegram credentials!")
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    bot = UnifiedTradingBot()
    bot.run()


if __name__ == "__main__":
    main()
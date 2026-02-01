#!/usr/bin/env python3
"""
Enhanced Trading Bot with Optimal Entries & Position Sizing
"""

import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from data_collector import DataCollector
from analyzer_enhanced import EnhancedMarketAnalyzer
from logger import TradingLogger
from config import *

class EnhancedTradingBot:
    def __init__(self, account_size=100, risk_percent=5):
        self.collector = DataCollector()
        self.logger = TradingLogger()
        self.is_analyzing = False
        self.auto_analysis_enabled = True
        self.default_timeframe = 'M15'
        self.application = None
        
        # Account settings
        self.account_size = account_size
        self.risk_percent = risk_percent
        
        # Statistics
        self.total_auto_runs = 0
        self.total_manual_runs = 0
        self.last_auto_run = None
        self.last_signal = None
        
        print("="*70)
        print("ENHANCED XAUUSD TRADING BOT")
        print("="*70)
        print(f"💰 Account Size: ${account_size}")
        print(f"⚠️  Risk Per Trade: {risk_percent}% (${account_size * risk_percent / 100:.2f})")
        print(f"✅ Auto monitoring: Every {UPDATE_INTERVAL_MINUTES} minutes")
        print(f"✅ Default timeframe: {self.default_timeframe}")
        print("="*70 + "\n")
    
    def is_trading_hours(self):
        """Check trading hours"""
        if not TRADING_ACTIVE:
            return False
        
        now = datetime.now()
        if now.weekday() not in TRADING_DAYS:
            return False
        
        return True
    
    async def automatic_analysis(self, context: ContextTypes.DEFAULT_TYPE):
        """Scheduled analysis with enhanced entry logic"""
        if not self.auto_analysis_enabled or not self.is_trading_hours():
            return
        
        if self.is_analyzing:
            return
        
        self.is_analyzing = True
        self.total_auto_runs += 1
        self.last_auto_run = datetime.now()
        
        try:
            print(f"\n{'='*70}")
            print(f"AUTO ANALYSIS #{self.total_auto_runs}")
            print(f"Time: {self.last_auto_run.strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*70)
            
            # Collect data
            market_data = self.collector.get_market_data()
            
            if not market_data or not market_data.get('current_price'):
                print("❌ Failed to collect data")
                return
            
            price = market_data['current_price']['price']
            print(f"  ✓ Price: ${price:.2f}")
            
            # Enhanced analysis
            analyzer = EnhancedMarketAnalyzer(
                timeframe=self.default_timeframe,
                account_size=self.account_size,
                risk_percent=self.risk_percent
            )
            analysis = analyzer.analyze_market(market_data)
            
            if not analysis.get('success'):
                print(f"❌ Analysis failed: {analysis.get('error')}")
                return
            
            trade_rec = analysis['trade_recommendation']
            confidence = analysis['confidence']
            primary_entry = analysis.get('primary_entry', price)
            
            print(f"  ✓ Signal: {trade_rec}")
            print(f"  ✓ Confidence: {confidence}/10")
            print(f"  ✓ Entry: ${primary_entry:.2f} (Current: ${price:.2f})")
            
            # Log
            self.logger.log_analysis(analysis, market_data)
            if SAVE_MARKET_DATA:
                self.logger.save_market_data(market_data)
            
            # Check alert
            should_alert = analyzer.should_alert(analysis)
            
            if should_alert:
                print("  🔔 ALERT TRIGGERED")
                self.last_signal = analysis
                await self.send_telegram_alert(analysis, is_auto=True)
                self.logger.log_performance(analysis, outcome='pending')
            else:
                if trade_rec == 'NO TRADE':
                    print("  ⏸️  NO TRADE")
                else:
                    print(f"  ⏸️  Below threshold (conf: {confidence})")
            
            print(f"{'='*70}\n")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_analyzing = False
    
    async def send_telegram_alert(self, analysis, is_auto=False):
        """Enhanced Telegram alert with entry info"""
        try:
            message = self.format_enhanced_alert(analysis, is_auto)
            
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
            print(f"  ❌ Telegram error: {e}")
    
    def format_enhanced_alert(self, analysis, is_auto=False):
        """Enhanced alert format with entry zones and position sizing"""
        signal = analysis['trade_recommendation']
        confidence = analysis['confidence']
        current_price = analysis['current_price']
        primary_entry = analysis.get('primary_entry', current_price)
        entry_zone_low = analysis.get('entry_zone_low', primary_entry)
        entry_zone_high = analysis.get('entry_zone_high', primary_entry)
        timeframe = analysis.get('analysis_mode', 'M15').upper()
        
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
<b>🎯 Confidence:</b> {confidence}/10
<b>📊 Bias:</b> {analysis['market_bias']} ({analysis['bias_strength']}/10)
<b>⚠️ Risk Level:</b> {analysis['risk_level']}
<b>🌍 Session:</b> {analysis.get('session', 'N/A')}

💰 <b>ACCOUNT INFO:</b>
├ Size: ${self.account_size}
└ Max Risk: ${self.account_size * self.risk_percent / 100:.2f} ({self.risk_percent}%)
"""
        
        if signal != 'NO TRADE':
            entry_diff = primary_entry - current_price
            at_market = abs(entry_diff) < 1
            
            msg += f"\n📍 <b>ENTRY STRATEGY:</b>\n"
            msg += f"├ Current: ${current_price:.2f}\n"
            
            if at_market:
                msg += f"├ <b>Entry: ${primary_entry:.2f}</b> ✅ AT MARKET\n"
            else:
                direction = "above" if entry_diff > 0 else "below"
                msg += f"├ <b>Entry: ${primary_entry:.2f}</b>\n"
                msg += f"├   ({direction} current by ${abs(entry_diff):.2f})\n"
            
            msg += f"└ Zone: ${entry_zone_low:.2f} - ${entry_zone_high:.2f}\n"
            
            if analysis.get('stop_loss'):
                sl = analysis['stop_loss']
                risk_price = abs(primary_entry - sl)
                
                msg += f"\n🛡 <b>RISK MANAGEMENT:</b>\n"
                msg += f"├ Stop: ${sl:.2f}\n"
                msg += f"├ Risk: ${risk_price:.2f}\n"
                
                position_info = analysis.get('position_sizing')
                if position_info:
                    lots = position_info['lots']
                    micro = position_info['micro_lots']
                    actual_risk = position_info['actual_risk_dollars']
                    
                    msg += f"├ <b>Position: {lots} lots</b> ({micro} micro)\n"
                    msg += f"└ <b>Actual Risk: ${actual_risk:.2f}</b>\n"
                    
                    if not position_info['position_size_valid']:
                        msg += f"   ⚠️ <b>EXCEEDS MAX RISK!</b>\n"
            
            if analysis.get('take_profit_1'):
                tp1 = analysis['take_profit_1']
                reward1 = abs(tp1 - primary_entry)
                rr1 = analysis.get('risk_reward_1', 0)
                
                msg += f"\n🎯 <b>TARGETS:</b>\n"
                msg += f"├ TP1: ${tp1:.2f} (+${reward1:.2f})\n"
                msg += f"│   R:R {rr1}:1\n"
                
                if analysis.get('take_profit_2'):
                    tp2 = analysis['take_profit_2']
                    reward2 = abs(tp2 - primary_entry)
                    rr2 = analysis.get('risk_reward_2', 0)
                    msg += f"└ TP2: ${tp2:.2f} (+${reward2:.2f})\n"
                    msg += f"    R:R {rr2}:1\n"
        
        if analysis.get('key_factors'):
            msg += f"\n🔑 <b>Key Factors:</b>\n"
            for i, factor in enumerate(analysis['key_factors'][:3], 1):
                msg += f"{i}. {factor}\n"
        
        if analysis.get('entry_logic'):
            logic = analysis['entry_logic'][:100]
            msg += f"\n💡 <b>Entry Logic:</b>\n<i>{logic}...</i>\n"
        
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
🤖 <b>ENHANCED TRADING ASSISTANT</b>

💰 <b>Account:</b> ${self.account_size}
⚠️ <b>Risk/Trade:</b> {self.risk_percent}% (${self.account_size * self.risk_percent / 100:.2f})

<b>Auto-Monitor:</b> {status}
<b>Default TF:</b> {self.default_timeframe}
<b>Interval:</b> {UPDATE_INTERVAL_MINUTES} min
<b>Last Run:</b> {last_run}

<b>📊 Runs:</b> {self.total_auto_runs} auto | {self.total_manual_runs} manual

<b>✨ NEW FEATURES:</b>
• Optimal entry points (not just current price)
• Entry zones for better fills
• Position sizing based on account
• Risk-adjusted stops

<b>Commands:</b>
/m15, /h1, /h4 - Quick analysis
/status - Statistics
/latest - Last signal
/pause / /resume - Control auto-monitoring

<b>Tap a button for instant analysis:</b>
        """
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def manual_analysis(self, update: Update, timeframe: str, is_callback: bool = False):
        """Enhanced manual analysis"""
        if self.is_analyzing:
            msg = "⏳ Analysis in progress..."
            if is_callback:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        self.is_analyzing = True
        self.total_manual_runs += 1
        
        try:
            status_msg = f"🔄 Analyzing {timeframe}...\n⏳ Please wait..."
            
            if is_callback:
                message = await update.callback_query.edit_message_text(status_msg)
            else:
                message = await update.message.reply_text(status_msg)
            
            # Collect and analyze
            market_data = self.collector.get_market_data()
            
            if not market_data or not market_data.get('current_price'):
                await message.edit_text("❌ Failed to collect data")
                return
            
            analyzer = EnhancedMarketAnalyzer(
                timeframe=timeframe,
                account_size=self.account_size,
                risk_percent=self.risk_percent
            )
            analysis = analyzer.analyze_market(market_data)
            
            if not analysis.get('success'):
                await message.edit_text(f"❌ Failed: {analysis.get('error')}")
                return
            
            # Format result
            response = self.format_enhanced_alert(analysis, is_auto=False)
            
            # Buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Again", callback_data=f'analyze_{timeframe}'),
                    InlineKeyboardButton("📊 Status", callback_data='status'),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await message.edit_text(response, parse_mode='HTML', reply_markup=reply_markup)
            
            # Log
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
    
    async def show_status(self, update: Update, is_callback: bool = False):
        """Show system status"""
        stats = self.logger.get_statistics()
        
        auto_status = "✅ RUNNING" if self.auto_analysis_enabled else "⏸️ PAUSED"
        last_run = self.last_auto_run.strftime('%H:%M') if self.last_auto_run else "Never"
        
        if stats:
            msg = f"""
📊 <b>SYSTEM STATUS</b>

💰 <b>Account: ${self.account_size}</b>
⚠️ <b>Risk/Trade: {self.risk_percent}% (${self.account_size * self.risk_percent / 100:.2f})</b>

<b>Auto-Monitor:</b> {auto_status}
<b>Last Run:</b> {last_run}
<b>Runs:</b> {self.total_auto_runs} auto | {self.total_manual_runs} manual

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
            msg = "No data yet."
            reply_markup = None
        
        if is_callback:
            await update.callback_query.edit_message_text(msg, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, parse_mode='HTML', reply_markup=reply_markup)
    
    async def show_latest(self, update: Update, is_callback: bool = False):
        """Show last signal"""
        if not self.last_signal:
            msg = "No signals yet."
        else:
            msg = self.format_enhanced_alert(self.last_signal, is_auto=True)
        
        if is_callback:
            await update.callback_query.edit_message_text(msg, parse_mode='HTML')
        else:
            await update.message.reply_text(msg, parse_mode='HTML')
    
    async def pause_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pause auto-monitoring"""
        self.auto_analysis_enabled = False
        await update.message.reply_text("⏸️ Paused. /resume to restart.")
    
    async def resume_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resume auto-monitoring"""
        self.auto_analysis_enabled = True
        await update.message.reply_text(f"✅ Resumed. Next in {UPDATE_INTERVAL_MINUTES} min.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle buttons"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('analyze_'):
            timeframe = query.data.replace('analyze_', '')
            await self.manual_analysis(update, timeframe, is_callback=True)
        elif query.data == 'status':
            await self.show_status(update, is_callback=True)
        elif query.data == 'latest':
            await self.show_latest(update, is_callback=True)
    
    # Quick commands
    async def cmd_m3(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M3')
    
    async def cmd_m5(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M5')
    
    async def cmd_m15(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'M15')
    
    async def cmd_h1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'H1')
    
    async def cmd_h4(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'H4')
    
    async def cmd_d1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.manual_analysis(update, 'D1')
    
    def run(self):
        """Start the bot"""
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Commands
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.start))
        self.application.add_handler(CommandHandler("status", self.show_status))
        self.application.add_handler(CommandHandler("latest", self.show_latest))
        self.application.add_handler(CommandHandler("pause", self.pause_auto))
        self.application.add_handler(CommandHandler("resume", self.resume_auto))
        
        # Quick timeframe commands
        self.application.add_handler(CommandHandler("m3", self.cmd_m3))
        self.application.add_handler(CommandHandler("m5", self.cmd_m5))
        self.application.add_handler(CommandHandler("m15", self.cmd_m15))
        self.application.add_handler(CommandHandler("h1", self.cmd_h1))
        self.application.add_handler(CommandHandler("h4", self.cmd_h4))
        self.application.add_handler(CommandHandler("d1", self.cmd_d1))
        
        # Callbacks
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Schedule auto analysis
        job_queue = self.application.job_queue
        job_queue.run_repeating(
            self.automatic_analysis,
            interval=UPDATE_INTERVAL_MINUTES * 60,
            first=10
        )
        
        print("✅ Enhanced bot starting...")
        print(f"💰 Account: ${self.account_size} | Risk: {self.risk_percent}%")
        print(f"🤖 Auto analysis every {UPDATE_INTERVAL_MINUTES} minutes")
        print("Press Ctrl+C to stop\n")
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Run the enhanced bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n❌ ERROR: Missing Telegram credentials!")
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    # Customize these settings
    ACCOUNT_SIZE = 100  # Your account size
    RISK_PERCENT = 5    # Risk percentage per trade (5% = $5 on $100)
    
    bot = EnhancedTradingBot(
        account_size=ACCOUNT_SIZE,
        risk_percent=RISK_PERCENT
    )
    bot.run()


if __name__ == "__main__":
    main()

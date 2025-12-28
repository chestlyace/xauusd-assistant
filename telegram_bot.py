#!/usr/bin/env python3
"""
Interactive Telegram Bot for On-Demand XAUUSD Analysis

Commands:
  /start - Welcome message and command list
  /analyze [timeframe] - Run analysis (e.g., /analyze M3, /analyze H1)
  /m1, /m3, /m5, /m15, /m30 - Quick timeframe analysis
  /h1, /h4, /d1 - Longer timeframe analysis
  /status - Show system status and statistics
  /help - Show command list
"""

import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from data_collector import DataCollector
from analyzer import MarketAnalyzer
from logger import TradingLogger
from config import *

class TradingBot:
    def __init__(self):
        self.collector = DataCollector()
        self.logger = TradingLogger()
        self.is_analyzing = False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message with quick action buttons"""
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
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_msg = """
🤖 <b>XAUUSD Trading Assistant</b>

Get AI-powered market analysis on any timeframe!

<b>Quick Actions:</b>
Tap a button below for instant analysis

<b>Commands:</b>
/analyze M3 - Custom timeframe
/m3, /m5, /m15 - Ultra-short term
/h1, /h4 - Intraday
/d1 - Swing trading
/status - System statistics

Choose a timeframe to begin:
        """
        
        await update.message.reply_text(
            welcome_msg,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    
    async def analyze_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /analyze [timeframe] command"""
        # Get timeframe from command
        if context.args and len(context.args) > 0:
            timeframe = context.args[0].upper()
        else:
            timeframe = 'M15'  # Default
        
        await self.run_analysis(update, timeframe)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('analyze_'):
            timeframe = query.data.replace('analyze_', '')
            await self.run_analysis(update, timeframe, is_callback=True)
        elif query.data == 'status':
            await self.show_status(update, is_callback=True)
    
    async def run_analysis(self, update: Update, timeframe: str, is_callback: bool = False):
        """Run analysis for given timeframe"""
        if self.is_analyzing:
            msg = "⏳ Analysis already in progress. Please wait..."
            if is_callback:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.message.reply_text(msg)
            return
        
        self.is_analyzing = True
        
        try:
            # Validate timeframe
            valid_timeframes = ['M1', 'M3', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
            if timeframe not in valid_timeframes:
                msg = f"❌ Invalid timeframe: {timeframe}\nValid: {', '.join(valid_timeframes)}"
                if is_callback:
                    await update.callback_query.edit_message_text(msg)
                else:
                    await update.message.reply_text(msg)
                return
            
            # Send initial message
            status_msg = f"🔄 Running {timeframe} analysis...\n⏳ Collecting market data..."
            
            if is_callback:
                message = await update.callback_query.edit_message_text(status_msg)
            else:
                message = await update.message.reply_text(status_msg)
            
            # Collect data
            market_data = self.collector.get_market_data()
            
            if not market_data or not market_data.get('current_price'):
                error_msg = "❌ Failed to collect market data. Please try again."
                await message.edit_text(error_msg)
                return
            
            # Update status
            await message.edit_text(f"🔄 Running {timeframe} analysis...\n🤖 Analyzing with AI...")
            
            # Analyze
            analyzer = MarketAnalyzer(timeframe=timeframe)
            analysis = analyzer.analyze_market(market_data)
            
            if not analysis.get('success'):
                error_msg = f"❌ Analysis failed: {analysis.get('error', 'Unknown error')}"
                await message.edit_text(error_msg)
                return
            
            # Format and send result
            response = self.format_analysis(analysis, timeframe)
            
            # Add quick action buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Analyze Again", callback_data=f'analyze_{timeframe}'),
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
        """Format analysis for Telegram with HTML"""
        signal = analysis['trade_recommendation']
        confidence = analysis['confidence']
        price = analysis['current_price']
        mode = analysis['analysis_mode'].upper()
        
        # Choose emoji
        if signal == 'BUY':
            emoji = '🟢'
            signal_emoji = '📈'
        elif signal == 'SELL':
            emoji = '🔴'
            signal_emoji = '📉'
        else:
            emoji = '⚪'
            signal_emoji = '⏸️'
        
        # Build message
        msg = f"""
{emoji} <b>{signal_emoji} {signal} SIGNAL</b>

<b>⏱ Timeframe:</b> {timeframe} ({mode})
<b>💰 Price:</b> ${price:.2f}
<b>🎯 Confidence:</b> {confidence}/10
<b>📊 Bias:</b> {analysis['market_bias']} ({analysis['bias_strength']}/10)
<b>⚠️ Risk:</b> {analysis['risk_level']}
<b>🌍 Session:</b> {analysis.get('session', 'N/A')}
"""
        
        if signal != 'NO TRADE' and confidence >= 6:
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
        
        if analysis.get('key_factors') and len(analysis['key_factors']) > 0:
            msg += f"\n<b>🔑 Key Factors:</b>\n"
            for i, factor in enumerate(analysis['key_factors'][:3], 1):
                # Truncate long factors
                factor_text = factor if len(factor) <= 80 else factor[:77] + "..."
                msg += f"{i}. {factor_text}\n"
        
        if signal == 'NO TRADE':
            msg += f"\n<i>💡 No clear edge detected. Better to wait for higher confidence setup.</i>\n"
        
        msg += f"\n<code>ID: {analysis['analysis_id']}</code>"
        
        return msg
    
    async def show_status(self, update: Update, is_callback: bool = False):
        """Show system status and statistics"""
        stats = self.logger.get_statistics()
        
        if stats:
            signal_rate = stats['trade_signal_rate']
            
            # Calculate quality metrics
            if stats['total_analyses'] > 0:
                quality = "🟢 Active" if stats['average_confidence'] >= 6.5 else "🟡 Moderate" if stats['average_confidence'] >= 5.5 else "🔴 Low"
            else:
                quality = "⚪ No Data"
            
            msg = f"""
📊 <b>System Statistics</b>

<b>Status:</b> {quality}
<b>Total Analyses:</b> {stats['total_analyses']}
<b>Avg Confidence:</b> {stats['average_confidence']}/10

<b>📈 Signal Distribution:</b>
├ BUY: {stats['buy_signals']} ({stats['buy_signals']/max(stats['total_analyses'],1)*100:.1f}%)
├ SELL: {stats['sell_signals']} ({stats['sell_signals']/max(stats['total_analyses'],1)*100:.1f}%)
└ NO TRADE: {stats['no_trade_signals']} ({stats['no_trade_signals']/max(stats['total_analyses'],1)*100:.1f}%)

<b>🎯 Trade Signal Rate:</b> {signal_rate:.1f}%

<b>📊 Mode Usage:</b>
├ Intraday: {stats['intraday_analyses']}
└ Scalping: {stats['scalping_analyses']}

<i>Updated: {stats.get('timestamp', 'N/A')}</i>
            """
            
            keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data='status')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            msg = "📊 No data available yet.\n\nRun an analysis first to see statistics!"
            reply_markup = None
        
        if is_callback:
            await update.callback_query.edit_message_text(
                msg,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                msg,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    
    # Quick timeframe commands
    async def cmd_m1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'M1')
    
    async def cmd_m3(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'M3')
    
    async def cmd_m5(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'M5')
    
    async def cmd_m15(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'M15')
    
    async def cmd_m30(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'M30')
    
    async def cmd_h1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'H1')
    
    async def cmd_h4(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'H4')
    
    async def cmd_d1(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.run_analysis(update, 'D1')

def main():
    """Run the interactive bot"""
    print("="*70)
    print("XAUUSD INTERACTIVE TELEGRAM BOT")
    print("="*70)
    print(f"Bot Token: {TELEGRAM_BOT_TOKEN[:20]}..." if TELEGRAM_BOT_TOKEN else "❌ NO TOKEN")
    print(f"Chat ID: {TELEGRAM_CHAT_ID}")
    print("="*70)
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("\n❌ ERROR: Missing Telegram credentials!")
        print("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return
    
    bot = TradingBot()
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.start))
    application.add_handler(CommandHandler("analyze", bot.analyze_command))
    application.add_handler(CommandHandler("status", bot.show_status))
    
    # Quick timeframe commands
    application.add_handler(CommandHandler("m1", bot.cmd_m1))
    application.add_handler(CommandHandler("m3", bot.cmd_m3))
    application.add_handler(CommandHandler("m5", bot.cmd_m5))
    application.add_handler(CommandHandler("m15", bot.cmd_m15))
    application.add_handler(CommandHandler("m30", bot.cmd_m30))
    application.add_handler(CommandHandler("h1", bot.cmd_h1))
    application.add_handler(CommandHandler("h4", bot.cmd_h4))
    application.add_handler(CommandHandler("d1", bot.cmd_d1))
    
    # Add callback query handler for buttons
    application.add_handler(CallbackQueryHandler(bot.button_callback))
    
    # Start bot
    print("\n✅ Bot is running!")
    print("📱 Open Telegram and send /start to your bot")
    print("Press Ctrl+C to stop\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
XAUUSD Trading Assistant - Main Application
Automated market analysis with AI-powered insights
"""

import time
import schedule
from datetime import datetime
from data_collector import DataCollector
from analyzer import MarketAnalyzer
from notifier import Notifier
from logger import TradingLogger
from config import *

class TradingAssistant:
    def __init__(self, analysis_mode='intraday'):
        """Initialize the trading assistant
        
        Args:
            analysis_mode: 'intraday' or 'scalping'
        """
        print("="*70)
        print("XAUUSD TRADING ASSISTANT")
        print("="*70)
        print(f"Mode: {analysis_mode.upper()}")
        print(f"Update Interval: {UPDATE_INTERVAL_MINUTES} minutes")
        print(f"Alert Methods: {', '.join(ALERT_METHODS)}")
        print("="*70 + "\n")
        
        self.analysis_mode = analysis_mode
        self.collector = DataCollector()
        self.analyzer = MarketAnalyzer(analysis_mode=analysis_mode)
        self.notifier = Notifier()
        self.logger = TradingLogger()
        
        self.run_count = 0
        self.last_run_time = None
        self.is_running = False
    
    def is_trading_hours(self):
        """Check if we're in active trading hours"""
        if not TRADING_ACTIVE:
            return False
        
        now = datetime.now()
        
        # Check if it's a trading day (Monday-Friday for forex)
        if now.weekday() not in TRADING_DAYS:
            return False
        
        return True
    
    def run_analysis(self):
        """Main analysis workflow - runs once"""
        if self.is_running:
            print("⚠️  Previous analysis still running, skipping...")
            return
        
        self.is_running = True
        self.run_count += 1
        self.last_run_time = datetime.now()
        
        try:
            print(f"\n{'='*70}")
            print(f"ANALYSIS RUN #{self.run_count}")
            print(f"Time: {self.last_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Mode: {self.analysis_mode.upper()}")
            print("="*70)
            
            # Check if we should trade
            if not self.is_trading_hours():
                print("⏸️  Outside trading hours - skipping analysis")
                self.notifier.send_info("Outside trading hours", "Status")
                self.is_running = False
                return
            
            # Step 1: Collect market data
            print("\n[1/4] Collecting market data...")
            market_data = self.collector.get_market_data()
            
            if not market_data or not market_data.get('current_price'):
                print("❌ Failed to collect market data")
                self.notifier.send_alert({'error': 'Data collection failed'}, alert_type='error')
                self.is_running = False
                return
            
            price = market_data['current_price']['price']
            news_count = len(market_data.get('news', []))
            high_rel_count = len(market_data.get('high_relevance_news', []))
            
            print(f"  ✓ Price: ${price:.2f}")
            print(f"  ✓ News: {news_count} articles ({high_rel_count} high relevance)")
            
            # Step 2: Save market data
            if SAVE_MARKET_DATA:
                self.logger.save_market_data(market_data)
            
            # Step 3: Analyze with AI
            print("\n[2/4] Analyzing with AI...")
            analysis = self.analyzer.analyze_market(market_data)
            
            if not analysis.get('success'):
                print(f"❌ Analysis failed: {analysis.get('error')}")
                self.notifier.send_alert(analysis, alert_type='error')
                self.is_running = False
                return
            
            trade_rec = analysis['trade_recommendation']
            confidence = analysis['confidence']
            
            print(f"  ✓ Signal: {trade_rec}")
            print(f"  ✓ Confidence: {confidence}/10")
            print(f"  ✓ Bias: {analysis['market_bias']} ({analysis['bias_strength']}/10)")
            
            # Step 4: Log analysis
            print("\n[3/4] Logging analysis...")
            if LOG_ALL_ANALYSES or trade_rec != 'NO TRADE':
                self.logger.log_analysis(analysis, market_data)
                print("  ✓ Analysis logged")
            
            # Step 5: Send alerts if needed
            print("\n[4/4] Checking alert criteria...")
            should_alert = self.analyzer.should_alert(analysis)
            
            if should_alert:
                print("  🔔 ALERT TRIGGERED - Sending notifications...")
                self.notifier.send_alert(analysis, alert_type='signal')
                
                # Log as potential trade for performance tracking
                self.logger.log_performance(analysis, outcome='pending')
            else:
                if trade_rec == 'NO TRADE':
                    print("  ⏸️  NO TRADE - No alert sent")
                else:
                    print(f"  ⏸️  Signal doesn't meet threshold (conf: {confidence}, threshold: {CONFIDENCE_THRESHOLD})")
            
            # Print summary
            print(f"\n{'='*70}")
            print("ANALYSIS COMPLETE")
            print("="*70)
            print(f"Total Runs: {self.run_count}")
            print(f"Next run: {UPDATE_INTERVAL_MINUTES} minutes")
            
            # Show API usage
            self.collector.print_api_usage()
            
            # Show statistics every 10 runs
            if self.run_count % 10 == 0:
                self.logger.print_statistics()
            
        except KeyboardInterrupt:
            raise  # Allow Ctrl+C to propagate
        except Exception as e:
            print(f"\n❌ Unexpected error in analysis: {e}")
            import traceback
            traceback.print_exc()
            self.notifier.send_alert({'error': str(e), 'timestamp': datetime.now().isoformat()}, alert_type='error')
        finally:
            self.is_running = False
    
    def start_continuous(self):
        """Start continuous monitoring with scheduled runs"""
        print("\n🚀 Starting continuous monitoring...")
        print(f"⏰ Running every {UPDATE_INTERVAL_MINUTES} minutes")
        print("Press Ctrl+C to stop\n")
        
        # Send startup notification
        self.notifier.send_info(
            f"Trading Assistant started in {self.analysis_mode.upper()} mode. Running every {UPDATE_INTERVAL_MINUTES} minutes.",
            "Startup"
        )
        
        # Run immediately on start
        self.run_analysis()
        
        # Schedule future runs
        schedule.every(UPDATE_INTERVAL_MINUTES).minutes.do(self.run_analysis)
        
        # Main loop
        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping trading assistant...")
            self.notifier.send_info(
                f"Trading Assistant stopped after {self.run_count} analyses",
                "Shutdown"
            )
            self.logger.print_statistics()
            print("\n✓ Shutdown complete")
    
    def start_once(self):
        """Run analysis once and exit"""
        print("\n🔍 Running single analysis...\n")
        self.run_analysis()
        print("\n✓ Single run complete")


def main():
    """Main entry point"""
    import sys
    
    # Parse command line arguments
    mode = ANALYSIS_MODE  # Default from config
    run_mode = RUN_MODE  # Default from config
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['scalping', 'intraday']:
            mode = sys.argv[1]
        elif sys.argv[1] in ['once', 'continuous']:
            run_mode = sys.argv[1]
    
    if len(sys.argv) > 2:
        if sys.argv[2] in ['once', 'continuous']:
            run_mode = sys.argv[2]
    
    # Create and start assistant
    assistant = TradingAssistant(analysis_mode=mode)
    
    if run_mode == 'once':
        assistant.start_once()
    else:
        assistant.start_continuous()


if __name__ == "__main__":
    main()
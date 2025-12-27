#!/usr/bin/env python3
"""Force run analysis for testing - ignores trading hours"""

from data_collector import DataCollector
from analyzer import MarketAnalyzer
from notifier import Notifier
from logger import TradingLogger

print("="*70)
print("FORCED TEST RUN (Ignoring Trading Hours)")
print("="*70)

# Collect data
print("\n[1/4] Collecting market data...")
collector = DataCollector()
market_data = collector.get_market_data()

if not market_data or not market_data.get('current_price'):
    print("❌ Failed to collect data")
    exit(1)

price = market_data['current_price']['price']
print(f"  ✓ Price: ${price:.2f}")

# Analyze
print("\n[2/4] Analyzing with AI...")
analyzer = MarketAnalyzer(analysis_mode='intraday')
analysis = analyzer.analyze_market(market_data)

if not analysis.get('success'):
    print(f"❌ Analysis failed: {analysis.get('error')}")
    exit(1)

print(f"  ✓ Signal: {analysis['trade_recommendation']}")
print(f"  ✓ Confidence: {analysis['confidence']}/10")

# Log
print("\n[3/4] Logging...")
logger = TradingLogger()
logger.log_analysis(analysis, market_data)
print("  ✓ Logged")

# Alert
print("\n[4/4] Sending notifications...")
notifier = Notifier()

if analyzer.should_alert(analysis):
    print("  🔔 Alert criteria met - sending...")
    notifier.send_alert(analysis, alert_type='signal')
else:
    print("  ⏸️  No alert (criteria not met)")
    print("\n--- ANALYSIS SUMMARY ---")
    print(analyzer.generate_summary(analysis))

print("\n✓ Test complete!")
import json
import os
from datetime import datetime
from config import *

class TradingLogger:
    def __init__(self):
        """Initialize logging system"""
        self.ensure_data_directory()
        self.session_start = datetime.now().isoformat()
    
    def ensure_data_directory(self):
        """Create data directory if it doesn't exist"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            print(f"Created data directory: {DATA_DIR}")
    
    def log_analysis(self, analysis, market_data=None):
        """Log a complete analysis with optional market data
        
        Args:
            analysis: Structured analysis from analyzer
            market_data: Optional raw market data
        """
        try:
            # Load existing log
            log_data = self.load_json(LOG_FILE, default=[])
            
            # Create log entry
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'analysis_id': analysis.get('analysis_id'),
                'analysis': {
                    'mode': analysis.get('analysis_mode'),
                    'session': analysis.get('session'),
                    'trade_recommendation': analysis.get('trade_recommendation'),
                    'confidence': analysis.get('confidence'),
                    'market_bias': analysis.get('market_bias'),
                    'bias_strength': analysis.get('bias_strength'),
                    'risk_level': analysis.get('risk_level'),
                    'current_price': analysis.get('current_price'),
                    'stop_loss': analysis.get('stop_loss'),
                    'take_profit_1': analysis.get('take_profit_1'),
                    'take_profit_2': analysis.get('take_profit_2'),
                    'key_factors': analysis.get('key_factors', []),
                    'invalidation': analysis.get('invalidation')
                }
            }
            
            # Add market data summary if available
            if market_data and SAVE_MARKET_DATA:
                log_entry['market_summary'] = market_data.get('market_data_summary', {})
            
            # Append to log
            log_data.append(log_entry)
            
            # Keep only last 500 entries to prevent huge files
            if len(log_data) > 500:
                log_data = log_data[-500:]
            
            # Save
            self.save_json(LOG_FILE, log_data)
            
            return True
            
        except Exception as e:
            print(f"Error logging analysis: {e}")
            return False
    
    def log_performance(self, analysis, outcome=None, pnl=None):
        """Log trading performance (for paper trading tracking)
        
        Args:
            analysis: Original analysis that generated signal
            outcome: 'win', 'loss', 'breakeven', 'pending'
            pnl: Profit/loss amount (optional)
        """
        try:
            perf_data = self.load_json(PERFORMANCE_LOG, default=[])
            
            perf_entry = {
                'timestamp': datetime.now().isoformat(),
                'analysis_id': analysis.get('analysis_id'),
                'trade_recommendation': analysis.get('trade_recommendation'),
                'confidence': analysis.get('confidence'),
                'entry_price': analysis.get('current_price'),
                'stop_loss': analysis.get('stop_loss'),
                'take_profit_1': analysis.get('take_profit_1'),
                'outcome': outcome,
                'pnl': pnl
            }
            
            perf_data.append(perf_entry)
            
            # Keep last 200 trades
            if len(perf_data) > 200:
                perf_data = perf_data[-200:]
            
            self.save_json(PERFORMANCE_LOG, perf_data)
            
            return True
            
        except Exception as e:
            print(f"Error logging performance: {e}")
            return False
    
    def get_statistics(self):
        """Calculate statistics from logged analyses"""
        try:
            log_data = self.load_json(LOG_FILE, default=[])
            
            if not log_data:
                return None
            
            total = len(log_data)
            
            # Count by recommendation
            buy_count = sum(1 for entry in log_data if entry['analysis']['trade_recommendation'] == 'BUY')
            sell_count = sum(1 for entry in log_data if entry['analysis']['trade_recommendation'] == 'SELL')
            no_trade_count = sum(1 for entry in log_data if entry['analysis']['trade_recommendation'] == 'NO TRADE')
            
            # Average confidence
            confidences = [entry['analysis']['confidence'] for entry in log_data if entry['analysis'].get('confidence')]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Count by mode
            intraday_count = sum(1 for entry in log_data if entry['analysis']['mode'] == 'intraday')
            scalping_count = sum(1 for entry in log_data if entry['analysis']['mode'] == 'scalping')
            
            stats = {
                'total_analyses': total,
                'buy_signals': buy_count,
                'sell_signals': sell_count,
                'no_trade_signals': no_trade_count,
                'average_confidence': round(avg_confidence, 2),
                'intraday_analyses': intraday_count,
                'scalping_analyses': scalping_count,
                'trade_signal_rate': round((buy_count + sell_count) / total * 100, 1) if total > 0 else 0
            }
            
            return stats
            
        except Exception as e:
            print(f"Error calculating statistics: {e}")
            return None
    
    def get_recent_analyses(self, count=10):
        """Get most recent analyses"""
        try:
            log_data = self.load_json(LOG_FILE, default=[])
            return log_data[-count:] if log_data else []
        except Exception as e:
            print(f"Error getting recent analyses: {e}")
            return []
    
    def save_market_data(self, market_data):
        """Save raw market data for historical review"""
        if not SAVE_MARKET_DATA:
            return False
        
        try:
            history = self.load_json(MARKET_DATA_FILE, default=[])
            
            data_entry = {
                'timestamp': datetime.now().isoformat(),
                'price': market_data.get('current_price', {}),
                'indicators': market_data.get('technical_indicators', {}),
                'news_count': len(market_data.get('news', [])),
                'high_rel_news_count': len(market_data.get('high_relevance_news', []))
            }
            
            history.append(data_entry)
            
            # Keep last 1000 entries
            if len(history) > 1000:
                history = history[-1000:]
            
            self.save_json(MARKET_DATA_FILE, history)
            
            return True
            
        except Exception as e:
            print(f"Error saving market data: {e}")
            return False
    
    def load_json(self, filepath, default=None):
        """Safely load JSON file"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
            return default if default is not None else {}
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return default if default is not None else {}
    
    def save_json(self, filepath, data):
        """Safely save JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving {filepath}: {e}")
            return False
    
    def print_statistics(self):
        """Print current statistics to console"""
        stats = self.get_statistics()
        
        if not stats:
            print("\nNo statistics available yet.")
            return
        
        print("\n" + "="*60)
        print("ANALYSIS STATISTICS")
        print("="*60)
        print(f"Total Analyses: {stats['total_analyses']}")
        print(f"Average Confidence: {stats['average_confidence']}/10")
        print(f"\nSignal Distribution:")
        print(f"  BUY signals: {stats['buy_signals']}")
        print(f"  SELL signals: {stats['sell_signals']}")
        print(f"  NO TRADE: {stats['no_trade_signals']}")
        print(f"  Trade Signal Rate: {stats['trade_signal_rate']}%")
        print(f"\nMode Distribution:")
        print(f"  Intraday: {stats['intraday_analyses']}")
        print(f"  Scalping: {stats['scalping_analyses']}")
        print("="*60 + "\n")


# Test the logger
if __name__ == "__main__":
    print("Testing Logger System...")
    
    logger = TradingLogger()
    
    # Test with mock data
    mock_analysis = {
        'analysis_id': 'test_456',
        'timestamp': datetime.now().isoformat(),
        'analysis_mode': 'intraday',
        'session': 'LONDON',
        'current_price': 4510.50,
        'trade_recommendation': 'BUY',
        'confidence': 7,
        'market_bias': 'BULLISH',
        'bias_strength': 8,
        'risk_level': 'MEDIUM',
        'stop_loss': 4500.00,
        'take_profit_1': 4530.00,
        'key_factors': ['Test factor 1', 'Test factor 2']
    }
    
    print("\n1. Logging analysis...")
    logger.log_analysis(mock_analysis)
    print("  ✓ Analysis logged")
    
    print("\n2. Logging performance...")
    logger.log_performance(mock_analysis, outcome='pending')
    print("  ✓ Performance logged")
    
    print("\n3. Getting statistics...")
    logger.print_statistics()
    
    print("\n4. Getting recent analyses...")
    recent = logger.get_recent_analyses(count=3)
    print(f"  Found {len(recent)} recent analyses")
    
    print("\n✓ Logger test complete!")
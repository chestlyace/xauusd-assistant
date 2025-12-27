import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import *

class Notifier:
    def __init__(self):
        """Initialize notification system"""
        self.notification_count = 0
        self.enabled_methods = ALERT_METHODS
        
        # Validate configurations
        if 'email' in self.enabled_methods and not EMAIL_ENABLED:
            print("Warning: Email in ALERT_METHODS but EMAIL_ENABLED=False")
            self.enabled_methods.remove('email')
        
        if 'telegram' in self.enabled_methods and not TELEGRAM_ENABLED:
            print("Warning: Telegram in ALERT_METHODS but TELEGRAM_ENABLED=False")
            self.enabled_methods.remove('telegram')
    
    def send_alert(self, analysis, alert_type='signal'):
        """Send alert through all enabled channels
        
        Args:
            analysis: Structured analysis dict from analyzer
            alert_type: 'signal', 'error', 'info'
        """
        self.notification_count += 1
        
        # Generate message
        if alert_type == 'signal':
            message = self.format_signal_alert(analysis)
            subject = f"🔔 XAUUSD {analysis['trade_recommendation']} Signal"
        elif alert_type == 'error':
            message = self.format_error_alert(analysis)
            subject = "⚠️ XAUUSD Analyzer Error"
        else:
            message = str(analysis)
            subject = "ℹ️ XAUUSD Info"
        
        # Send through all enabled channels
        results = {}
        
        if 'console' in self.enabled_methods:
            results['console'] = self.send_console(message, subject)
        
        if 'file' in self.enabled_methods:
            results['file'] = self.send_file(message, subject)
        
        if 'email' in self.enabled_methods:
            results['email'] = self.send_email(message, subject)
        
        if 'telegram' in self.enabled_methods:
            results['telegram'] = self.send_telegram(message, subject)
        
        return results
    
    def format_signal_alert(self, analysis):
        """Format a trading signal alert"""
        trade = analysis['trade_recommendation']
        confidence = analysis['confidence']
        price = analysis.get('current_price', 0)
        mode = analysis['analysis_mode'].upper()
        
        message = f"""
{'='*60}
🚨 XAUUSD TRADING SIGNAL
{'='*60}

Mode: {mode}
Signal: {trade}
Confidence: {confidence}/10
Current Price: ${price:.2f}
Session: {analysis.get('session', 'N/A')}
Risk Level: {analysis['risk_level']}

Market Bias: {analysis['market_bias']} (Strength: {analysis['bias_strength']}/10)
"""
        
        if trade != 'NO TRADE':
            message += f"\n--- TRADE SETUP ---\n"
            message += f"Entry: ~${price:.2f}\n"
            
            if analysis.get('stop_loss'):
                sl = analysis['stop_loss']
                risk = abs(price - sl)
                message += f"Stop Loss: ${sl:.2f} (Risk: ${risk:.2f})\n"
            
            if analysis.get('take_profit_1'):
                tp1 = analysis['take_profit_1']
                reward = abs(tp1 - price)
                rr = reward / risk if risk > 0 else 0
                message += f"Target 1: ${tp1:.2f} (Reward: ${reward:.2f}, R:R {rr:.2f})\n"
            
            if analysis.get('take_profit_2'):
                message += f"Target 2: ${analysis['take_profit_2']:.2f}\n"
        
        if analysis.get('key_factors'):
            message += f"\n--- KEY FACTORS ---\n"
            for factor in analysis['key_factors'][:3]:
                message += f"• {factor}\n"
        
        message += f"\n--- INVALIDATION ---\n"
        message += f"{analysis.get('invalidation', 'Not specified')[:150]}\n"
        
        message += f"\nAnalysis ID: {analysis['analysis_id']}"
        message += f"\nTimestamp: {analysis['timestamp']}"
        message += f"\n{'='*60}"
        
        return message
    
    def format_error_alert(self, error_info):
        """Format an error alert"""
        message = f"""
{'='*60}
⚠️ ANALYZER ERROR
{'='*60}

Error: {error_info.get('error', 'Unknown error')}
Timestamp: {error_info.get('timestamp', 'N/A')}

This may require attention. Check logs for details.
{'='*60}
"""
        return message
    
    def send_console(self, message, subject):
        """Print alert to console"""
        try:
            print(f"\n{'='*60}")
            print(subject)
            print('='*60)
            print(message)
            return True
        except Exception as e:
            print(f"Console notification error: {e}")
            return False
    
    def send_file(self, message, subject):
        """Append alert to alerts file"""
        try:
            alert_file = f"{DATA_DIR}/alerts.txt"
            
            with open(alert_file, 'a') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"{subject}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write('='*60 + '\n')
                f.write(message)
                f.write('\n\n')
            
            return True
        except Exception as e:
            print(f"File notification error: {e}")
            return False
    
    def send_email(self, message, subject):
        """Send alert via email"""
        if not EMAIL_ENABLED:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_FROM
            msg['To'] = EMAIL_TO
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            print(f"  ✓ Email sent to {EMAIL_TO}")
            return True
            
        except Exception as e:
            print(f"  ✗ Email error: {e}")
            return False
    
    def send_telegram(self, message, subject):
        """Send alert via Telegram"""
        if not TELEGRAM_ENABLED:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            
            # Combine subject and message
            full_message = f"<b>{subject}</b>\n\n<pre>{message}</pre>"
            
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': full_message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"  ✓ Telegram message sent")
                return True
            else:
                print(f"  ✗ Telegram error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ✗ Telegram error: {e}")
            return False
    
    def send_info(self, message, title="Info"):
        """Send a simple info notification"""
        if 'console' in self.enabled_methods:
            print(f"\nℹ️  {title}: {message}")
        
        if 'file' in self.enabled_methods:
            try:
                with open(f"{DATA_DIR}/alerts.txt", 'a') as f:
                    f.write(f"\n[{datetime.now().isoformat()}] {title}: {message}\n")
            except:
                pass


# Test the notifier
if __name__ == "__main__":
    print("Testing Notifier System...")
    
    notifier = Notifier()
    
    # Test with mock analysis
    mock_analysis = {
        'success': True,
        'analysis_id': 'test_123',
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
        'take_profit_2': 4550.00,
        'key_factors': [
            'Strong bullish momentum above SMA20',
            'Breaking key resistance at $4505',
            'Positive USD weakness supporting gold'
        ],
        'invalidation': 'Break below $4500 would invalidate the setup'
    }
    
    print("\n1. Testing Signal Alert...")
    notifier.send_alert(mock_analysis, alert_type='signal')
    
    print("\n2. Testing Error Alert...")
    mock_error = {
        'error': 'API rate limit exceeded',
        'timestamp': datetime.now().isoformat()
    }
    notifier.send_alert(mock_error, alert_type='error')
    
    print("\n3. Testing Info Message...")
    notifier.send_info("System started successfully", "Startup")
    
    print(f"\n✓ Notifier test complete! Total notifications: {notifier.notification_count}")
    print(f"Enabled methods: {notifier.enabled_methods}")
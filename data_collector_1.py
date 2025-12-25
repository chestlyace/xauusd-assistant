import requests
import feedparser
import json
import time
from datetime import datetime, timedelta
from config import *

class DataCollector:
    def __init__(self):
        self.api_call_count = {
            'alpha_vantage': 0,
            'news_api': 0,
            'newsdata_io': 0,
            'twelve_data': 0,
            'finnhub': 0
        }
    
    # ===== MARKET DATA METHODS =====
    
    def get_xauusd_price_alphavantage(self):
        """Get current XAUUSD price from Alpha Vantage"""
        try:
            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'CURRENCY_EXCHANGE_RATE',
                'from_currency': 'XAU',
                'to_currency': 'USD',
                'apikey': ALPHA_VANTAGE_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'Realtime Currency Exchange Rate' in data:
                rate_data = data['Realtime Currency Exchange Rate']
                self.api_call_count['alpha_vantage'] += 1
                
                return {
                    'price': float(rate_data['5. Exchange Rate']),
                    'bid': float(rate_data['8. Bid Price']),
                    'ask': float(rate_data['9. Ask Price']),
                    'timestamp': rate_data['6. Last Refreshed'],
                    'source': 'Alpha Vantage'
                }
            else:
                print(f"Alpha Vantage Error: {data}")
                return None
                
        except Exception as e:
            print(f"Error fetching from Alpha Vantage: {e}")
            return None
    
    def get_xauusd_price_twelvedata(self):
        """Get current XAUUSD price from Twelve Data"""
        try:
            url = f"https://api.twelvedata.com/price"
            params = {
                'symbol': 'XAU/USD',
                'apikey': TWELVE_DATA_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'price' in data:
                self.api_call_count['twelve_data'] += 1
                return {
                    'price': float(data['price']),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'Twelve Data'
                }
            return None
            
        except Exception as e:
            print(f"Error fetching from Twelve Data: {e}")
            return None
    
    def get_xauusd_price_finnhub(self):
        """Get current XAUUSD price from Finnhub"""
        try:
            url = f"https://finnhub.io/api/v1/forex/rates"
            params = {
                'base': 'XAU',
                'token': FINNHUB_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'quote' in data and 'USD' in data['quote']:
                self.api_call_count['finnhub'] += 1
                return {
                    'price': float(data['quote']['USD']),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'Finnhub'
                }
            return None
            
        except Exception as e:
            print(f"Error fetching from Finnhub: {e}")
            return None
    
    def get_current_price(self):
        """Get current price with fallback strategy"""
        print("Fetching current XAUUSD price...")
        
        # Try primary source
        price_data = self.get_xauusd_price_alphavantage()
        if price_data:
            return price_data
        
        # Fallback to Twelve Data
        print("Alpha Vantage failed, trying Twelve Data...")
        price_data = self.get_xauusd_price_twelvedata()
        if price_data:
            return price_data
        
        # Final fallback to Finnhub
        print("Twelve Data failed, trying Finnhub...")
        price_data = self.get_xauusd_price_finnhub()
        if price_data:
            return price_data
        
        print("All price sources failed!")
        return None
    
    def get_price_history(self, days=7):
        """Get historical price data for trend analysis"""
        try:
            url = f"https://api.twelvedata.com/time_series"
            params = {
                'symbol': 'XAU/USD',
                'interval': '1h',
                'outputsize': days * 24,
                'apikey': TWELVE_DATA_KEY
            }
            
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if 'values' in data:
                self.api_call_count['twelve_data'] += 1
                return {
                    'history': data['values'][:48],  # Last 48 hours
                    'source': 'Twelve Data'
                }
            return None
            
        except Exception as e:
            print(f"Error fetching price history: {e}")
            return None
    
    # ===== NEWS METHODS =====
    
    def get_news_newsapi(self, hours=24):
        """Get news from NewsAPI"""
        try:
            url = "https://newsapi.org/v2/everything"
            
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=hours)
            
            params = {
                'q': 'gold OR XAUUSD OR "gold price" OR "US dollar"',
                'from': from_date.isoformat(),
                'to': to_date.isoformat(),
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'apiKey': NEWS_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == 'ok':
                self.api_call_count['news_api'] += 1
                articles = []
                
                for article in data.get('articles', [])[:10]:
                    articles.append({
                        'title': article['title'],
                        'description': article.get('description', ''),
                        'source': article['source']['name'],
                        'url': article['url'],
                        'published': article['publishedAt']
                    })
                
                return articles
            return []
            
        except Exception as e:
            print(f"Error fetching from NewsAPI: {e}")
            return []
    
    def get_news_newsdata(self, hours=24):
        """Get news from NewsData.io"""
        try:
            url = "https://newsdata.io/api/1/news"
            
            params = {
                'apikey': NEWSDATA_IO_KEY,
                'q': 'gold OR forex OR XAUUSD',
                'language': 'en',
                'category': 'business',
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('status') == 'success':
                self.api_call_count['newsdata_io'] += 1
                articles = []
                
                for article in data.get('results', [])[:10]:
                    articles.append({
                        'title': article['title'],
                        'description': article.get('description', ''),
                        'source': article.get('source_id', 'Unknown'),
                        'url': article['link'],
                        'published': article.get('pubDate', '')
                    })
                
                return articles
            return []
            
        except Exception as e:
            print(f"Error fetching from NewsData.io: {e}")
            return []
    
    def get_rss_feeds(self):
        """Get news from RSS feeds (no API limits!)"""
        feeds = [
            'https://www.investing.com/rss/news_285.rss',  # Gold news
            'https://www.fxstreet.com/rss/gold',  # FXStreet gold
        ]
        
        articles = []
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    articles.append({
                        'title': entry.title,
                        'description': entry.get('summary', ''),
                        'source': 'RSS Feed',
                        'url': entry.link,
                        'published': entry.get('published', '')
                    })
            except Exception as e:
                print(f"Error parsing RSS feed {feed_url}: {e}")
        
        return articles
    
    def get_all_news(self):
        """Aggregate news from all sources"""
        print("Fetching news from multiple sources...")
        all_news = []
        
        # Try NewsAPI first (most reliable)
        news = self.get_news_newsapi()
        if news:
            all_news.extend(news)
            print(f"  ✓ Got {len(news)} articles from NewsAPI")
        
        # Add RSS feeds (no limits)
        rss_news = self.get_rss_feeds()
        if rss_news:
            all_news.extend(rss_news)
            print(f"  ✓ Got {len(rss_news)} articles from RSS")
        
        # If we need more, try NewsData.io
        if len(all_news) < 10:
            news = self.get_news_newsdata()
            if news:
                all_news.extend(news)
                print(f"  ✓ Got {len(news)} articles from NewsData.io")
        
        # Remove duplicates by title
        seen_titles = set()
        unique_news = []
        for article in all_news:
            if article['title'] not in seen_titles:
                seen_titles.add(article['title'])
                unique_news.append(article)
        
        print(f"Total unique articles: {len(unique_news)}")
        return unique_news
    
    def get_market_data(self):
        """Get complete market snapshot"""
        return {
            'current_price': self.get_current_price(),
            'price_history': self.get_price_history(),
            'news': self.get_all_news(),
            'timestamp': datetime.now().isoformat(),
            'api_usage': self.api_call_count.copy()
        }
    
    def print_api_usage(self):
        """Display API usage statistics"""
        print("\n" + "="*50)
        print("API USAGE STATISTICS")
        print("="*50)
        for api, count in self.api_call_count.items():
            limit = RATE_LIMITS.get(api, 'N/A')
            print(f"{api:20} {count:4}/{limit}")
        print("="*50 + "\n")


# Test the collector
if __name__ == "__main__":
    collector = DataCollector()
    
    print("Testing Data Collector...")
    print("\n1. Fetching current price...")
    price = collector.get_current_price()
    if price:
        print(f"   Price: ${price['price']:.2f}")
        print(f"   Source: {price['source']}")
    
    print("\n2. Fetching news...")
    news = collector.get_all_news()
    print(f"   Found {len(news)} articles")
    if news:
        print(f"   Latest: {news[0]['title'][:80]}...")
    
    print("\n3. Getting complete market data...")
    data = collector.get_market_data()
    
    collector.print_api_usage()
    
    print("✓ Data collection working!")
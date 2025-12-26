import requests
import feedparser
import json
import time
from datetime import datetime, timedelta, timezone
from config import (
    GEMINI_API_KEY,
    ALPHA_VANTAGE_KEY,
    TWELVE_DATA_KEY,
    FINNHUB_KEY,
    NEWS_API_KEY,
    NEWSDATA_IO_KEY,
    FMP_API_KEY,
    RATE_LIMITS,
    NEWS_KEYWORDS
)

# Optional API key for MarketAUX
try:
    from config import MARKETAUX_API_KEY
except ImportError:
    MARKETAUX_API_KEY = None

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
        if not ALPHA_VANTAGE_KEY:
            print("Alpha Vantage API Key is missing.")
            return None
            
        try:
            # Try FX_INTRADAY - more reliable for gold
            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'FX_INTRADAY',
                'from_symbol': 'XAU',
                'to_symbol': 'USD',
                'interval': '5min',
                'apikey': ALPHA_VANTAGE_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'Time Series FX (5min)' in data:
                # Get most recent entry
                time_series = data['Time Series FX (5min)']
                latest_time = list(time_series.keys())[0]
                latest_data = time_series[latest_time]
                
                self.api_call_count['alpha_vantage'] += 1
                
                return {
                    'price': float(latest_data['4. close']),
                    'bid': float(latest_data['1. open']),
                    'ask': float(latest_data['4. close']),
                    'timestamp': latest_time,
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
                    'timestamp': datetime.now(timezone.utc).isoformat(),
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
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'source': 'Finnhub'
                }
            return None
            
        except Exception as e:
            print(f"Error fetching from Finnhub: {e}")
            return None
    
    
    def get_current_price(self):
        """Get current price from multiple sources and aggregate"""
        print("Fetching current XAUUSD price from multiple sources...")
        
        sources = [
            ('Twelve Data', self.get_xauusd_price_twelvedata),
            # ('FMP', self.get_xauusd_price_fmp),
            ('Finnhub', self.get_xauusd_price_finnhub)
        ]
        
        prices = []
        
        for name, func in sources:
            try:
                data = func()
                if data and 1500 < data['price'] < 6000:
                    prices.append(data)
                    print(f"  ✓ {name}: ${data['price']:.2f}")
            except Exception as e:
                print(f"  ✗ {name} failed: {e}")
        
        if not prices:
            print("All price sources failed!")
            return None
        
        # Use the first successful price as primary
        primary = prices[0]
        
        # If we have multiple sources, calculate average for validation
        if len(prices) > 1:
            avg_price = sum(p['price'] for p in prices) / len(prices)
            primary['avg_price'] = avg_price
            primary['sources_count'] = len(prices)
            print(f"  → Average across {len(prices)} sources: ${avg_price:.2f}")
        
        return primary

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

    # def get_xauusd_price_fmp(self):
    #     """Get current XAUUSD price from FMP"""
    #     try:
    #         url = f"https://financialmodelingprep.com/api/v3/quote/XAUUSD"
    #         params = {'apikey': FMP_API_KEY}
            
    #         response = requests.get(url, params=params, timeout=10)

    #         if response.status_code != 200:
    #             print(f"Error fetching from FMP: {response.status_code}")
    #             return None

    #         data = response.json()
            
    #         if not data or len(data) == 0:
    #             print(f"  FMP returned no data. Check API key or symbol format.")
    #             return None
                
    #         quote = data[0]
    #         self.api_call_count['fmp'] = self.api_call_count.get('fmp', 0) + 1
                
    #         return {
    #                 'price': float(quote['price']),
    #                 'open': float(quote.get('open', 0)),
    #                 'high': float(quote.get('dayHigh', 0)),
    #                 'low': float(quote.get('dayLow', 0)),
    #                 'change': float(quote.get('change', 0)),
    #                 'change_percent': float(quote.get('changesPercentage', 0)),
    #                 'volume': quote.get('volume', 0),
    #                 'timestamp': datetime.now().isoformat(),
    #                 'source': 'FMP'
    #         }
            
    #     except Exception as e:
    #         print(f"Error fetching from FMP: {e}")
    #         return None

    # CALCULATE TECHNICAL INDICATORS
    def calculate_technical_indicators(self, history_data):
        """Calculate technical indicators from price history"""
        if not history_data or 'history' not in history_data:
            return None
        
        try:
            prices = [float(candle['close']) for candle in history_data['history'][:50]]
            
            if len(prices) < 20:
                return None
            
            # Simple Moving Averages
            sma_20 = sum(prices[:20]) / 20
            sma_50 = sum(prices[:50]) / 50 if len(prices) >= 50 else None
            
            # Price change metrics
            current_price = prices[0]
            price_24h_ago = prices[23] if len(prices) > 23 else prices[-1]
            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
            
            # Volatility (simple standard deviation)
            mean_price = sum(prices[:20]) / 20
            variance = sum((p - mean_price) ** 2 for p in prices[:20]) / 20
            volatility = variance ** 0.5
            
            # Trend detection
            recent_trend = "bullish" if prices[0] > prices[4] > prices[9] else \
                           "bearish" if prices[0] < prices[4] < prices[9] else "neutral"
            
            return {
                'sma_20': round(sma_20, 2),
                'sma_50': round(sma_50, 2) if sma_50 else None,
                'change_24h': round(change_24h, 2),
                'volatility': round(volatility, 2),
                'recent_trend': recent_trend,
                'current_vs_sma20': round(((current_price - sma_20) / sma_20) * 100, 2)
            }
        
        except Exception as e:
            print(f"Error calculating indicators: {e}")
            return None
    
    # ===== NEWS METHODS =====
    
    def _build_news_query(self, max_length=500):
        """Build a dynamic query string from configured keywords"""
        query_parts = []
        current_length = 0
        
        # Always include primary keywords first
        priority_keywords = ['gold', 'XAUUSD', 'gold price']
        for keyword in priority_keywords:
            # Quote multi-word phrases for exact match
            term = f'"{keyword}"' if ' ' in keyword else keyword
            if term not in query_parts:
                query_parts.append(term)
                current_length += len(term) + 4  # +4 for " OR "
        
        # Add other keywords until limit reached
        for keyword in NEWS_KEYWORDS:
            if keyword in priority_keywords:
                continue
                
            term = f'"{keyword}"' if ' ' in keyword else keyword
            # Check length limit (leave buffer)
            if current_length + len(term) + 4 > max_length:
                break
                
            query_parts.append(term)
            current_length += len(term) + 4
            
        return " OR ".join(query_parts)

    def get_news_marketaux(self):
        """Get news from MarketAUX"""
        if not MARKETAUX_API_KEY:
            return []
        try:
            url = "https://api.marketaux.com/v1/news/all"
            params = {
                'api_token': MARKETAUX_API_KEY,
                'symbols': 'XAUUSD,GC=F',
                'filter_entities': 'true',
                'language': 'en',
                'limit': 10
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if 'data' in data:
                self.api_call_count['marketaux'] = self.api_call_count.get('marketaux', 0) + 1
                articles = []
                
                for article in data['data']:
                    articles.append({
                        'title': article['title'],
                        'description': article.get('description', ''),
                        'source': article.get('source', 'MarketAUX'),
                        'url': article['url'],
                        'published': article.get('published_at', ''),
                        'sentiment': article.get('entities', [{}])[0].get('sentiment_score', 0) if article.get('entities') else 0
                    })
                
                return articles
            return []
            
        except Exception as e:
            print(f"Error fetching from MarketAUX: {e}")
            return []
    
    def _calculate_relevance(self, title, description):
        """Calculate relevance score from title and description text"""
        combined = (title + ' ' + description).lower()
        
        # High relevance keywords
        high_value_keywords = ['xauusd', 'gold price', 'gold futures', 'gold rally', 
                               'gold drops', 'federal reserve', 'fed rate', 'inflation']
        
        # Medium relevance keywords
        medium_value_keywords = ['gold', 'dollar', 'usd', 'treasury', 'yield',
                                'safe haven', 'precious metals', 'bullion']
        
        score = 0
        
        # Check high value keywords
        for keyword in high_value_keywords:
            if keyword in combined:
                score += 3
        
        # Check medium value keywords
        for keyword in medium_value_keywords:
            if keyword in combined:
                score += 1
        
        return min(score, 10)  # Cap at 10

    def calculate_relevance_score(self, article):
        """Calculate how relevant an article is to XAUUSD trading"""
        title = article.get('title', '').lower()
        description = article.get('description', '').lower()
        combined = title + ' ' + description
    
        score = 0
    
        # Tier 1: Direct gold mentions (8 points) - INCREASED
        tier1_keywords = ['gold', 'xauusd', 'xau/usd', 'gold price', 'gold futures']
        for keyword in tier1_keywords:
            if keyword in combined:
                score += 8  # Was 5, now 8
                break
    
        # Tier 2: Strong market drivers (4 points)
        tier2_keywords = ['federal reserve', 'fed rate', 'fed cut', 'fed hike',
                      'powell', 'inflation', 'cpi', 'treasury yield']
        if any(keyword in combined for keyword in tier2_keywords):
            score += 4  # Was 2, now 4
    
        # Tier 3: General forex (2 points)
        tier3_keywords = ['dollar', 'usd', 'forex', 'currency', 'bullion']
        if any(keyword in combined for keyword in tier3_keywords):
            score += 2  # Was 1, now 2
    
        return min(score, 15)

    # ECONOMIC CALENDAR EVENTS FROM FMP
    # def get_economic_calendar(self):
    #     """Get upcoming economic events that affect gold/USD"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         future = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
            
    #         url = "https://financialmodelingprep.com/api/v3/economic_calendar"
    #         params = {
    #             'apikey': FMP_API_KEY,
    #             'from': today,
    #             'to': future
    #         }
            
    #         response = requests.get(url, params=params, timeout=10)

    #         if response.status_code != 200:
    #             print(f"Error fetching from FMP: {response.status_code}")
    #             return []

    #         data = response.json()

    #         if not isinstance(data, list):
    #             print(f"Economic Calendar unexpected format: {type(data)}")
    #             return []
            
    #         # Filter for high-impact USD events
    #         important_events = []
    #         for event in data:

    #             if not isinstance(event, dict):
    #                 print(f"Economic Calendar unexpected format: {type(event)}")
    #                 continue

    #             if event.get('currency') == 'USD' and event.get('impact') in ['High', 'Medium']:
    #                 important_events.append({
    #                     'event': event.get('event', 'Unknown Event'),
    #                     'date': event.get('date', ''),
    #                     'impact': event.get('impact', ''),
    #                     'actual': event.get('actual', 'N/A'),
    #                     'estimate': event.get('estimate', 'N/A'),
    #                     'previous': event.get('previous', 'N/A')
    #                 })
    #         print(f"  ✓ Found {len(important_events)} important economic events")
    #         return important_events[:5]  # Next 5 important events
            
    #     except Exception as e:
    #         print(f"  Economic Calendar Exception: {str(e)}")
    #         return []

    
    def get_news_newsapi(self, hours=24):
        """Get news from NewsAPI"""
        try:
            url = "https://newsapi.org/v2/everything"
            
            # Calculate date range
            to_date = datetime.now()
            from_date = to_date - timedelta(hours=hours)
            
            params = {
                'q': self._build_news_query(max_length=300),
                'from': from_date.isoformat(),
                'to': to_date.isoformat(),
                'language': 'en',
                'sortBy': 'publishedAt',
                'pageSize': 20,
                'apiKey': NEWS_API_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Debug info
            if data.get('status') != 'ok':
                print(f"  NewsAPI Error: {data.get('message', 'Unknown error')}")
                return []
            
            if data.get('status') == 'ok':
                self.api_call_count['news_api'] += 1
                articles = []
                
                for article in data.get('articles', [])[:10]:
                    articles.append({
                        'title': article['title'],
                        'description': article.get('description', ''),
                        'source': article['source']['name'],
                        'url': article['url'],
                        'published': article['publishedAt'],
                        'relevance_score': self._calculate_relevance(
                            article['title'], 
                            article.get('description', '')
                        )
                    })
                
                return articles
            return []
            
        except Exception as e:
            print(f"Error fetching from NewsAPI: {e}")
            return []
    
    def get_news_finnhub(self):
        """Get forex/gold news from Finnhub"""
        try:
            url = "https://finnhub.io/api/v1/news"
            params = {
                'category': 'forex',
                'token': FINNHUB_KEY
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            self.api_call_count['finnhub'] = self.api_call_count.get('finnhub', 0) + 1
            
            articles = []
            for item in data[:10]:
                articles.append({
                    'title': item.get('headline', ''),
                    'description': item.get('summary', ''),
                    'source': item.get('source', 'Finnhub'),
                    'url': item.get('url', ''),
                    'published': datetime.fromtimestamp(item.get('datetime', 0)).isoformat()
                })
            
            return articles
            
        except Exception as e:
            print(f"  Finnhub news error: {e}")
            return []

    def get_news_newsdata(self, hours=24):
        """Get news from NewsData.io"""
        try:
            url = "https://newsdata.io/api/1/news"
            
            params = {
                'apikey': NEWSDATA_IO_KEY,
                'q': self._build_news_query(max_length=90),  # NewsData.io limit is strict (approx 100)
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
                        'published': article.get('pubDate', ''),
                        'relevance_score': self._calculate_relevance(
                            article['title'], 
                            article.get('description', '')
                        )
                    })
                
                return articles
            return []
            
        except Exception as e:
            print(f"Error fetching from NewsData.io: {e}")
            return []
    
    def get_rss_feeds(self):
        """Get news from RSS feeds (no API limits!)"""
        feeds = {
            'Investing.com Gold': 'https://www.investing.com/rss/news_285.rss',
            'FXStreet Gold': 'https://www.fxstreet.com/rss/gold',
            'Kitco News': 'https://www.kitco.com/rss/KitcoNews.xml',
            'Gold.org': 'https://www.gold.org/feed',
            'Reuters Metals': 'https://www.reuters.com/rssfeed/metalsNews',
            'MarketWatch Gold': 'https://feeds.content.dowjones.io/public/rss/mw_topstories',
        }
        
        articles = []
        for source_name,feed_url in feeds.items():
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    articles.append({
                        'title': entry.title,
                        'description': entry.get('summary', entry.get('description', '')),
                        'source': feed.feed.get('title', 'RSS Feed'),
                        'url': entry.link,
                        'published': entry.get('published', ''),
                    })
                print(f"  ✓ {source_name}: {len(feed.entries[:3])} articles")
            except Exception as e:
                print(f"✗ {source_name} failed: {str(e)[:50]}")
        
        return articles
    
    def get_all_news(self):
        """Aggregate news from all sources with relevance scoring"""
        print("Fetching news from multiple sources...")
        all_news = []
        
        # RSS feeds first (unlimited, most reliable)
        rss_news = self.get_rss_feeds()
        if rss_news:
            all_news.extend(rss_news)

        # Try NewsAPI (100/day limit)
        if self.api_call_count.get('news_api', 0) < 50:  # Use only half daily quota
            news = self.get_news_newsapi()
            if news:
                all_news.extend(news)
                print(f"  ✓ Got {len(news)} articles from NewsAPI")
        
        # Try Finnhub (60/day limit)
        if self.api_call_count.get('finnhub', 0) < 30:  # Use only half daily quota
            news = self.get_news_finnhub()
            if news:
                all_news.extend(news)
                print(f"  ✓ Got {len(news)} articles from Finnhub")
        
        # NewsData.io as backup (200/day limit)
        if len(all_news) < 15:
            news = self.get_news_newsdata()
            if news:
                all_news.extend(news)
                print(f"  ✓ Got {len(news)} articles from NewsData.io")

        # Try MarketAUX
        marketaux_news = self.get_news_marketaux()
        if marketaux_news:
            all_news.extend(marketaux_news)
            print(f"  ✓ Got {len(marketaux_news)} articles from MarketAUX")
        
        # Remove duplicates by title similarity
        unique_news = []
        seen_titles = set()
        
        for article in all_news:
            title_key = article['title'][:50].lower()  # First 50 chars
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                # Add relevance score if not already present
                article['relevance_score'] = self.calculate_relevance_score(article)
            unique_news.append(article)
        
        # Sort by relevance score (highest first)
        unique_news.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        print(f"Total unique articles: {len(unique_news)}")
        print(f"High relevance articles (score >= 5): {sum(1 for a in unique_news if a['relevance_score'] >= 5)}")
        
        return unique_news[:25]  # Return top 25 most relevant
    
    def get_market_data(self):
        """Get complete enhanced market snapshot"""
        print("\n" + "="*60)
        print("COLLECTING MARKET DATA")
        print("="*60)
        
        # Get current price from multiple sources
        current_price = self.get_current_price()
        
        # Get price history and calculate indicators
        price_history = self.get_price_history()
        technical_indicators = self.calculate_technical_indicators(price_history)
        
        # Get news with relevance scoring
        news = self.get_all_news()
        
        # Get economic calendar
        # economic_events = self.get_economic_calendar()
        economic_events = []
        print("="*60 + "\n")
        
        return {
            'current_price': current_price,
            'technical_indicators': technical_indicators,
            'price_history': price_history,
            'news': news,
            'high_relevance_news': [n for n in news if n.get('relevance_score', 0) >= 5],
            'economic_calendar': economic_events,
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
    
    print("🚀 Testing Enhanced Data Collector...")
    
    data = collector.get_market_data()
    
    if data['current_price']:
        print(f"\n💰 CURRENT PRICE: ${data['current_price']['price']:.2f}")
        if 'change_percent' in data['current_price']:
            print(f"   24h Change: {data['current_price']['change_percent']:.2f}%")
    
    if data['technical_indicators']:
        print(f"\n📊 TECHNICAL INDICATORS:")
        ti = data['technical_indicators']
        print(f"   SMA 20: ${ti['sma_20']:.2f}")
        print(f"   24h Change: {ti['change_24h']:.2f}%")
        print(f"   Trend: {ti['recent_trend']}")
        print(f"   Volatility: {ti['volatility']:.2f}")
    
    print(f"\n📰 NEWS SUMMARY:")
    print(f"   Total articles: {len(data['news'])}")
    print(f"   High relevance: {len(data['high_relevance_news'])}")
    
    if data['high_relevance_news']:
        print(f"\n🔥 TOP 3 MOST RELEVANT:")
        for i, article in enumerate(data['high_relevance_news'][:3], 1):
            print(f"   {i}. [{article['relevance_score']}] {article['title'][:70]}...")
    
    if data['economic_calendar']:
        print(f"\n📅 UPCOMING EVENTS:")
        for event in data['economic_calendar'][:3]:
            print(f"   • {event['date']}: {event['event']} ({event['impact']})")
    
    collector.print_api_usage()
    
    print("\n✅ Enhanced data collection complete!")

    # Add to the bottom of data_collector.py, in the if __name__ == "__main__": section

# def test_fmp_api():
#     """Test FMP API specifically"""
#     print("\n🔍 Testing FMP API...")
#     print(f"API Key: {FMP_API_KEY[:10]}..." if FMP_API_KEY else "NO API KEY!")
    
#     # Test 1: Simple quote
#     url = "https://financialmodelingprep.com/api/v3/quote/AAPL"
#     params = {'apikey': FMP_API_KEY}
#     response = requests.get(url, params=params)
#     print(f"Test 1 - AAPL Quote: Status {response.status_code}")
#     if response.status_code == 200:
#         print(f"  Data: {response.json()[:1] if response.json() else 'Empty'}")
    
#     # Test 2: Gold/XAUUSD
#     url = "https://financialmodelingprep.com/api/v3/quote/XAUUSD"
#     response = requests.get(url, params=params)
#     print(f"Test 2 - XAUUSD: Status {response.status_code}")
#     print(f"  Response: {response.text[:200]}")
    
#     # Test 3: Alternative gold symbols
#     for symbol in ['GC=F', 'GOLD', 'GLD']:
#         url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}"
#         response = requests.get(url, params=params)
#         if response.status_code == 200 and response.json():
#             print(f"  ✓ {symbol} works!")

# # Run it
# test_fmp_api()
import krakenex
import requests
import time
from decimal import Decimal

class KrakenBot:
    def __init__(self):
        self.kraken = krakenex.API()
        self.kraken.load_key('kraken.key')
        self.gnews_api_key = 'test-key'  # replace with your actual GNews API key
        self.check_interval = 300  # check every 5 minutes
        self.top_coins = []
        self.base_currency = 'EUR'  # or 'USD', depending on your preference
        self.asset_pairs = {}

    def get_asset_pairs(self):
        try:
            assets = self.kraken.query_public('AssetPairs')['result']
            self.asset_pairs = {
                pair: {
                    'altname': info['altname'],
                    'min_order': Decimal(info['ordermin']),
                    'decimal_places': info['pair_decimals']
                }
                for pair, info in assets.items()
                if info['quote'] == f'Z{self.base_currency}'
            }
        except Exception as e:
            print(f"Error fetching asset pairs: {str(e)}")

    def get_top_coins(self, limit=10):
        try:
            ticker = self.kraken.query_public('Ticker')['result']
            volumes = [(pair, Decimal(info['v'][1])) for pair, info in ticker.items() if pair in self.asset_pairs]
            volumes.sort(key=lambda x: x[1], reverse=True)
            return [pair for pair, _ in volumes[:limit]]
        except Exception as e:
            print(f"Error fetching top coins: {str(e)}")
            return []

    def get_news_sentiment(self, asset):
        try:
            url = f"https://gnews.io/api/v4/search?q={asset}&token={self.gnews_api_key}&lang=en"
            response = requests.get(url)
            news_data = response.json()
            
            if 'articles' not in news_data:
                print(f"Error fetching news for {asset}: {news_data.get('errors', ['Unknown error'])}")
                return 0
            
            positive_words = ['bullish', 'surge', 'rise', 'gain', 'positive', 'up']
            negative_words = ['bearish', 'plunge', 'fall', 'loss', 'negative', 'down']
            
            sentiment = 0
            for article in news_data['articles'][:5]:
                title = article['title'].lower()
                description = article['description'].lower()
                content = f"{title} {description}"
                sentiment += sum(content.count(word) for word in positive_words)
                sentiment -= sum(content.count(word) for word in negative_words)
            
            print(f"Current sentiment for {asset}: {sentiment}")
            return sentiment
        except Exception as e:
            print(f"Error fetching news sentiment for {asset}: {str(e)}")
            return 0

    def place_market_order(self, pair, type, volume):
        try:
            volume = round(volume, self.asset_pairs[pair]['decimal_places'])
            response = self.kraken.query_private('AddOrder', {
                'pair': pair,
                'type': type,
                'ordertype': 'market',
                'volume': str(volume)
            })
            print(f"Order response: {response}")
            if 'error' in response and response['error']:
                print(f"Error placing order: {response['error']}")
            elif 'result' in response and 'txid' in response['result']:
                print(f"Order placed successfully. Transaction ID: {response['result']['txid']}")
            else:
                print("Unexpected response format")
        except Exception as e:
            print(f"Exception occurred while placing order: {str(e)}")

    def get_balance(self):
        try:
            return self.kraken.query_private('Balance')['result']
        except Exception as e:
            print(f"Error fetching balance: {str(e)}")
            return {}

    def trading_strategy(self):
        self.get_asset_pairs()
        self.top_coins = self.get_top_coins()
        balance = self.get_balance()
        
        for pair in self.top_coins:
            asset = pair[:-4]  # remove the 'EUR' or 'USD' suffix
            sentiment = self.get_news_sentiment(asset)
            
            if sentiment > 1:  # positive sentiment
                if asset in balance and Decimal(balance[asset]) > 0:
                    print(f"Already holding {asset}. No action taken.")
                else:
                    print(f"Positive sentiment detected for {asset}. Attempting to buy.")
                    base_balance = Decimal(balance.get(f'Z{self.base_currency}', '0'))
                    min_order = self.asset_pairs[pair]['min_order']
                    buy_volume = max(base_balance * Decimal('0.1'), min_order)
                    if buy_volume >= min_order:
                        self.place_market_order(pair, 'buy', buy_volume)
                    else:
                        print(f"Insufficient funds to meet minimum order size for {asset}")
            elif sentiment < -1:  # negative sentiment
                if asset in balance and Decimal(balance[asset]) > 0:
                    print(f"Negative sentiment detected for {asset}. Attempting to sell.")
                    sell_volume = Decimal(balance[asset])
                    min_order = self.asset_pairs[pair]['min_order']
                    if sell_volume >= min_order:
                        self.place_market_order(pair, 'sell', sell_volume)
                    else:
                        print(f"Balance too low to meet minimum order size for selling {asset}")
                else:
                    print(f"No {asset} balance to sell.")
            else:
                print(f"Neutral sentiment for {asset}. No trade executed.")
            
            time.sleep(10)  # small delay between API calls to avoid rate limiting

    def run(self):
        print("Starting Kraken trading bot with dynamic coin selection...")
        while True:
            try:
                self.trading_strategy()
                time.sleep(self.check_interval)
            except Exception as e:
                print(f"Error in trading strategy: {str(e)}")
                time.sleep(60)

if __name__ == "__main__":
    bot = KrakenBot()
    bot.run()
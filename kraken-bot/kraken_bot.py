import krakenex
import requests
import time
import os
from decimal import Decimal
import pandas as pd
import numpy as np
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KrakenBot:
    def __init__(self):
        """Initialize the KrakenBot with necessary configurations and API connections."""
        self.kraken = krakenex.API()
        self.kraken.load_key('kraken.key')
        self.gnews_api_key = os.getenv('GNEWS_API_KEY')
        self.check_interval = 300  # check every 5 minutes
        self.base_currency = 'USD'
        self.asset_pairs = {}
        self.max_risk_per_trade = Decimal('0.02')  # 2% of account balance
        self.sentiment_threshold = Decimal('0.2')  # Sentiment threshold for trading decisions
        self.volatility_threshold = Decimal('0.02')  # 2% volatility threshold
        self.moving_average_periods = [20, 50]  # For simple moving average crossover strategy
        self.rebalance_threshold = Decimal('0.1')  # 10% threshold for rebalancing
        self.min_trade_size = Decimal('5')  # Minimum trade size in base currency
        self.is_trading = False
        nltk.download('vader_lexicon', quiet=True)
        self.sia = SentimentIntensityAnalyzer()

    @sleep_and_retry
    @limits(calls=15, period=60)  # Limit to 15 calls per 60 seconds
    def _make_kraken_api_call(self, method, endpoint, payload=None):
        """Make a rate-limited API call to Kraken."""
        if method == 'public':
            return self.kraken.query_public(endpoint, payload)
        elif method == 'private':
            return self.kraken.query_private(endpoint, payload)
        else:
            raise ValueError("Invalid method. Use 'public' or 'private'.")

    def get_asset_pairs(self):
        """Fetch and store valid asset pairs from Kraken."""
        try:
            assets = self._make_kraken_api_call('public', 'AssetPairs')['result']
            self.asset_pairs = {}
            for pair, info in assets.items():
                if info['quote'] == self.base_currency or info['quote'] == f'Z{self.base_currency}':
                    try:
                        min_order = Decimal(info['ordermin'])
                        self.asset_pairs[pair] = {
                            'altname': info['altname'],
                            'min_order': min_order,
                            'decimal_places': info['pair_decimals']
                        }
                    except KeyError:
                        logger.warning(f"Skipping pair {pair} due to missing 'ordermin' information")
            logger.info(f"Valid asset pairs: {list(self.asset_pairs.keys())}")
        except Exception as e:
            logger.error(f"Error fetching asset pairs: {str(e)}")

    def get_balance(self):
        """Fetch account balance from Kraken."""
        try:
            return {k: Decimal(v) for k, v in self._make_kraken_api_call('private', 'Balance')['result'].items()}
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            return {}

    def get_ticker_info(self, pair):
        """Fetch ticker information for a specific asset pair."""
        try:
            ticker = self._make_kraken_api_call('public', 'Ticker', {'pair': pair})['result'][pair]
            return {
                'last': Decimal(ticker['c'][0]),
                'bid': Decimal(ticker['b'][0]),
                'ask': Decimal(ticker['a'][0]),
            }
        except KeyError:
            logger.error(f"Error fetching ticker info for {pair}: KeyError")
            return None
        except Exception as e:
            logger.error(f"Error fetching ticker info for {pair}: {str(e)}")
            return None

    def get_portfolio_value(self):
        """Calculate the total portfolio value in the base currency."""
        balance = self.get_balance()
        total_value = Decimal('0')
        for asset, amount in balance.items():
            if asset == self.base_currency or asset == f'Z{self.base_currency}':
                total_value += amount
            else:
                for pair in self.asset_pairs:
                    if pair.startswith(asset) or pair.startswith(f'X{asset}'):
                        ticker_info = self.get_ticker_info(pair)
                        if ticker_info:
                            total_value += amount * ticker_info['last']
                            break
        logger.info(f"Total portfolio value: {total_value:.4f} {self.base_currency}")
        return total_value

    @sleep_and_retry
    @limits(calls=5, period=60)  # Limit to 5 calls per 60 seconds
    def get_news_sentiment(self, asset):
        """Fetch and analyze news sentiment for a specific asset."""
        try:
            url = f"https://gnews.io/api/v4/search?q={asset}&token={self.gnews_api_key}&lang=en"
            response = requests.get(url)
            news_data = response.json()
            
            if 'articles' not in news_data:
                logger.error(f"Error fetching news for {asset}: {news_data.get('errors', ['Unknown error'])}")
                return Decimal('0')
            
            sentiments = []
            for article in news_data['articles'][:10]:
                title = article['title']
                description = article['description']
                content = f"{title} {description}"
                sentiment = self.sia.polarity_scores(content)['compound']
                sentiments.append(sentiment)
            
            avg_sentiment = Decimal(sum(sentiments) / len(sentiments)) if sentiments else Decimal('0')
            logger.info(f"Current sentiment for {asset}: {avg_sentiment:.4f}")
            return avg_sentiment
        except Exception as e:
            logger.error(f"Error fetching news sentiment for {asset}: {str(e)}")
            return Decimal('0')
        
    def get_recent_trades(self, limit=10):
        """Fetch recent trades from the account."""
        try:
            trades = self._make_kraken_api_call('private', 'TradesHistory')['result']['trades']
            recent_trades = []
            for trade_id, trade_info in list(trades.items())[:limit]:
                recent_trades.append({
                    'time': trade_info['time'],
                    'pair': trade_info['pair'],
                    'type': trade_info['type'],
                    'price': trade_info['price'],
                    'amount': trade_info['vol'],
                    'cost': trade_info['cost']
                })
            return recent_trades
        except Exception as e:
            logger.error(f"Error fetching recent trades: {str(e)}")
            return []

    def place_order(self, pair, type, volume):
        """Place a market order on Kraken."""
        try:
            volume = round(volume, self.asset_pairs[pair]['decimal_places'])
            min_order = self.asset_pairs[pair]['min_order']
            if volume < min_order:
                logger.warning(f"Order volume {volume} is below minimum {min_order} for {pair}")
                return
            
            order_params = {
                'pair': pair,
                'type': type,
                'ordertype': 'market',
                'volume': str(volume)
            }
            
            response = self._make_kraken_api_call('private', 'AddOrder', order_params)
            logger.info(f"Order response: {response}")
            if 'error' in response and response['error']:
                logger.error(f"Error placing order: {response['error']}")
            elif 'result' in response and 'txid' in response['result']:
                logger.info(f"Order placed successfully. Transaction ID: {response['result']['txid']}")
            else:
                logger.warning("Unexpected response format")
        except Exception as e:
            logger.error(f"Exception occurred while placing order: {str(e)}")

    def rebalance_portfolio(self):
        """Rebalance the portfolio based on predefined thresholds."""
        portfolio_value = self.get_portfolio_value()
        balance = self.get_balance()
        base_balance = Decimal(balance.get(self.base_currency, '0'))
        target_allocation = Decimal('0.1')  # 10% of portfolio for each asset

        for pair, info in self.asset_pairs.items():
            asset = pair.split(self.base_currency)[0]
            if asset not in balance:
                continue

            ticker_info = self.get_ticker_info(pair)
            if not ticker_info:
                continue

            current_price = ticker_info['last']
            current_value = Decimal(balance[asset]) * current_price
            target_value = portfolio_value * target_allocation

            if current_value > target_value * (1 + self.rebalance_threshold):
                # Sell excess
                sell_amount = (current_value - target_value) / current_price
                if sell_amount * current_price >= self.min_trade_size:
                    self.place_order(pair, 'sell', sell_amount)
            elif current_value < target_value * (1 - self.rebalance_threshold) and base_balance > self.min_trade_size:
                # Buy more
                buy_amount = min((target_value - current_value) / current_price, base_balance / current_price)
                if buy_amount * current_price >= self.min_trade_size:
                    self.place_order(pair, 'buy', buy_amount)

    def get_historical_data(self, pair, interval=1440, since=None):
        """Fetch historical OHLC data for a specific pair."""
        try:
            payload = {'pair': pair, 'interval': interval}
            if since:
                payload['since'] = since
            ohlc_data = self._make_kraken_api_call('public', 'OHLC', payload)['result'][pair]
            df = pd.DataFrame(ohlc_data, columns=['time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            df = df.astype(float)
            return df
        except Exception as e:
            logger.error(f"Error fetching historical data for {pair}: {str(e)}")
            return None

    def calculate_indicators(self, df):
        """Calculate technical indicators for trading decisions."""
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['RSI'] = self.calculate_rsi(df['close'])
        df['MACD'], df['Signal'], df['Hist'] = self.calculate_macd(df['close'])
        return df

    def calculate_rsi(self, prices, period=14):
        """Calculate the Relative Strength Index."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """Calculate the Moving Average Convergence Divergence."""
        exp1 = prices.ewm(span=fast, adjust=False).mean()
        exp2 = prices.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram
    
    def get_current_signals(self):
        """Get current trading signals for all asset pairs."""
        signals = {}
        self.get_asset_pairs()
        balance = self.get_balance()
        
        for asset, amount in balance.items():
            if asset == self.base_currency or asset == f'Z{self.base_currency}':
                continue

            pair = f"{asset}{self.base_currency}"
            if pair not in self.asset_pairs:
                continue

            try:
                sentiment = self.get_news_sentiment(asset)
                df = self.get_historical_data(pair)
                if df is None or df.empty:
                    continue

                df = self.calculate_indicators(df)
                
                # Convert numpy.bool_ to Python bool
                sma_signal = bool(df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1])
                rsi = df['RSI'].iloc[-1]
                macd_signal = bool(df['MACD'].iloc[-1] > df['Signal'].iloc[-1])

                signals[asset] = {
                    'sma_signal': sma_signal,
                    'rsi_signal': 'Oversold' if rsi < 30 else 'Overbought' if rsi > 70 else 'Neutral',
                    'macd_signal': macd_signal,
                    'sentiment': float(sentiment)
                }
            
            except Exception as e:
                logger.error(f"Error getting signals for {asset}: {str(e)}")
        
        return signals

    def trading_strategy(self):
        """Implement the trading strategy based on technical indicators and sentiment analysis."""
        self.get_asset_pairs()
        balance = self.get_balance()
        
        for asset, amount in balance.items():
            if asset == self.base_currency or asset == f'Z{self.base_currency}':
                continue

            pair = f"{asset}{self.base_currency}"
            if pair not in self.asset_pairs:
                logger.debug(f"Asset pair {pair} not in asset pairs.")
                continue

            try:
                sentiment = self.get_news_sentiment(asset)
                df = self.get_historical_data(pair)
                if df is None or df.empty:
                    logger.debug(f"No historical data for {pair}.")
                    continue

                df = self.calculate_indicators(df)
                current_price = Decimal(str(df['close'].iloc[-1]))
                current_value = Decimal(amount) * current_price

                # Use the risk tolerance parameter
                risk_amount = current_value * self.max_risk_per_trade

                # Technical analysis signals
                sma_signal = bool(df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1])
                rsi_value = df['RSI'].iloc[-1]
                macd_signal = bool(df['MACD'].iloc[-1] > df['Signal'].iloc[-1])

                # Combine technical and sentiment signals
                buy_signal = (sma_signal and macd_signal and rsi_value < 50) or sentiment > self.sentiment_threshold
                sell_signal = (not sma_signal and not macd_signal and rsi_value > 50) or sentiment < -self.sentiment_threshold

                logger.debug(f"Signals for {asset}: Buy={buy_signal}, Sell={sell_signal}, Price={current_price}")

                if buy_signal:
                    base_balance = Decimal(balance.get(self.base_currency, '0'))
                    buy_volume = (risk_amount / current_price).quantize(Decimal('1e-8'))
                    if buy_volume * current_price >= self.min_trade_size and base_balance >= buy_volume * current_price:
                        self.place_order(pair, 'buy', buy_volume)
                        logger.info(f"Placed buy order for {buy_volume} {asset}")
                    else:
                        logger.debug(f"Not enough balance to buy {asset} or trade size too small.")
                elif sell_signal:
                    sell_volume = min((risk_amount / current_price).quantize(Decimal('1e-8')), Decimal(amount))
                    if sell_volume * current_price >= self.min_trade_size:
                        self.place_order(pair, 'sell', sell_volume)
                        logger.info(f"Placed sell order for {sell_volume} {asset}")
                    else:
                        logger.debug(f"Not enough {asset} to sell or trade size too small.")
                else:
                    logger.debug(f"No trade action for {asset}.")
            
            except Exception as e:
                logger.error(f"Error processing {asset}: {str(e)}")
            
            time.sleep(1)

    def start_trading(self):
        """Start the trading bot."""
        self.is_trading = True
        logger.info("Trading bot started")

    def stop_trading(self):
        """Stop the trading bot."""
        self.is_trading = False
        logger.info("Trading bot stopped")

    def run(self):
        """Main loop to run the trading bot."""
        logger.info("Starting improved Kraken trading bot with portfolio management...")
        while True:
            try:
                if self.is_trading:
                    self.rebalance_portfolio()
                    self.trading_strategy()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in trading strategy: {str(e)}")
                time.sleep(60)

if __name__ == "__main__":
    bot = KrakenBot()
    bot.run()
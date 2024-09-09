# Kraken Trading Bot

A simple Python-based trading bot for automated cryptocurrency trading on the Kraken exchange. This bot is a work in progress and is intended for educational and experimental purposes.

## What This Bot Does

This Kraken Trading Bot offers a basic framework for automated cryptocurrency trading:

1. **News-Based Trading**: The bot uses a simple sentiment analysis of recent news to make buy or sell decisions.

2. **Multiple Coin Monitoring**: It can monitor multiple cryptocurrencies available on Kraken, not just those in your current balance.

3. **Automatic Trading**: Once started, the bot runs continuously, checking for trading opportunities at regular intervals.

4. **Basic Volume-Based Selection**: The bot focuses on the top traded coins on Kraken based on volume.

## Important Note

This bot is in its early stages and should be considered a starting point for more advanced trading strategies. It lacks sophisticated risk management features and may not be suitable for real trading without significant improvements.

## How to Use

### Prerequisites

- Python 3.6 or higher
- Kraken account with API key and secret
- GNews API key (for news sentiment analysis)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/your-username/kraken-trading-bot.git
   cd kraken-trading-bot
   ```

2. Install required packages:
   ```
   pip install krakenex requests
   ```

3. Set up your Kraken API key:
   - Create a file named `kraken.key` in the project directory
   - On the first line, put your Kraken API key
   - On the second line, put your Kraken private key

4. Update the `gnews_api_key` in the `KrakenBot` class with your actual GNews API key.

### Running the Bot

To start the bot, run the following command from the project directory:

```
python kraken_bot.py
```

The bot will start running, checking for trading opportunities based on news sentiment for various cryptocurrencies.

## Customization

You can adjust some basic parameters in the `KrakenBot` class:

- `check_interval`: Time between trading checks (default: 300 seconds)
- `base_currency`: Base currency for trading pairs (default: 'EUR')
- `get_top_coins`: Number of top coins to consider (default: 10)

## Disclaimer and Warnings

- This bot is for educational and experimental purposes only. It is not ready for real trading without significant improvements and thorough testing.
- The bot's trading strategy is very basic and does not include proper risk management.
- Always start with small amounts and monitor the bot's actions closely if you decide to use it with real funds.
- Cryptocurrency trading involves significant risk. This bot is not financial advice. Always do your own research and invest responsibly.

## Future Development

This bot is a work in progress. Future improvements may include:

- More sophisticated trading strategies
- Improved risk management features
- Better error handling and logging
- Integration with additional news sources and technical indicators

Contributions and suggestions for improvement are welcome!

## License

This project is open-source and available under the Apache License. See the LICENSE file for more details.
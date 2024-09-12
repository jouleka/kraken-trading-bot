# Kraken Trading Bot

A Python-based trading bot for automated cryptocurrency trading on the Kraken exchange, featuring a web-based dashboard for real-time monitoring and control. This bot is intended for educational and experimental purposes.

## Features

1. **Web Dashboard**: Monitor your portfolio, recent trades, trading signals, and activity logs.

2. **Automated Trading Strategy**: Combines technical indicators (SMA, RSI, MACD) with news sentiment analysis to make buy/sell decisions.

3. **Portfolio Management**: Automatically rebalances your portfolio based on predefined thresholds.

4. **Customizable Settings**: Adjust trading parameters through the web interface.

## Important Note

This bot is experimental and not suitable for real trading without significant improvements and thorough testing. Use at your own risk.

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
   pip install -r requirements.txt
   ```

3. Set up your Kraken API key:
   - Create a file named `kraken.key` in the project directory
   - On the first line, put your Kraken API key
   - On the second line, put your Kraken private key

### Set Up GNews API Key

Create a file named `.env` in the project directory with your `GNews API key`:
   ```
   GNEWS_API_KEY=your_gnews_api_key
   ```

### NLTK Data

The bot uses NLTK’s VADER lexicon for sentiment analysis. The necessary data will be automatically downloaded when the bot runs.

### Running the Bot

1. Start the Flask application:
   ```
   python app.py
   ```

2. Access the web dashboard at `http://127.0.0.1:5000`.

### Starting and Stopping the Bot

- **Start Trading**: Click “Start Trading” on the dashboard to start the bot.
- **Stop Trading**: Click “Stop Trading” to stop the bot.

### Adjusting Settings

Navigate to the “Settings” section in the dashboard to adjust trading parameters such as:

- Check Interval
- Max Risk per Trade
- Sentiment Threshold
- Rebalance Threshold
- Volatility Threshold
- Minimum Trade Size

### Additional Notes

- **Logging**: Activity logs are saved to `kraken_trader.log`.
- **API Rate Limits**: Be mindful of Kraken’s API rate limits to avoid being throttled.
- **Account Balance**: Ensure your Kraken account has sufficient funds for trading.

## Disclaimer

- **Educational Purposes Only**: This bot is for educational purposes and should not be used for live trading without proper testing.
- **No Financial Advice**: This bot does not constitute financial advice.
- **Risk of Loss**: Cryptocurrency trading involves significant risk. Use caution.

## License

This project is open-source and available under the Apache License. See the LICENSE file for more details.

Note: Always ensure you comply with local laws and regulations related to cryptocurrency trading and the use of automated trading systems.

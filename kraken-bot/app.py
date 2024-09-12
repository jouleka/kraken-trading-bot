from flask import Flask, render_template, request, jsonify
from kraken_bot import KrakenBot
import threading
import time
import sass
import os
from datetime import datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('kraken_trader.log', maxBytes=10000, backupCount=3)
logger.addHandler(handler)

# Global variables to store bot state and logs
bot = None
bot_thread = None
bot_running = False
portfolio_history = []
bot_start_time = None

def run_bot():
    global bot_running, portfolio_history
    while bot_running:
        try:
            bot.rebalance_portfolio()
            bot.trading_strategy()
            
            # Update portfolio history
            portfolio_value = bot.get_portfolio_value()
            portfolio_history.append({
                'timestamp': datetime.now().isoformat(),
                'value': float(portfolio_value)
            })
            
            # Keep only the last 24 hours of data
            cutoff_time = datetime.now() - timedelta(hours=24)
            portfolio_history = [ph for ph in portfolio_history if datetime.fromisoformat(ph['timestamp']) > cutoff_time]
            
            time.sleep(bot.check_interval)
        except Exception as e:
            logger.error(f"Error in trading strategy: {str(e)}")
            time.sleep(60)

@app.route('/')
def index():
    return render_template('index.html', bot_running=bot_running)

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot, bot_thread, bot_running, bot_start_time
    logger.debug("Start bot route called")
    try:
        if not bot_running:
            logger.info("Starting bot")
            bot = KrakenBot()
            bot.start_trading()
            bot_running = True
            bot_start_time = datetime.now().isoformat()
            bot_thread = threading.Thread(target=run_bot)
            bot_thread.start()
            logger.info("Bot started successfully")
            return jsonify({"status": "success", "message": "Bot started successfully"})
        else:
            logger.info("Bot is already running")
            return jsonify({"status": "warning", "message": "Bot is already running"})
    except Exception as e:
        error_message = f"Error starting bot: {str(e)}"
        logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_running, bot_start_time
    logger.debug("Stop bot route called")
    try:
        if bot_running:
            bot.stop_trading()
            bot_running = False
            bot_start_time = None
            logger.info("Bot stopped successfully")
            return jsonify({"status": "success", "message": "Bot stopped successfully"})
        else:
            logger.info("Bot is not running")
            return jsonify({"status": "warning", "message": "Bot is not running"})
    except Exception as e:
        error_message = f"Error stopping bot: {str(e)}"
        logger.error(error_message)
        return jsonify({"status": "error", "message": error_message}), 500

@app.route('/get_logs')
def get_logs():
    try:
        with open('kraken_trader.log', 'r') as log_file:
            logs = log_file.readlines()[-100:]  # Get last 100 lines
        return jsonify({"logs": logs})
    except Exception as e:
        error_message = f"Error reading logs: {str(e)}"
        logger.error(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/get_portfolio')
def get_portfolio():
    logger.debug("Get portfolio route called")
    try:
        if bot and bot_running:
            portfolio = bot.get_balance()
            portfolio_value = bot.get_portfolio_value()
            return jsonify({
                "portfolio": {k: float(v) for k, v in portfolio.items()},
                "total_value": float(portfolio_value),
                "history": portfolio_history,
                "start_time": bot_start_time
            })
        else:
            logger.info("Bot is not running, cannot retrieve portfolio")
            return jsonify({"error": "Bot is not running"}), 400
    except Exception as e:
        error_message = f"Error getting portfolio: {str(e)}"
        logger.error(error_message)
        return jsonify({"error": error_message}), 500

@app.route('/get_trades')
def get_trades():
    if bot and bot_running:
        try:
            trades = bot.get_recent_trades()
            return jsonify({"trades": trades})
        except Exception as e:
            error_message = f"Error getting trades: {str(e)}"
            logger.error(error_message)
            return jsonify({"error": error_message}), 500
    return jsonify({"error": "Bot is not running"}), 400

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if bot and bot_running:
        try:
            data = request.json
            bot.check_interval = int(data['checkInterval'])
            bot.max_risk_per_trade = float(data['maxRiskPerTrade']) / 100
            bot.sentiment_threshold = float(data['sentimentThreshold'])
            bot.rebalance_threshold = float(data['rebalanceThreshold']) / 100
            bot.volatility_threshold = float(data['volatilityThreshold']) / 100
            bot.min_trade_size = float(data['minTradeSize'])
            logger.info("Settings updated successfully")
            return jsonify({"status": "success", "message": "Settings updated successfully"})
        except Exception as e:
            error_message = f"Error updating settings: {str(e)}"
            logger.error(error_message)
            return jsonify({"status": "error", "message": error_message}), 500
    return jsonify({"status": "error", "message": "Bot is not running"}), 400

@app.route('/get_bot_status')
def get_bot_status():
    status = "running" if bot_running else "stopped"
    uptime = None
    if bot_running and bot_start_time:
        uptime = (datetime.now() - datetime.fromisoformat(bot_start_time)).total_seconds()
    return jsonify({
        "status": status,
        "start_time": bot_start_time,
        "uptime": uptime,
        "current_settings": get_current_settings() if bot and bot_running else None
    })

@app.route('/get_trading_signals')
def get_trading_signals():
    if bot and bot_running:
        try:
            signals = bot.get_current_signals()
            return jsonify(signals)
        except Exception as e:
            error_message = f"Error getting trading signals: {str(e)}"
            logger.error(error_message)
            return jsonify({"status": "error", "message": error_message}), 500
    return jsonify({"status": "error", "message": "Bot is not running"}), 400

def get_current_settings():
    return {
        "check_interval": bot.check_interval,
        "max_risk_per_trade": bot.max_risk_per_trade,
        "sentiment_threshold": bot.sentiment_threshold,
        "rebalance_threshold": bot.rebalance_threshold,
        "volatility_threshold": bot.volatility_threshold,
        "min_trade_size": bot.min_trade_size
    }

def compile_scss():
    scss_path = os.path.join(app.static_folder, 'scss', 'main.scss')
    css_path = os.path.join(app.static_folder, 'css', 'main.css')
    
    if not os.path.exists(os.path.dirname(css_path)):
        os.makedirs(os.path.dirname(css_path))
    
    with open(scss_path, 'r') as scss_file:
        scss_content = scss_file.read()
    
    compiled_css = sass.compile(string=scss_content)
    
    with open(css_path, 'w') as css_file:
        css_file.write(compiled_css)

if __name__ == '__main__':
    compile_scss()
    app.run(debug=True)
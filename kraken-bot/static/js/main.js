document.addEventListener('DOMContentLoaded', function() {
    console.log('Kraken Trader initialized');

    const ctx = document.getElementById('portfolioChart').getContext('2d');
    const portfolioChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Portfolio Value',
                data: [],
                borderColor: '#3a4f41',
                backgroundColor: 'rgba(58, 79, 65, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour',
                        displayFormats: {
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        color: '#2c3e50'
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    },
                    ticks: {
                        color: '#2c3e50'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            },
            animation: {
                duration: 2000,
                easing: 'easeOutQuart'
            }
        }
    });

    const toggleButton = document.getElementById('toggleBot');
    console.log('Trader control:', toggleButton);

    if (toggleButton) {
        toggleButton.addEventListener('click', function(event) {
            console.log('Trader toggle initiated');
            event.preventDefault();
            const action = this.textContent.trim().toLowerCase().includes('start') ? 'start_bot' : 'stop_bot';
            console.log('Trader action:', action);

            fetch(`/${action}`, { 
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            })
            .then(response => {
                console.log('Trader response received:', response);
                return response.json();
            })
            .then(data => {
                console.log('Trader data received:', data);
                updateTraderStatus(data.status);
                showToast(data.message, data.status);
            })
            .catch(error => {
                console.error('Trader error:', error);
                updateTraderStatus('Error: Check console');
                showToast('An error occurred. Please check the console for details.', 'error');
            });
        });
    } else {
        console.error('Trader control not found in the interface');
    }

    function updateTraderStatus(status) {
        const statusElement = document.getElementById('botStatus');
        const toggleButton = document.getElementById('toggleBot');
        
        if (status === 'running' || status === 'success') {
            statusElement.textContent = 'Online';
            statusElement.className = 'status-indicator online';
            toggleButton.textContent = 'Stop Trading';
            toggleButton.classList.remove('btn-primary');
            toggleButton.classList.add('btn-danger');
        } else {
            statusElement.textContent = 'Offline';
            statusElement.className = 'status-indicator offline';
            toggleButton.textContent = 'Start Trading';
            toggleButton.classList.remove('btn-danger');
            toggleButton.classList.add('btn-primary');
        }
    }

    function showToast(message, status) {
        const toast = document.createElement('div');
        toast.className = `toast ${status}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(toast);
                }, 300);
            }, 3000);
        }, 100);
    }

    function updateDashboard() {
        console.log('Updating Trader dashboard');
        fetch('/get_portfolio')
            .then(response => response.json())
            .then(data => {
                console.log('Trader data received:', data);
                updateSummaryCards(data);
                updateAssetGrid(data.portfolio);
                updatePortfolioChart(data.history);
            })
            .catch(error => {
                console.error('Error updating Trader dashboard:', error);
                showToast('Failed to update dashboard. Please check the console for details.', 'error');
            });
    }

    function updateSummaryCards(data) {
        document.getElementById('totalValue').textContent = `$${data.total_value.toFixed(2)}`;
        document.getElementById('dailyChange').textContent = `${calculateDailyChange(data.history)}%`;
        document.getElementById('topAsset').textContent = getTopAsset(data.portfolio);
        document.getElementById('botUptime').textContent = calculateUptime(data.start_time);
    }

    function calculateDailyChange(history) {
        if (history.length < 2) return '0.00';
        const oldestValue = history[0].value;
        const newestValue = history[history.length - 1].value;
        return ((newestValue - oldestValue) / oldestValue * 100).toFixed(2);
    }

    function getTopAsset(portfolio) {
        return Object.entries(portfolio).reduce((a, b) => a[1] > b[1] ? a : b)[0];
    }

    function calculateUptime(startTime) {
        if (!startTime) return '0:00:00';
        const uptime = new Date() - new Date(startTime);
        const hours = Math.floor(uptime / 3600000);
        const minutes = Math.floor((uptime % 3600000) / 60000);
        const seconds = Math.floor((uptime % 60000) / 1000);
        return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    function updateAssetGrid(portfolio) {
        const assetGrid = document.getElementById('assetGrid');
        assetGrid.innerHTML = '';
        for (const [asset, amount] of Object.entries(portfolio)) {
            const assetCard = document.createElement('div');
            assetCard.className = 'asset-card';
            assetCard.innerHTML = `
                <h3>${asset}</h3>
                <p>${parseFloat(amount).toFixed(8)}</p>
            `;
            assetGrid.appendChild(assetCard);
        }
    }

    function updatePortfolioChart(history) {
        portfolioChart.data.labels = history.map(item => new Date(item.timestamp));
        portfolioChart.data.datasets[0].data = history.map(item => item.value);
        portfolioChart.update();
    }

    function updateTradeList() {
        fetch('/get_trades')
            .then(response => response.json())
            .then(data => {
                const tradeList = document.getElementById('tradeList');
                tradeList.innerHTML = '';
                data.trades.forEach(trade => {
                    const tradeItem = document.createElement('div');
                    tradeItem.className = 'trade-item';
                    tradeItem.innerHTML = `
                        <p>${new Date(trade.time).toLocaleString()} - ${trade.type} ${trade.amount} ${trade.pair} @ ${trade.price}</p>
                    `;
                    tradeList.appendChild(tradeItem);
                });
            })
            .catch(error => {
                console.error('Error updating trade list:', error);
                showToast('Failed to update trade list. Please check the console for details.', 'error');
            });
    }

    function updateLogs() {
        fetch('/get_logs')
            .then(response => response.json())
            .then(data => {
                document.getElementById('logData').textContent = data.logs.join('\n');
            })
            .catch(error => {
                console.error('Error updating logs:', error);
                showToast('Failed to update logs. Please check the console for details.', 'error');
            });
    }

    function updateTradingSignals() {
        fetch('/get_trading_signals')
            .then(response => response.json())
            .then(data => {
                const signalsContainer = document.getElementById('tradingSignals');
                signalsContainer.innerHTML = '';
                for (const [asset, signals] of Object.entries(data)) {
                    const signalCard = document.createElement('div');
                    signalCard.className = 'signal-card';
                    signalCard.innerHTML = `
                        <h3>${asset}</h3>
                        <p>SMA: ${signals.sma_signal ? 'Bullish' : 'Bearish'}</p>
                        <p>RSI: ${signals.rsi_signal}</p>
                        <p>MACD: ${signals.macd_signal ? 'Bullish' : 'Bearish'}</p>
                        <p>Sentiment: ${signals.sentiment.toFixed(2)}</p>
                    `;
                    signalsContainer.appendChild(signalCard);
                }
            })
            .catch(error => {
                console.error('Error updating trading signals:', error);
                showToast('Failed to update trading signals. Please check the console for details.', 'error');
            });
    }

    document.getElementById('settingsForm').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = {
            checkInterval: document.getElementById('checkInterval').value,
            maxRiskPerTrade: document.getElementById('maxRiskPerTrade').value,
            sentimentThreshold: document.getElementById('sentimentThreshold').value,
            rebalanceThreshold: document.getElementById('rebalanceThreshold').value,
            volatilityThreshold: document.getElementById('volatilityThreshold').value,
            minTradeSize: document.getElementById('minTradeSize').value
        };
        fetch('/update_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Trader settings updated:', data);
            showToast(data.message, data.status);
        })
        .catch(error => {
            console.error('Error updating Trader settings:', error);
            showToast('Error reconfiguring Trader. Please check the console for details.', 'error');
        });
    });

    // Navigation
    document.querySelectorAll('.main-nav a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = this.getAttribute('href').substring(1);
            document.querySelectorAll('.content-section').forEach(section => section.classList.remove('active'));
            document.getElementById(target).classList.add('active');
            document.querySelectorAll('.main-nav a').forEach(a => a.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Range input updates
    document.querySelectorAll('input[type="range"]').forEach(input => {
        input.addEventListener('input', function() {
            this.nextElementSibling.value = this.value + (this.id === 'maxRiskPerTrade' || this.id === 'rebalanceThreshold' || this.id === 'volatilityThreshold' ? '%' : '');
        });
    });

    // Get initial bot status and settings
    function getInitialBotStatus() {
        fetch('/get_bot_status')
            .then(response => response.json())
            .then(data => {
                updateTraderStatus(data.status);
                if (data.status === 'running') {
                    updateDashboard();
                    updateTradeList();
                    updateLogs();
                    updateTradingSignals();
                }
                if (data.current_settings) {
                    updateSettingsForm(data.current_settings);
                }
            })
            .catch(error => {
                console.error('Error getting initial bot status:', error);
                showToast('Failed to get initial bot status. Please check the console for details.', 'error');
            });
    }

    function updateSettingsForm(settings) {
        document.getElementById('checkInterval').value = settings.check_interval;
        document.getElementById('maxRiskPerTrade').value = settings.max_risk_per_trade * 100;
        document.getElementById('sentimentThreshold').value = settings.sentiment_threshold;
        document.getElementById('rebalanceThreshold').value = settings.rebalance_threshold * 100;
        document.getElementById('volatilityThreshold').value = settings.volatility_threshold * 100;
        document.getElementById('minTradeSize').value = settings.min_trade_size;
        
        // Update output displays
        document.querySelectorAll('input[type="range"]').forEach(input => {
            input.nextElementSibling.value = input.value + (input.id === 'maxRiskPerTrade' || input.id === 'rebalanceThreshold' || input.id === 'volatilityThreshold' ? '%' : '');
        });
    }

    // Initial setup and periodic updates
    getInitialBotStatus();
    setInterval(() => {
        fetch('/get_bot_status')
            .then(response => response.json())
            .then(data => {
                updateTraderStatus(data.status);
                if (data.status === 'running') {
                    updateDashboard();
                    updateTradeList();
                    updateLogs();
                    updateTradingSignals();
                }
            })
            .catch(error => {
                console.error('Error getting bot status:', error);
                showToast('Failed to update bot status. Please check the console for details.', 'error');
            });
    }, 10000);
});
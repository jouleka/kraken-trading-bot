"""Exercise real Flask handlers and bot calculations with synthetic offline data."""

import logging
import runpy
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import flask
import pytest

from conftest import SOURCE
from kraken_bot import KrakenBot


ERROR_MARKER = "synthetic-sensitive-error-marker"


def fail(*args, **kwargs):
    raise RuntimeError(ERROR_MARKER)


@pytest.mark.parametrize(
    ("path", "method", "payload", "error_key"),
    [
        ("/start_bot", "post", None, "message"),
        ("/stop_bot", "post", None, "message"),
        ("/get_logs", "get", None, "error"),
        ("/get_portfolio", "get", None, "error"),
        ("/get_trades", "get", None, "error"),
        ("/update_settings", "post", {"checkInterval": ERROR_MARKER}, "message"),
        ("/get_trading_signals", "get", None, "message"),
    ],
)
def test_handler_errors_hide_details(dashboard, monkeypatch, caplog, path, method, payload, error_key):
    dashboard.bot = SimpleNamespace(
        stop_trading=fail,
        get_balance=fail,
        get_recent_trades=fail,
        get_current_signals=fail,
    )
    dashboard.bot_running = path != "/start_bot"
    monkeypatch.setattr(dashboard, "KrakenBot", fail)
    monkeypatch.setattr(dashboard, "open", fail, raising=False)
    caplog.set_level(logging.INFO)

    response = getattr(dashboard.app.test_client(), method)(path, json=payload)

    assert response.status_code == 500
    assert response.get_json()[error_key].startswith("Error ")
    assert ERROR_MARKER not in response.get_data(as_text=True)
    assert ERROR_MARKER not in caplog.text
    assert "Traceback" not in caplog.text


def test_portfolio_response_preserves_values_and_history(dashboard):
    dashboard.bot = SimpleNamespace(
        get_balance=lambda: {"USD": Decimal("100.5"), "BTC": Decimal("0.25")},
        get_portfolio_value=lambda: Decimal("1100.5"),
    )
    dashboard.bot_running = True
    dashboard.bot_start_time = "2026-01-01T12:00:00"
    dashboard.portfolio_history = [{"timestamp": "2026-01-01T12:00:00", "value": 1100.5}]

    response = dashboard.app.test_client().get("/get_portfolio")

    assert response.status_code == 200
    assert response.get_json() == {
        "portfolio": {"USD": 100.5, "BTC": 0.25},
        "total_value": 1100.5,
        "history": dashboard.portfolio_history,
        "start_time": dashboard.bot_start_time,
    }


def test_start_stop_use_existing_response_contract_without_running_a_worker(dashboard, monkeypatch):
    fake_bot = SimpleNamespace(start_trading=Mock(), stop_trading=Mock())
    worker = SimpleNamespace(start=Mock())
    monkeypatch.setattr(dashboard, "KrakenBot", lambda: fake_bot)
    monkeypatch.setattr(dashboard.threading, "Thread", lambda **kwargs: worker)
    client = dashboard.app.test_client()

    assert client.post("/start_bot").get_json()["status"] == "success"
    assert dashboard.bot_running is True
    fake_bot.start_trading.assert_called_once_with()
    worker.start.assert_called_once_with()
    assert client.post("/start_bot").get_json()["status"] == "warning"
    assert client.post("/stop_bot").get_json()["status"] == "success"
    fake_bot.stop_trading.assert_called_once_with()
    assert dashboard.bot_running is False
    assert dashboard.bot_start_time is None


def test_command_line_entrypoint_keeps_debugger_disabled(monkeypatch, tmp_path):
    static = tmp_path / "static"
    (static / "scss").mkdir(parents=True)
    (static / "scss/main.scss").write_text("body { color: black; }")
    application = flask.Flask("offline_entrypoint", static_folder=str(static))
    run = Mock()
    monkeypatch.setattr(application, "run", run)
    monkeypatch.setattr(flask, "Flask", lambda *args, **kwargs: application)

    namespace = runpy.run_path(str(SOURCE / "app.py"), run_name="__main__")
    try:
        run.assert_called_once_with(debug=False)
        assert application.debug is False
    finally:
        namespace["logger"].removeHandler(namespace["handler"])
        namespace["handler"].close()


def test_bot_valuation_uses_decimal_amounts_without_external_requests():
    bot = KrakenBot.__new__(KrakenBot)
    bot.base_currency = "USD"
    bot.asset_pairs = {"BTCUSD": {}}
    bot.get_balance = lambda: {"ZUSD": Decimal("100.5"), "BTC": Decimal("0.25")}
    bot.get_ticker_info = lambda pair: {"last": Decimal("4000")}

    assert bot.get_portfolio_value() == Decimal("1100.50")


def test_order_below_minimum_never_reaches_exchange():
    bot = KrakenBot.__new__(KrakenBot)
    bot.asset_pairs = {"BTCUSD": {"decimal_places": 4, "min_order": Decimal("0.01")}}
    bot._make_kraken_api_call = Mock(side_effect=AssertionError("No order may be sent"))

    bot.place_order("BTCUSD", "buy", Decimal("0.001"))

    bot._make_kraken_api_call.assert_not_called()


def test_order_error_does_not_log_raw_exchange_response(caplog):
    bot = KrakenBot.__new__(KrakenBot)
    bot.asset_pairs = {"BTCUSD": {"decimal_places": 4, "min_order": Decimal("0.01")}}
    bot._make_kraken_api_call = Mock(return_value={"error": [ERROR_MARKER]})
    caplog.set_level(logging.INFO)

    bot.place_order("BTCUSD", "buy", Decimal("0.02"))

    bot._make_kraken_api_call.assert_called_once_with(
        "private", "AddOrder", {"pair": "BTCUSD", "type": "buy", "ordertype": "market", "volume": "0.0200"}
    )
    assert "Kraken rejected the order" in caplog.text
    assert ERROR_MARKER not in caplog.text


@pytest.mark.parametrize("response", [{"errors": [ERROR_MARKER]}, RuntimeError(ERROR_MARKER)])
def test_news_errors_do_not_log_response_or_request_credentials(monkeypatch, caplog, response):
    bot = KrakenBot.__new__(KrakenBot)
    bot.gnews_api_key = "synthetic-test-token"
    get = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=SimpleNamespace(json=lambda: response))
    monkeypatch.setattr("kraken_bot.requests.get", get)
    caplog.set_level(logging.INFO)

    assert bot.get_news_sentiment("BTC") == Decimal("0")
    assert get.call_count == 1
    assert ERROR_MARKER not in caplog.text
    assert bot.gnews_api_key not in caplog.text


def test_background_failure_does_not_expose_exception(dashboard, monkeypatch, caplog):
    dashboard.bot = SimpleNamespace(rebalance_portfolio=fail)
    dashboard.bot_running = True
    monkeypatch.setattr(dashboard.time, "sleep", lambda seconds: setattr(dashboard, "bot_running", False))
    caplog.set_level(logging.INFO)

    dashboard.run_bot()

    assert "Error in trading strategy" in caplog.text
    assert ERROR_MARKER not in caplog.text

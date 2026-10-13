"""Real Flask requests cannot start or modify trading through an external page."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conftest import SOURCE


REJECTION = {"status": "error", "message": "Local control request rejected"}
SETTINGS = {
    "checkInterval": 60,
    "maxRiskPerTrade": 12,
    "sentimentThreshold": 0.3,
    "rebalanceThreshold": 15,
    "volatilityThreshold": 3,
    "minTradeSize": 10,
}


@pytest.fixture
def controls(dashboard, monkeypatch):
    bot = SimpleNamespace(
        start_trading=Mock(), stop_trading=Mock(),
        check_interval=300, max_risk_per_trade=0.02, sentiment_threshold=0.2,
        rebalance_threshold=0.1, volatility_threshold=0.02, min_trade_size=5,
    )
    factory = Mock(return_value=bot)
    worker = SimpleNamespace(start=Mock())
    thread = Mock(return_value=worker)
    monkeypatch.setattr(dashboard, "KrakenBot", factory)
    monkeypatch.setattr(dashboard.threading, "Thread", thread)
    return SimpleNamespace(dashboard=dashboard, bot=bot, factory=factory, thread=thread, worker=worker)


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://hostile.invalid"},
        {"Origin": "null"},
        {"Origin": "http://localhost:5001"},
        {"Origin": "https://localhost:5000"},
        {"Origin": "http://127.0.0.1:5000"},
        {"Origin": "http://user@localhost:5000"},
        {"Origin": "http://localhost:5000/control"},
        {"Origin": "http://localhost:5000?x=1"},
        {"Origin": "http://localhost:5000#x"},
        {"Origin": "http://localhost:5000:"},
        {"Origin": ""},
        {"Origin": "http://localhost:5000 https://hostile.invalid"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
        {"Sec-Fetch-Site": "unexpected"},
        {"Origin": "http://localhost:5000", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_untrusted_form_cannot_reach_bot_factory_keys_or_worker(controls, caplog, headers):
    response = controls.dashboard.app.test_client().post(
        "/start_bot", base_url="http://localhost:5000", headers=headers, data={"start": "1"}
    )

    assert response.status_code == 403
    assert response.get_json() == REJECTION
    controls.factory.assert_not_called()
    controls.thread.assert_not_called()
    controls.worker.start.assert_not_called()
    controls.bot.start_trading.assert_not_called()
    assert controls.dashboard.bot is None
    assert controls.dashboard.bot_running is False
    assert controls.dashboard.bot_start_time is None
    for value in headers.values():
        if value:
            assert value not in response.get_data(as_text=True)
            assert value not in caplog.text


@pytest.mark.parametrize(
    "host",
    [
        "attacker.invalid:5000", "localhost.attacker.invalid:5000", "127.0.0.2:5000",
        "[::ffff:127.0.0.1]:5000", "localhost:65536", "localhost:abc", "localhost:",
        "localhost/path", "user@localhost:5000", "::1:5000",
    ],
)
@pytest.mark.parametrize(("path", "method"), [("/", "get"), ("/get_bot_status", "get"), ("/start_bot", "post")])
def test_rebinding_and_invalid_hosts_reject_pages_apis_and_mutations(controls, caplog, host, path, method):
    response = getattr(controls.dashboard.app.test_client(), method)(path, headers={"Host": host})

    assert response.status_code == 403
    assert response.get_json() == REJECTION
    assert host not in response.get_data(as_text=True)
    assert host not in caplog.text
    controls.factory.assert_not_called()
    controls.thread.assert_not_called()
    assert controls.dashboard.bot_running is False


@pytest.mark.parametrize("path", ["/stop_bot", "/update_settings"])
@pytest.mark.parametrize(
    "headers",
    [{"Origin": "https://hostile.invalid"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}],
)
def test_stop_and_settings_reject_before_state_changes(controls, path, headers):
    dashboard = controls.dashboard
    dashboard.bot = controls.bot
    dashboard.bot_running = True
    dashboard.bot_start_time = "2026-01-01T12:00:00"
    settings_before = vars(controls.bot).copy()

    response = dashboard.app.test_client().post(path, headers=headers, json=SETTINGS)

    assert response.status_code == 403
    assert response.get_json() == REJECTION
    assert vars(controls.bot) == settings_before
    controls.bot.stop_trading.assert_not_called()
    controls.factory.assert_not_called()
    controls.thread.assert_not_called()
    assert dashboard.bot is controls.bot
    assert dashboard.bot_running is True
    assert dashboard.bot_start_time == "2026-01-01T12:00:00"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:5000", "http://127.0.0.1:5000", "http://[::1]:5000",
        "http://localhost", "http://127.0.0.1:80", "http://[0:0:0:0:0:0:0:1]:5000",
        "http://LOCALHOST:5000",
    ],
)
@pytest.mark.parametrize("headers", [{}, {"Sec-Fetch-Site": "none"}])
def test_local_cli_without_origin_keeps_start_contract(controls, base_url, headers):
    response = controls.dashboard.app.test_client().post("/start_bot", base_url=base_url, headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {"status": "success", "message": "Bot started successfully"}
    controls.factory.assert_called_once_with()
    controls.bot.start_trading.assert_called_once_with()
    controls.thread.assert_called_once_with(target=controls.dashboard.run_bot)
    controls.worker.start.assert_called_once_with()
    assert controls.dashboard.bot_running is True


@pytest.mark.parametrize(
    ("base_url", "origin"),
    [
        ("http://localhost:5000", "http://localhost:5000"),
        ("http://127.0.0.1:5000", "http://127.0.0.1:5000"),
        ("http://[::1]:5000", "http://[::1]:5000"),
        ("http://localhost", "http://localhost:80"),
        ("http://127.0.0.1:80", "http://127.0.0.1"),
        ("http://[0:0:0:0:0:0:0:1]:5000", "http://[::1]:5000"),
        ("http://LOCALHOST:5000", "http://localhost:5000"),
        ("https://localhost:8443", "https://localhost:8443"),
        ("https://[::1]:443", "https://[::1]"),
    ],
)
def test_same_origin_ui_preserves_start_settings_stop(controls, base_url, origin):
    client = controls.dashboard.app.test_client()
    headers = {"Origin": origin, "Sec-Fetch-Site": "same-origin"}

    start = client.post("/start_bot", base_url=base_url, headers=headers)
    assert start.status_code == 200
    controls.factory.assert_called_once_with()
    controls.worker.start.assert_called_once_with()
    update = client.post("/update_settings", base_url=base_url, headers=headers, json=SETTINGS)
    assert update.status_code == 200
    assert update.get_json() == {"status": "success", "message": "Settings updated successfully"}
    assert controls.bot.check_interval == 60
    assert controls.bot.max_risk_per_trade == 0.12
    assert controls.bot.sentiment_threshold == 0.3
    assert controls.bot.rebalance_threshold == 0.15
    assert controls.bot.volatility_threshold == 0.03
    assert controls.bot.min_trade_size == 10
    stop = client.post("/stop_bot", base_url=base_url, headers=headers)
    assert stop.status_code == 200
    controls.bot.stop_trading.assert_called_once_with()
    assert controls.dashboard.bot_running is False
    assert controls.dashboard.bot_start_time is None


@pytest.mark.parametrize(
    ("path", "method", "headers", "status"),
    [
        ("/", "get", {}, 200),
        ("/get_bot_status", "get", {}, 200),
        ("/start_bot", "post", {}, 200),
        ("/stop_bot", "post", {}, 200),
        ("/update_settings", "post", {}, 400),
        ("/start_bot", "post", {"Origin": "https://hostile.invalid"}, 403),
        ("/", "get", {"Host": "attacker.invalid"}, 403),
        ("/start_bot", "post", {"Host": "attacker.invalid"}, 403),
    ],
)
def test_actual_dashboard_and_control_responses_deny_external_framing(
    controls, monkeypatch, path, method, headers, status
):
    # The fixture loads app.py under a synthetic module name; use the actual
    # repository templates so the successful index response renders the real UI.
    monkeypatch.setattr(controls.dashboard.app, "template_folder", str(SOURCE / "templates"))
    response = getattr(controls.dashboard.app.test_client(), method)(path, headers=headers)

    assert response.status_code == status
    assert response.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
    assert response.headers["X-Frame-Options"] == "DENY"
    if path == "/" and status == 200:
        assert "<html" in response.get_data(as_text=True).lower()
    if status == 403:
        assert response.get_json() == REJECTION
        controls.factory.assert_not_called()
        controls.thread.assert_not_called()

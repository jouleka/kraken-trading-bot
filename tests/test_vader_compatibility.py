"""Real offline sentiment and trading decisions with the original NLTK VADER rules."""

import inspect
import sys
from decimal import Decimal
from itertools import count, islice
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from _vendor.nltk_vader import SentimentIntensityAnalyzer
from _vendor.nltk_vader._compat import pairwise
from kraken_bot import KrakenBot


@pytest.fixture
def offline_bot(monkeypatch):
    api = SimpleNamespace(load_key=Mock())
    monkeypatch.setattr("kraken_bot.krakenex.API", lambda: api)
    bot = KrakenBot()
    api.load_key.assert_called_once_with("kraken.key")
    # Exercise the actual news method without elapsed-time throttling; transport
    # stays mocked and the shared fixture prohibits sockets and credential reads.
    news_method = inspect.unwrap(KrakenBot.get_news_sentiment)
    bot.get_news_sentiment = lambda asset: news_method(bot, asset)
    return bot


@pytest.mark.parametrize(
    ("text", "compound"),
    [
        ("", 0.0),
        ("good", 0.4404),
        ("bad", -0.5423),
        ("fine", 0.2023),
        ("assets", 0.1779),
        ("anxiety", -0.1779),
        ("liability", -0.2023),
        ("#good", 0.0),
        ("😍", 0.0),
        ("not good", -0.3412),
    ],
)
def test_real_original_lexicon_scores(text, compound):
    scores = SentimentIntensityAnalyzer().polarity_scores(text)

    assert set(scores) == {"neg", "neu", "pos", "compound"}
    assert scores["compound"] == compound
    assert all(0 <= scores[key] <= 1 for key in ("neg", "neu", "pos"))
    if text not in {"", "😍"}:
        assert sum(scores[key] for key in ("neg", "neu", "pos")) == pytest.approx(1, abs=0.001)
    else:
        assert scores == {"neg": 0.0, "neu": 0.0, "pos": 0.0, "compound": 0.0}


def test_constructor_uses_real_bundled_analyzer_without_a_download(offline_bot):
    assert type(offline_bot.sia) is SentimentIntensityAnalyzer
    assert offline_bot.sia.polarity_scores("BTC fine")["compound"] == 0.2023
    assert offline_bot.sentiment_threshold == Decimal("0.2")
    assert offline_bot.max_risk_per_trade == Decimal("0.02")
    assert offline_bot.is_trading is False


def test_real_news_average_preserves_first_ten_and_decimal_conversion(offline_bot, monkeypatch):
    articles = [{"title": "BTC fine", "description": ""}] * 4
    articles += [{"title": "BTC assets", "description": ""}] * 6
    articles += [{"title": "BTC bad", "description": ""}] * 2
    get = Mock(return_value=SimpleNamespace(json=lambda: {"articles": articles}))
    monkeypatch.setattr("kraken_bot.requests.get", get)

    result = offline_bot.get_news_sentiment("BTC")

    assert result == Decimal(sum([0.2023] * 4 + [0.1779] * 6) / 10)
    assert result < offline_bot.sentiment_threshold
    assert get.call_count == 1


@pytest.mark.parametrize(
    ("headline", "compound", "action"),
    [
        ("BTC assets", Decimal(0.1779), None),
        ("BTC fine", Decimal(0.2023), "buy"),
        ("BTC anxiety", Decimal(-0.1779), None),
        ("BTC liability", Decimal(-0.2023), "sell"),
        (None, Decimal("0.2"), None),
        (None, Decimal("-0.2"), None),
    ],
)
def test_sentiment_threshold_drives_existing_strategy_offline(
    offline_bot, monkeypatch, headline, compound, action
):
    if headline is None:
        offline_bot.get_news_sentiment = lambda asset: compound
    else:
        response = {"articles": [{"title": headline, "description": ""}]}
        monkeypatch.setattr(
            "kraken_bot.requests.get", Mock(return_value=SimpleNamespace(json=lambda: response))
        )
        assert offline_bot.get_news_sentiment("BTC") == compound
    offline_bot.asset_pairs = {"BTCUSD": {}}
    offline_bot.get_asset_pairs = Mock()
    offline_bot.get_balance = lambda: {"USD": "1000", "BTC": "10"}
    # RSI exactly 50 and tied moving averages/MACD disable both technical signals.
    # Each action therefore comes from the real sentiment score around +/- 0.2.
    frame = pd.DataFrame(
        {"close": [100], "SMA_20": [100], "SMA_50": [100], "RSI": [50], "MACD": [0], "Signal": [0]}
    )
    offline_bot.get_historical_data = lambda pair: frame
    offline_bot.calculate_indicators = lambda data: data
    offline_bot.place_order = Mock()
    monkeypatch.setattr("kraken_bot.time.sleep", lambda seconds: None)

    offline_bot.trading_strategy()

    if action is None:
        offline_bot.place_order.assert_not_called()
    else:
        offline_bot.place_order.assert_called_once_with("BTCUSD", action, Decimal("0.20000000"))


def test_extracted_pairwise_keeps_generator_laziness_and_empty_input():
    assert list(islice(pairwise(count()), 3)) == [(0, 1), (1, 2), (2, 3)]
    assert list(pairwise(iter([]))) == []
    assert list(pairwise(iter([4]))) == []


def test_production_imports_do_not_load_the_full_nltk_distribution():
    assert not any(name == "nltk" or name.startswith("nltk.") for name in sys.modules)

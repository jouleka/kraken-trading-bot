"""Offline fixtures: tests cannot load credentials, download data or make requests."""

import importlib.util
import sys
from pathlib import Path

import krakenex
import nltk
import pytest
import requests


SOURCE = Path(__file__).resolve().parents[1] / "kraken-bot"
sys.path.insert(0, str(SOURCE))


@pytest.fixture(autouse=True)
def deny_external_services(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("External service or credential access is forbidden")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(krakenex.API, "load_key", forbidden)
    monkeypatch.setattr(nltk, "download", forbidden)
    monkeypatch.delenv("GNEWS_API_KEY", raising=False)


@pytest.fixture
def dashboard(monkeypatch):
    spec = importlib.util.spec_from_file_location("guardian_test_dashboard", SOURCE / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    yield module
    module.logger.removeHandler(module.handler)
    module.handler.close()


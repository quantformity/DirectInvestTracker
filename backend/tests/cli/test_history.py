"""Tests for qfi_history CLI commands."""
import json
import pytest
import pandas as pd
from datetime import date
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_history import app

runner = CliRunner()


def _mock_cache_df():
    return pd.DataFrame(
        {"Close": [175.0, 178.0, 180.0]},
        index=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    )


def test_symbol_history(db, sample_data):
    mock_df = _mock_cache_df()
    with patch("app.services.history_cache.read_cache", return_value=mock_df), \
         patch("cli.qfi_history.get_session", return_value=db):
        result = runner.invoke(app, ["symbol", "AAPL", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 3
    assert all("date" in p and "close_price" in p and "pnl" in p and "mtm" in p for p in data)


def test_portfolio_history(db, sample_data):
    mock_df = _mock_cache_df()
    with patch("app.services.history_cache.read_cache", return_value=mock_df), \
         patch("cli.qfi_history.get_session", return_value=db):
        result = runner.invoke(app, ["portfolio", "--json"])
    # May return empty if cache is empty; just check it runs without crashing
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


def test_sector_history(db, sample_data):
    mock_df = _mock_cache_df()
    with patch("app.services.history_cache.read_cache", return_value=mock_df), \
         patch("cli.qfi_history.get_session", return_value=db):
        result = runner.invoke(app, ["sector", "Information Technology", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


def test_account_history(db, sample_data):
    acct_id = sample_data["acct1"].id
    mock_df = _mock_cache_df()
    with patch("app.services.history_cache.read_cache", return_value=mock_df), \
         patch("cli.qfi_history.get_session", return_value=db):
        result = runner.invoke(app, ["account", str(acct_id), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)


def test_symbol_history_empty_cache(db, sample_data):
    with patch("app.services.history_cache.read_cache", return_value=pd.DataFrame()), \
         patch("cli.qfi_history.get_session", return_value=db):
        result = runner.invoke(app, ["symbol", "AAPL", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == []

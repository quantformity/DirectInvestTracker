"""Tests for qfi_market CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_market import app

runner = CliRunner()


def invoke(args, db_session):
    with patch("cli.qfi_market.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_quote_returns_latest(db, sample_data):
    result = invoke(["quote", "AAPL", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "AAPL"
    assert data["last_price"] == 180.0
    assert "timestamp" in data


def test_quote_unknown_symbol(db, sample_data):
    result = invoke(["quote", "UNKNOWN", "--json"], db)
    assert result.exit_code == 1


def test_quote_list_returns_all(db, sample_data):
    result = invoke(["quote-list", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    symbols = [d["symbol"] for d in data]
    assert "AAPL" in symbols
    assert "VFV.TO" in symbols


def test_add_market_data(db, sample_data):
    result = invoke(["add", "NVDA", "--price", "500.0", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "NVDA"
    assert data["last_price"] == 500.0


def test_modify_market_data(db, sample_data):
    result = invoke(["modify", "AAPL", "--price", "200.0", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "AAPL"
    assert data["last_price"] == 200.0


def test_history_returns_rows(db, sample_data):
    result = invoke(["history", "AAPL", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all("symbol" in d and "last_price" in d for d in data)


def test_refresh_calls_fetch_prices(db, sample_data, mock_yahoo):
    with patch("cli.qfi_market.get_session", return_value=db), \
         patch("cli.qfi_market.fetch_prices", mock_yahoo["prices"]):
        result = runner.invoke(app, ["refresh", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "updated" in data

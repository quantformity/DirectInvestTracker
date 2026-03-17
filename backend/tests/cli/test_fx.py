"""Tests for qfi_fx CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_fx import app

runner = CliRunner()


def invoke(args, db_session):
    with patch("cli.qfi_fx.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_list_returns_all_pairs(db, sample_data):
    result = invoke(["list", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    pairs = [d["pair"] for d in data]
    assert "USD/CAD" in pairs


def test_show_usd_cad(db, sample_data):
    result = invoke(["show", "USD/CAD", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["pair"] == "USD/CAD"
    assert data["rate"] == 1.36


def test_show_unknown_pair(db, sample_data):
    result = invoke(["show", "XYZ/ABC", "--json"], db)
    assert result.exit_code == 1


def test_add_fx_rate(db):
    result = invoke(["add", "USD/EUR", "0.92", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["pair"] == "USD/EUR"
    assert data["rate"] == 0.92


def test_modify_fx_rate(db, sample_data):
    result = invoke(["modify", "USD/CAD", "1.40", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["pair"] == "USD/CAD"
    assert data["rate"] == 1.40


def test_refresh_calls_fetch_fx_rates_batch(db, sample_data, mock_yahoo):
    with patch("cli.qfi_fx.get_session", return_value=db), \
         patch("cli.qfi_fx.fetch_fx_rates_batch", mock_yahoo["fx"]):
        result = runner.invoke(app, ["refresh", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "updated" in data

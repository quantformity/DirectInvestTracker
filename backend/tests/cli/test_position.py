"""Tests for qfi_position CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_position import app

runner = CliRunner()


def invoke(args, db_session):
    with patch("cli.qfi_position.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_list_returns_all_positions(db, sample_data):
    result = invoke(["list", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 3


def test_list_filter_by_account(db, sample_data):
    acct_id = sample_data["acct1"].id
    result = invoke(["list", "--account-id", str(acct_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    assert all(p["account_id"] == acct_id for p in data)


def test_list_filter_by_category(db, sample_data):
    result = invoke(["list", "--category", "equity", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert all(p["category"] == "Equity" for p in data)
    assert len(data) == 2


def test_add_position(db, sample_data):
    acct_id = sample_data["acct1"].id
    result = invoke([
        "add", "MSFT", "5", "300.0",
        "--account-id", str(acct_id),
        "--category", "equity",
        "--currency", "USD",
        "--json"
    ], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "MSFT"
    assert data["quantity"] == 5.0
    assert data["category"] == "Equity"


def test_add_position_missing_required(db):
    result = invoke(["add", "MSFT", "5"], db)
    # Missing required args returns non-zero exit (typer may return 1 or 2 depending on click version)
    assert result.exit_code != 0


def test_show_position(db, sample_data):
    pos_id = sample_data["pos1"].id
    result = invoke(["show", str(pos_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == pos_id
    assert data["symbol"] == "AAPL"
    assert "current_price" in data
    assert "mtm" in data
    assert "pnl" in data


def test_show_nonexistent_position(db):
    result = invoke(["show", "9999", "--json"], db)
    assert result.exit_code == 1


def test_modify_quantity(db, sample_data):
    pos_id = sample_data["pos1"].id
    result = invoke(["modify", str(pos_id), "--qty", "20", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["quantity"] == 20.0


def test_delete_position(db, sample_data):
    pos_id = sample_data["pos2"].id
    result = invoke(["delete", str(pos_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["success"] is True


def test_pnl_returns_list(db, sample_data):
    result = invoke(["pnl", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert all("pnl" in p and "mtm" in p for p in data)

"""Tests for qfi_sector CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_sector import app

runner = CliRunner()


def invoke(args, db_session):
    with patch("cli.qfi_sector.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_list_returns_all_mappings(db, sample_data):
    result = invoke(["list", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 2
    symbols = [d["symbol"] for d in data]
    assert "AAPL" in symbols


def test_add_sector_mapping(db, sample_data):
    result = invoke(["add", "MSFT", "Information Technology", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "MSFT"
    assert data["sector"] == "Information Technology"


def test_update_sector_mapping(db, sample_data):
    result = invoke(["update", "AAPL", "Tech", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "AAPL"
    assert data["sector"] == "Tech"


def test_delete_sector_mapping(db, sample_data):
    result = invoke(["delete", "VFV.TO", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["success"] is True


def test_show_sector(db, sample_data):
    result = invoke(["show", "Information Technology", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    symbols = [d["symbol"] for d in data]
    assert "AAPL" in symbols


def test_sector_summary(db, sample_data):
    result = invoke(["summary", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert all("sector" in d and "symbol_count" in d and "total_mtm" in d for d in data)

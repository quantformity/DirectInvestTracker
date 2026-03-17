"""Tests for qfi_report CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_report import app

runner = CliRunner()


def invoke(args, db_session):
    with patch("cli.qfi_report.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_generate_json(db, sample_data):
    result = invoke(["generate", "--format", "json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "positions" in data
    assert "total_mtm" in data
    assert "total_pnl" in data
    assert "sector_breakdown" in data
    assert "account_breakdown" in data
    assert "reporting_currency" in data


def test_generate_html(db, sample_data):
    result = invoke(["generate", "--format", "html"], db)
    assert result.exit_code == 0
    output = result.output
    assert "<html" in output
    assert "data-llm-section" in output
    assert "bootstrap" in output.lower()


def test_generate_csv(db, sample_data):
    result = invoke(["generate", "--format", "csv"], db)
    assert result.exit_code == 0
    output = result.output
    assert "," in output
    assert "symbol" in output


def test_positions_report(db, sample_data):
    result = invoke(["positions", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 3
    assert all("symbol" in p and "mtm" in p and "pnl" in p for p in data)


def test_pnl_report(db, sample_data):
    result = invoke(["pnl", "--period", "1m", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "total_pnl" in data
    assert "positions" in data
    assert "period" in data


def test_sector_breakdown(db, sample_data):
    result = invoke(["sector-breakdown", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert all("sector" in d and "total_mtm" in d for d in data)


def test_account_breakdown(db, sample_data):
    result = invoke(["account-breakdown", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert all("account_name" in d and "total_mtm" in d for d in data)

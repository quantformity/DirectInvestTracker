"""Tests for qfi_summary CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_summary import app

runner = CliRunner()


def invoke(args, db_session):
    with patch("cli.qfi_summary.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_show_returns_groups_and_totals(db, sample_data):
    result = invoke(["show", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "groups" in data
    assert "total_mtm_reporting" in data
    assert "total_pnl_reporting" in data
    assert "reporting_currency" in data
    assert isinstance(data["groups"], list)


def test_show_group_by_account(db, sample_data):
    result = invoke(["show", "--group-by", "account", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    group_keys = [g["group_key"] for g in data["groups"]]
    assert "TFSA" in group_keys
    assert "RRSP" in group_keys


def test_show_group_by_sector(db, sample_data):
    result = invoke(["show", "--group-by", "sector", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "groups" in data
    group_keys = [g["group_key"] for g in data["groups"]]
    assert "Information Technology" in group_keys


def test_account_summary(db, sample_data):
    acct_id = sample_data["acct1"].id
    result = invoke(["account", str(acct_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["account_id"] == acct_id
    assert data["account_name"] == "TFSA"
    assert "groups" in data


def test_category_summary(db, sample_data):
    result = invoke(["category", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "groups" in data
    group_keys = [g["group_key"] for g in data["groups"]]
    assert "Equity" in group_keys
    assert "Cash" in group_keys

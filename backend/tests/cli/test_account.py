"""Tests for qfi_account CLI commands."""
import json
import pytest
from unittest.mock import patch
from typer.testing import CliRunner

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from cli.qfi_account import app

runner = CliRunner()


def invoke(args, db_session):
    """Invoke CLI with patched db session."""
    with patch("cli.qfi_account.get_session", return_value=db_session):
        return runner.invoke(app, args)


def test_list_returns_json(db, sample_data):
    result = invoke(["list", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 2
    assert all("id" in item and "name" in item and "base_currency" in item for item in data)


def test_list_human_readable(db, sample_data):
    result = invoke(["list"], db)
    assert result.exit_code == 0
    assert "TFSA" in result.output
    assert "RRSP" in result.output


def test_add_account(db):
    result = invoke(["add", "TestAccount", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "TestAccount"
    assert data["base_currency"] == "CAD"
    assert "id" in data


def test_add_account_custom_currency(db):
    result = invoke(["add", "USD Account", "--currency", "USD", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["base_currency"] == "USD"


def test_show_account(db, sample_data):
    acct_id = sample_data["acct1"].id
    result = invoke(["show", str(acct_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == acct_id
    assert data["name"] == "TFSA"
    assert "total_mtm" in data
    assert "reporting_currency" in data


def test_show_nonexistent_account(db):
    result = invoke(["show", "9999", "--json"], db)
    assert result.exit_code == 1


def test_rename_account(db, sample_data):
    acct_id = sample_data["acct1"].id
    result = invoke(["rename", str(acct_id), "MyTFSA", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "MyTFSA"


def test_delete_account(db, sample_data):
    acct_id = sample_data["acct2"].id
    result = invoke(["delete", str(acct_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["success"] is True


def test_mtm_returns_list(db, sample_data):
    result = invoke(["mtm", "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all("account_id" in item and "account_name" in item and "mtm" in item for item in data)


def test_mtm_filtered_by_account(db, sample_data):
    acct_id = sample_data["acct1"].id
    result = invoke(["mtm", "--account-id", str(acct_id), "--json"], db)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["account_id"] == acct_id

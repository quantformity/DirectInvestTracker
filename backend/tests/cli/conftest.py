"""Shared test fixtures for CLI tool tests."""
import pytest
from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

# Add backend to path
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.models import Base, Account, Position, MarketData, FxRate, SectorMapping, CategoryEnum


@pytest.fixture
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_data(db):
    """Insert representative sample data."""
    acct1 = Account(name="TFSA", base_currency="CAD")
    acct2 = Account(name="RRSP", base_currency="CAD")
    db.add_all([acct1, acct2])
    db.flush()

    pos1 = Position(account_id=acct1.id, symbol="AAPL", category=CategoryEnum.Equity,
                    quantity=10, cost_per_share=150.0, currency="USD", date_added=date(2024, 1, 1))
    pos2 = Position(account_id=acct1.id, symbol="CASH", category=CategoryEnum.Cash,
                    quantity=1000, cost_per_share=1.0, currency="CAD", date_added=date(2024, 1, 1))
    pos3 = Position(account_id=acct2.id, symbol="VFV.TO", category=CategoryEnum.Equity,
                    quantity=5, cost_per_share=100.0, currency="CAD", date_added=date(2024, 2, 1))
    db.add_all([pos1, pos2, pos3])
    db.flush()

    md1 = MarketData(symbol="AAPL", company_name="Apple Inc.", last_price=180.0,
                     pe_ratio=28.5, change_percent=0.5, beta=1.2,
                     timestamp=datetime.now(timezone.utc))
    md2 = MarketData(symbol="VFV.TO", company_name="Vanguard S&P 500",
                     last_price=110.0, pe_ratio=None, change_percent=0.3, beta=None,
                     timestamp=datetime.now(timezone.utc))
    db.add_all([md1, md2])

    fx1 = FxRate(pair="USD/CAD", rate=1.36, timestamp=datetime.now(timezone.utc))
    db.add(fx1)

    sec1 = SectorMapping(symbol="AAPL", sector="Information Technology")
    sec2 = SectorMapping(symbol="VFV.TO", sector="Unspecified")
    db.add_all([sec1, sec2])

    db.commit()
    return {"acct1": acct1, "acct2": acct2, "pos1": pos1, "pos2": pos2, "pos3": pos3}


@pytest.fixture
def mock_yahoo():
    """Mock Yahoo Finance calls to prevent network access."""
    with patch("app.services.yahoo_finance.fetch_prices") as mock_prices, \
         patch("app.services.yahoo_finance.fetch_fx_rates_batch") as mock_fx, \
         patch("app.services.yahoo_finance.fetch_history") as mock_hist:
        mock_prices.return_value = {
            "AAPL": {"last_price": 180.0, "pe_ratio": 28.5, "change_percent": 0.5, "beta": 1.2, "company_name": "Apple Inc."}
        }
        mock_fx.return_value = {"USD/CAD": 1.36}
        import pandas as pd
        from datetime import date
        mock_hist.return_value = pd.DataFrame(
            {"Close": [175.0, 178.0, 180.0]},
            index=[date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        )
        yield {"prices": mock_prices, "fx": mock_fx, "hist": mock_hist}

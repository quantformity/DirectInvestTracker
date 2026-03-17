"""Re-export Yahoo Finance functions for CLI use."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.yahoo_finance import fetch_prices, fetch_fx_rates_batch, fetch_fx_rate, fetch_history

__all__ = ["fetch_prices", "fetch_fx_rates_batch", "fetch_fx_rate", "fetch_history"]

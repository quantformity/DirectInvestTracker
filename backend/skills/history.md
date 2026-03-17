# Portfolio History — `qfi-history`

Views historical portfolio performance from the DB cache. All commands read from the local SQLite cache (fast, no Yahoo Finance calls).

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Notes
- All commands use `use_cache=True` — reads from local DB only, never calls Yahoo Finance
- To populate the cache, run `qfi-market refresh --full-history` first
- Date filters use YYYY-MM-DD format
- MTM and P&L values are in reporting currency (CAD by default)
- Returns empty list `[]` if no cached data is available

## Commands

### Portfolio aggregate history
**Usage:** `qfi-history portfolio --json`
**Filter by account:** `qfi-history portfolio --account-id 1 --json`
**With date range:** `qfi-history portfolio --from 2024-01-01 --to 2024-12-31 --json`
**Returns:** `[{"date": "2024-01-02", "mtm": 95420.12, "pnl": 1234.56, "cash_gic": 10000.0}, ...]`

### Symbol history
**Usage:** `qfi-history symbol AAPL --json`
**With date range:** `qfi-history symbol AAPL --from 2024-01-01 --json`
**Returns:** `[{"date": "2024-01-02", "close_price": 180.5, "pnl": 305.0, "mtm": 1805.0}, ...]`

### Sector history
**Usage:** `qfi-history sector "Information Technology" --json`
**With date range:** `qfi-history sector "Information Technology" --from 2024-01-01 --json`
**Returns:** Same as portfolio format but filtered to sector symbols

### Account history
**Usage:** `qfi-history account 1 --json`
**With date range:** `qfi-history account 1 --from 2024-01-01 --json`
**Returns:** Same as portfolio format but filtered to account

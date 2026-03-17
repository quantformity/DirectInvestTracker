# FX Rates — `qfi-fx`

Manages foreign exchange rates used for portfolio valuation.

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Notes
- Pair format is "FROM/TO" e.g. "USD/CAD", "EUR/USD"
- FX rates are append-only: new rows are always inserted, not updated in-place
- The system uses the most recent row per pair for valuations
- `refresh` derives needed pairs from current positions/accounts

## Commands

### List latest FX rates
**Usage:** `qfi-fx list --json`
**Returns:** `[{"pair": "USD/CAD", "rate": 1.36, "timestamp": "..."}, ...]`

### Show rate for a pair
**Usage:** `qfi-fx show USD/CAD --json`
**Returns:** `{"pair": "USD/CAD", "rate": 1.36, "timestamp": "..."}`

### Refresh FX rates from Yahoo Finance
**Usage:** `qfi-fx refresh --json`
**Returns:** `{"updated": ["USD/CAD", "EUR/CAD"], "count": 2}`
**Note:** Derives required pairs automatically from positions and accounts

### Add FX rate manually
**Usage:** `qfi-fx add USD/CAD 1.36 --json`
**Returns:** `{"pair": "USD/CAD", "rate": 1.36, "timestamp": "..."}`

### Update FX rate (insert new row)
**Usage:** `qfi-fx modify USD/CAD 1.40 --json`
**Returns:** `{"pair": "USD/CAD", "rate": 1.40, "timestamp": "..."}`

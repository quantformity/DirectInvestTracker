# Market Data — `qfi-market`

Manages market price data for tracked symbols.

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Notes
- `refresh` calls Yahoo Finance live and may take several seconds
- `history` reads from the DB (fast, no network calls)
- `--full-history` in refresh fetches full price history back to earliest position date and writes to history cache
- Market data is append-only: new rows are always inserted, not updated in-place

## Commands

### Get latest quote for a symbol
**Usage:** `qfi-market quote AAPL --json`
**Returns:** `{"symbol": "AAPL", "company_name": "Apple Inc.", "last_price": 180.5, "pe_ratio": 28.5, "change_percent": 0.5, "beta": 1.2, "timestamp": "..."}`

### Get latest quotes for all symbols
**Usage:** `qfi-market quote-list --json`
**Returns:** Array of quote objects (one per symbol, latest only)

### Refresh prices from Yahoo Finance
**Usage:** `qfi-market refresh --json`
**Specific symbol:** `qfi-market refresh --symbol AAPL --json`
**With history:** `qfi-market refresh --full-history --json`
**Returns:** `{"updated": ["AAPL", "VFV.TO"], "count": 2}`

### Manually add market data
**Usage:** `qfi-market add AAPL --price 180.0 --json`
**Full:** `qfi-market add AAPL --price 180.0 --pe 28.5 --change 0.5 --beta 1.2 --name "Apple Inc." --json`
**Returns:** Created market data object

### Insert updated market data row
**Usage:** `qfi-market modify AAPL --price 185.0 --json`
**Note:** Copies existing pe/change/beta values for unspecified fields
**Returns:** New market data row

### Query price history from DB
**Usage:** `qfi-market history AAPL --json`
**With date range:** `qfi-market history AAPL --from 2024-01-01 --to 2024-12-31 --json`
**Returns:** Array of `{symbol, timestamp, last_price, pe_ratio, change_percent, beta, company_name}`

# Position Management — `qfi-position`

Manages investment positions within accounts.

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Enriched Position Fields

| Field | Description |
|-------|-------------|
| `id` | Position ID |
| `symbol` | Ticker symbol (e.g. AAPL, VFV.TO) |
| `category` | Category: Equity, GIC, Cash, or Dividend |
| `account_id` | Parent account ID |
| `account_name` | Parent account name |
| `quantity` | Number of units held |
| `cost_per_share` | Average cost per unit in position currency |
| `currency` | Position trading currency (e.g. USD, CAD) |
| `date_added` | Date position was opened (YYYY-MM-DD) |
| `yield_rate` | Annual yield rate (for GIC, e.g. 0.045 = 4.5%) |
| `current_price` | Latest market price in position currency |
| `mtm` | Mark-to-market value in reporting currency (CAD default) |
| `pnl` | Unrealised profit/loss in reporting currency |

## Commands

### List positions
**Usage:** `qfi-position list --json`
**Filter by account:** `qfi-position list --account-id 1 --json`
**Filter by category:** `qfi-position list --category equity --json`
**Valid categories:** equity, gic, cash, dividend
**Returns:** Array of enriched position objects

### Show position
**Usage:** `qfi-position show 5 --json`
**Returns:** Single enriched position object

### Add position
**Usage:** `qfi-position add AAPL 10 150.0 --account-id 1 --category equity --currency USD --json`
**With date:** `qfi-position add AAPL 10 150.0 --account-id 1 --category equity --date 2024-01-15 --json`
**With yield:** `qfi-position add "GIC001" 10000 1.0 --account-id 1 --category gic --yield-rate 0.045 --json`
**Returns:** Created enriched position object

### Modify position
**Usage:** `qfi-position modify 5 --qty 20 --json`
**Options:** `--qty`, `--cost`, `--currency`, `--yield-rate`, `--account-id`
**Returns:** Updated enriched position object

### Delete position
**Usage:** `qfi-position delete 5 --json`
**Returns:** `{"success": true, "message": "Position 5 deleted"}`

### P&L summary
**Usage:** `qfi-position pnl --json`
**Filter:** `qfi-position pnl --account-id 1 --json` or `qfi-position pnl --symbol AAPL --json`
**Returns:** Array of `{id, symbol, account_name, quantity, cost_per_share, current_price, mtm, pnl, currency}`

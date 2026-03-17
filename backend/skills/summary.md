# Portfolio Summary — `qfi-summary`

Provides snapshot summary views of current portfolio state.

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Notes
- All monetary values are in reporting currency (CAD by default, set via `REPORTING_CURRENCY` env var)
- MTM uses latest market prices from DB (no live Yahoo Finance calls)
- FX conversion uses latest stored FX rates

## group-by Options
| Value | Description |
|-------|-------------|
| `category` | Group by Equity / GIC / Cash / Dividend |
| `account` | Group by account name |
| `symbol` | Group by ticker symbol |
| `sector` | Group by sector mapping |
| `cash_gic` | Split GIC/Cash vs Other |

## Commands

### Portfolio summary
**Usage:** `qfi-summary show --json`
**Group by account:** `qfi-summary show --group-by account --json`
**Group by sector:** `qfi-summary show --group-by sector --json`
**Group by symbol:** `qfi-summary show --group-by symbol --json`
**Returns:**
```json
{
  "groups": [
    {
      "group_key": "Equity",
      "total_mtm_reporting": 85420.12,
      "total_pnl_reporting": 3210.00,
      "proportion": 89.5
    }
  ],
  "total_mtm_reporting": 95420.12,
  "total_pnl_reporting": 4210.00,
  "reporting_currency": "CAD"
}
```

### Account MTM breakdown
**Usage:** `qfi-summary account 1 --json`
**Returns:** Summary grouped by symbol for the specified account, plus `account_id` and `account_name` fields

### Sector breakdown
**Usage:** `qfi-summary sector --json`
**Specific sector:** `qfi-summary sector "Information Technology" --json`
**Returns:** Summary grouped by sector

### Category breakdown
**Usage:** `qfi-summary category --json`
**Returns:** Summary grouped by category (Equity/GIC/Cash/Dividend)

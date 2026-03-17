# Report Generation — `qfi-report`

Generates comprehensive investment portfolio reports in JSON, CSV, or HTML format.

## Important
Always use the `--json` flag for structured output. The `--format` option controls the report format for `generate`. On error, output is `{"error": "message"}` and exit code 1.

## HTML Format Notes
The HTML report contains `data-llm-section` placeholder divs intended for agent-generated narrative text. The tool itself does **not** make any LLM calls. After receiving the HTML output, an agent should:
1. Find all elements with `data-llm-section` attribute
2. Read the `data-context` JSON attribute for context data
3. Generate appropriate narrative text
4. Insert the narrative into the div (replacing the comment)

Example placeholder:
```html
<div class="llm-narrative" data-llm-section="portfolio_overview" data-context='{"total_mtm": 95420.12}'>
  <!-- Agent: insert portfolio overview narrative here -->
</div>
```

## Commands

### Generate comprehensive report
**Usage:** `qfi-report generate --format json`
**HTML format:** `qfi-report generate --format html`
**CSV format:** `qfi-report generate --format csv`
**Filter by account:** `qfi-report generate --format json --account-id 1`
**With date range:** `qfi-report generate --format json --from 2024-01-01 --to 2024-12-31`

**JSON Returns:**
```json
{
  "generated_at": "2025-03-17 12:00:00",
  "reporting_currency": "CAD",
  "total_mtm": 95420.12,
  "total_pnl": 4210.00,
  "positions": [...],
  "sector_breakdown": [...],
  "account_breakdown": [...]
}
```

### Positions report
**Usage:** `qfi-report positions --json`
**Filter:** `qfi-report positions --account-id 1 --json`
**Returns:** Array of enriched position objects

### P&L report
**Usage:** `qfi-report pnl --period 1m --json`
**Periods:** 1d, 1w, 1m, 3m, 1y, all
**Returns:**
```json
{
  "period": "1m",
  "reporting_currency": "CAD",
  "total_pnl": 4210.00,
  "positions": [{"symbol": "AAPL", "pnl": 3050.0, ...}]
}
```

### Sector breakdown report
**Usage:** `qfi-report sector-breakdown --json`
**Returns:** `[{"sector": "Information Technology", "total_mtm": 45230.12, "total_pnl": 2100.0, "symbols": ["AAPL"]}, ...]`

### Account breakdown report
**Usage:** `qfi-report account-breakdown --json`
**Returns:** `[{"account_id": 1, "account_name": "TFSA", "total_mtm": 55230.12, "total_pnl": 2100.0}, ...]`

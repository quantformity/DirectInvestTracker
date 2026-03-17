# Sector Mappings — `qfi-sector`

Manages symbol-to-sector mappings for portfolio categorization.

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Notes
- Symbols without a mapping are treated as "Unspecified" in summary/history views
- `add` and `update` both perform upsert (create or replace)
- Sector names are case-sensitive (use consistent naming)

## Commands

### List all mappings
**Usage:** `qfi-sector list --json`
**Returns:** `[{"symbol": "AAPL", "sector": "Information Technology"}, ...]`

### Add sector mapping
**Usage:** `qfi-sector add AAPL "Information Technology" --json`
**Returns:** `{"symbol": "AAPL", "sector": "Information Technology"}`

### Update sector mapping (upsert)
**Usage:** `qfi-sector update AAPL "Technology" --json`
**Returns:** `{"symbol": "AAPL", "sector": "Technology"}`

### Delete sector mapping
**Usage:** `qfi-sector delete AAPL --json`
**Returns:** `{"success": true, "message": "Sector mapping for AAPL deleted"}`

### List symbols in a sector
**Usage:** `qfi-sector show "Information Technology" --json`
**Returns:** `[{"symbol": "AAPL", "sector": "Information Technology"}, ...]`

### Sector summary with MTM
**Usage:** `qfi-sector summary --json`
**Returns:** `[{"sector": "Information Technology", "symbol_count": 3, "total_mtm": 45230.12}, ...]`

# Account Management — `qfi-account`

Manages investment accounts (e.g. TFSA, RRSP).

## Important
Always use the `--json` flag. All output is JSON. On error, output is `{"error": "message"}` and exit code 1.

## Commands

### List all accounts
**Usage:** `qfi-account list --json`
**Returns:** `[{"id": 1, "name": "TFSA", "base_currency": "CAD"}, ...]`

### Add an account
**Usage:** `qfi-account add "TFSA" --currency CAD --json`
**Returns:** `{"id": 1, "name": "TFSA", "base_currency": "CAD"}`

### Show account details with MTM
**Usage:** `qfi-account show 1 --json`
**Returns:** `{"id": 1, "name": "TFSA", "base_currency": "CAD", "total_mtm": 45230.12, "reporting_currency": "CAD"}`

### Rename an account
**Usage:** `qfi-account rename 1 "New Name" --json`
**Returns:** `{"id": 1, "name": "New Name", "base_currency": "CAD"}`

### Delete an account
**Usage:** `qfi-account delete 1 --json`
**Returns:** `{"success": true, "message": "Account 1 deleted"}`

### Mark-to-market per account
**Usage:** `qfi-account mtm --json`  or  `qfi-account mtm --account-id 1 --json`
**Returns:** `[{"account_id": 1, "account_name": "TFSA", "mtm": 45230.12, "reporting_currency": "CAD"}]`

"""Output helpers for CLI tools."""
import json
import sys

_last_json_mode: bool = False


def print_output(data, use_json: bool) -> None:
    """Print data as JSON or human-readable text."""
    global _last_json_mode
    _last_json_mode = use_json

    if use_json:
        print(json.dumps(data, indent=2, default=str))
        return

    if isinstance(data, list):
        if not data:
            print("(no results)")
            return
        if data and isinstance(data[0], dict):
            # ASCII table
            headers = list(data[0].keys())
            col_widths = {h: len(str(h)) for h in headers}
            for row in data:
                for h in headers:
                    col_widths[h] = max(col_widths[h], len(str(row.get(h, ""))))

            separator = "+-" + "-+-".join("-" * col_widths[h] for h in headers) + "-+"
            header_row = "| " + " | ".join(str(h).ljust(col_widths[h]) for h in headers) + " |"
            print(separator)
            print(header_row)
            print(separator)
            for row in data:
                line = "| " + " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers) + " |"
                print(line)
            print(separator)
        else:
            for item in data:
                print(item)
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"{k}: {v}")
    elif isinstance(data, str):
        print(data)
    else:
        print(str(data))


def error_exit(msg: str) -> None:
    """Print error and exit with code 1."""
    if _last_json_mode:
        print(json.dumps({"error": msg}))
    else:
        print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def success_output(msg: str, use_json: bool) -> None:
    """Print success message."""
    global _last_json_mode
    _last_json_mode = use_json

    if use_json:
        print(json.dumps({"success": True, "message": msg}))
    else:
        print(msg)

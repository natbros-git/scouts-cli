"""Human-readable output formatter for Scouts CLI."""

import sys


class HumanFormatter:
    """Outputs readable text for direct terminal use."""

    def output_result(self, result, metadata=None):
        """Output result in human-readable format."""
        if isinstance(result, list):
            self._format_list(result)
        elif isinstance(result, dict):
            self._format_dict(result)
        else:
            print(result)

    def output_error(self, error):
        """Output error in human-readable format."""
        message = getattr(error, 'message', str(error))
        suggestion = getattr(error, 'suggestion', None)

        print(f"Error: {message}", file=sys.stderr)
        if suggestion:
            print(f"  Suggestion: {suggestion}", file=sys.stderr)

    def _format_list(self, items):
        """Format a list of items."""
        if not items:
            print("(no results)")
            return

        # Check if items are dicts (table format)
        if isinstance(items[0], dict):
            self._format_table(items)
        else:
            for item in items:
                print(f"  - {item}")

    def _format_dict(self, data, indent=0):
        """Format a dictionary."""
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"{prefix}{key}:")
                self._format_dict(value, indent + 1)
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                print(f"{prefix}{key}: ({len(value)} items)")
                for item in value[:5]:
                    self._format_dict(item, indent + 1)
                    print(f"{prefix}  ---")
                if len(value) > 5:
                    print(f"{prefix}  ... and {len(value) - 5} more")
            else:
                print(f"{prefix}{key}: {value}")

    def _format_table(self, items):
        """Format list of dicts as a simple table."""
        if not items:
            return

        # Pick columns: use first item's keys, limit to reasonable width
        keys = list(items[0].keys())
        # Skip deeply nested fields
        keys = [k for k in keys if not isinstance(items[0].get(k), (dict, list))]

        # Calculate column widths
        widths = {}
        for key in keys:
            values = [str(item.get(key, ''))[:40] for item in items]
            widths[key] = max(len(key), max(len(v) for v in values))

        # Header
        header = "  ".join(key.ljust(widths[key]) for key in keys)
        print(header)
        print("-" * len(header))

        # Rows
        for item in items:
            row = "  ".join(str(item.get(key, '')).ljust(widths[key])[:40] for key in keys)
            print(row)

        print(f"\n({len(items)} total)")

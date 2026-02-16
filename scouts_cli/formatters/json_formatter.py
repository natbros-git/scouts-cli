"""JSON output formatter for Scouts CLI."""

import json
import sys
from datetime import datetime, timezone


class JsonFormatter:
    """Outputs structured JSON for AI agent consumption."""

    def output_result(self, result, metadata=None):
        """Output successful result as structured JSON."""
        output = {
            'result': result,
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **(metadata or {})
            }
        }
        print(json.dumps(output, indent=2))

    def output_error(self, error):
        """Output error as structured JSON to stderr."""
        if hasattr(error, 'to_dict'):
            error_dict = error.to_dict()
        else:
            error_dict = {
                'error': type(error).__name__,
                'message': str(error)
            }
        error_dict['timestamp'] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(error_dict, indent=2), file=sys.stderr)

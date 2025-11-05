#!/usr/bin/env python3
"""Helper script to securely write CWD for a tab.

Called from shell hooks with: python3 -m smart_tabs.write_cwd <tab_id> <cwd>
"""

import sys
from .tempfiles import write_cwd_atomic


def main():
    """Write CWD to temp file securely."""
    if len(sys.argv) != 3:
        print("Usage: python3 -m smart_tabs.write_cwd <tab_id> <cwd>", file=sys.stderr)
        sys.exit(1)

    try:
        tab_id = int(sys.argv[1])
        cwd = sys.argv[2]
        write_cwd_atomic(tab_id, cwd)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error writing CWD: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

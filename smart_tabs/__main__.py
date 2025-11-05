"""Entry point for module execution."""

import sys


if __name__ == '__main__':
    # Check if write_cwd subcommand
    if len(sys.argv) > 1 and sys.argv[0].endswith('write_cwd'):
        from .write_cwd import main
        main()
    else:
        print("Usage: python3 -m smart_tabs.write_cwd <tab_id> <cwd>", file=sys.stderr)
        sys.exit(1)

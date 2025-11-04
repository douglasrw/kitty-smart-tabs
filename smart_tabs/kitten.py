#!/usr/bin/env python3
"""Kitten entry point for Smart Tabs.

This is the main kitten that can be invoked explicitly:
    kitten smart_tabs [--debug]

Or triggered by key mappings in kitty.conf.
"""

import sys
from .core import update_tabs


def main(args: list[str]) -> str:
    """Main kitten entry point.

    Args:
        args: Command-line arguments

    Returns:
        Empty string (no result to pass to handle_result)
    """
    debug = '--debug' in args
    update_tabs(debug=debug)
    return ""


# For standalone execution
if __name__ == '__main__':
    main(sys.argv[1:])

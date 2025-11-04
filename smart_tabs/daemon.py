#!/usr/bin/env python3
"""Background daemon for Smart Tabs.

Polls every N seconds to detect running commands and update tab titles.
"""

import sys
import time
from pathlib import Path

from .core import update_tabs
from .config import Config


def run_daemon(debug: bool = False):
    """Run the background polling daemon.

    Args:
        debug: Enable debug logging
    """
    config = Config()
    poll_interval = config.poll_interval

    log_file = Path.home() / '.config/kitty/smart_tabs_daemon.log'

    if debug:
        with open(log_file, 'w') as f:
            f.write(f"Smart Tabs daemon started\n")
            f.write(f"Poll interval: {poll_interval}s\n")

    iteration = 0
    while True:
        try:
            time.sleep(poll_interval)
            iteration += 1

            if debug and iteration % 5 == 0:  # Debug every 5th iteration
                with open(log_file, 'a') as f:
                    f.write(f"\n[{iteration}] Running update\n")
                update_tabs(debug=True)
            else:
                update_tabs(debug=False)

        except KeyboardInterrupt:
            if debug:
                with open(log_file, 'a') as f:
                    f.write("Daemon stopped by user\n")
            break
        except Exception as e:
            if debug:
                with open(log_file, 'a') as f:
                    f.write(f"Error in daemon: {e}\n")
            # Continue running even on error
            continue


def main():
    """Main entry point for daemon."""
    debug = '--debug' in sys.argv
    run_daemon(debug=debug)


if __name__ == '__main__':
    main()

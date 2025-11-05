#!/usr/bin/env python3
"""Background daemon for Smart Tabs.

Polls every N seconds to detect running commands and update tab titles.
"""

import sys
import os
import time
import atexit
import signal
from pathlib import Path

from .core import update_tabs
from .config import Config
from .tempfiles import get_temp_dir, cleanup_temp_files

# Global shutdown flag for signal handling
# Using flag-based approach per best practices (logging in handlers not re-entrant safe)
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully.

    Sets global flag for main loop to check.
    Best practice: Don't log here (threading locks not re-entrant safe).
    """
    global _shutdown_requested
    _shutdown_requested = True


def acquire_lock() -> Path:
    """Acquire PID lock file to prevent multiple daemon instances.

    Returns:
        Path to lock file.

    Raises:
        RuntimeError: If lock is already held by another process.
    """
    lock_file = get_temp_dir() / 'daemon.pid'

    # Check if lock file exists
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
            # Check if process is still running
            try:
                os.kill(pid, 0)  # Signal 0 checks if process exists
                raise RuntimeError(
                    f"Daemon already running (PID {pid}). "
                    f"If not running, remove {lock_file}"
                )
            except OSError:
                # Process not running, stale lock file
                lock_file.unlink()
        except (ValueError, OSError):
            # Invalid or inaccessible lock file, remove it
            try:
                lock_file.unlink()
            except Exception:
                pass

    # Write our PID to lock file
    lock_file.write_text(str(os.getpid()))
    lock_file.chmod(0o600)

    # Register cleanup on exit
    def cleanup():
        try:
            if lock_file.exists():
                current_pid = int(lock_file.read_text().strip())
                if current_pid == os.getpid():
                    lock_file.unlink()
        except Exception:
            pass

    atexit.register(cleanup)
    return lock_file


def run_daemon(debug: bool = False):
    """Run the background polling daemon with adaptive polling.

    Args:
        debug: Enable debug logging
    """
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Acquire lock to prevent multiple instances
    try:
        lock_file = acquire_lock()
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Register cleanup of temp files on exit
    atexit.register(cleanup_temp_files)

    config = Config()
    base_interval = config.poll_interval
    current_interval = base_interval
    max_interval = base_interval * 4  # Max 4x base interval when idle
    idle_iterations = 0
    idle_threshold = 3  # After 3 iterations with no changes, increase interval

    log_file = Path.home() / '.config/kitty/smart_tabs_daemon.log'

    if debug:
        with open(log_file, 'w') as f:
            f.write(f"Smart Tabs daemon started\n")
            f.write(f"Base poll interval: {base_interval}s\n")

    iteration = 0
    while not _shutdown_requested:
        try:
            # Skip sleep on first iteration for immediate startup response
            if iteration > 0:
                time.sleep(current_interval)
            iteration += 1

            # Check shutdown flag after sleep
            if _shutdown_requested:
                break

            # Run update and get number of actual changes made
            if debug and iteration % 5 == 0:  # Debug every 5th iteration
                with open(log_file, 'a') as f:
                    f.write(f"\n[{iteration}] Running update (interval={current_interval}s)\n")
                changes_made = update_tabs(debug=True)
            else:
                changes_made = update_tabs(debug=False)

            # Adaptive polling: if no changes made, gradually increase interval
            if changes_made == 0:
                idle_iterations += 1
                if idle_iterations >= idle_threshold and current_interval < max_interval:
                    current_interval = min(current_interval * 1.5, max_interval)
                    if debug:
                        with open(log_file, 'a') as f:
                            f.write(f"No changes for {idle_iterations} iterations, increasing poll interval to {current_interval:.1f}s\n")
            else:
                # Changes detected, reset to base interval
                if current_interval != base_interval:
                    current_interval = base_interval
                    if debug:
                        with open(log_file, 'a') as f:
                            f.write(f"Activity detected ({changes_made} changes), resetting to base interval\n")
                idle_iterations = 0

        except Exception as e:
            if debug:
                with open(log_file, 'a') as f:
                    f.write(f"Error in daemon: {e}\n")
            # Continue running even on error
            continue

    # Graceful shutdown
    if debug:
        with open(log_file, 'a') as f:
            f.write("Daemon shutting down gracefully\n")


def main():
    """Main entry point for daemon."""
    debug = '--debug' in sys.argv
    run_daemon(debug=debug)


if __name__ == '__main__':
    main()

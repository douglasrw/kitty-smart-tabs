"""Secure temporary file operations for Smart Tabs."""

import os
import tempfile
from pathlib import Path
from typing import Optional
import traceback


def _log_debug_error(operation: str, error: Exception) -> None:
    """Log tempfile errors for debugging.

    Args:
        operation: Description of operation that failed
        error: Exception that occurred
    """
    try:
        debug_log = Path.home() / '.config/kitty/smart_tabs_tempfile_debug.log'
        debug_log.parent.mkdir(parents=True, exist_ok=True)
        with open(debug_log, 'a') as f:
            f.write(f"\n{operation}: {error}\n")
            f.write(traceback.format_exc())
    except Exception:
        # Don't fail if logging fails
        pass


def get_temp_dir() -> Path:
    """Get secure temporary directory for Smart Tabs.

    Uses XDG_RUNTIME_DIR if available, falls back to ~/.cache/kitty-smart-tabs.
    Creates directory with mode 700 if it doesn't exist.

    Returns:
        Path to temp directory.
    """
    # Try XDG_RUNTIME_DIR first (more secure, cleaned on logout)
    xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
    if xdg_runtime:
        temp_dir = Path(xdg_runtime) / 'kitty-smart-tabs'
    else:
        # Fallback to user cache directory
        temp_dir = Path.home() / '.cache' / 'kitty-smart-tabs'

    # Create with restrictive permissions if doesn't exist
    if not temp_dir.exists():
        temp_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    else:
        # Ensure correct permissions on existing directory
        temp_dir.chmod(0o700)

    return temp_dir


def get_cwd_file_path(tab_id: int) -> Path:
    """Get path to CWD temp file for a tab.

    Args:
        tab_id: Tab ID (must be positive integer).

    Returns:
        Path to temp file.

    Raises:
        ValueError: If tab_id is invalid.
    """
    if not isinstance(tab_id, int) or tab_id <= 0:
        raise ValueError(f"Invalid tab_id: {tab_id}")

    return get_temp_dir() / f'tab_{tab_id}_cwd'


def write_cwd_atomic(tab_id: int, cwd: str) -> None:
    """Atomically write CWD to temp file with secure permissions.

    Args:
        tab_id: Tab ID.
        cwd: Current working directory path.

    Raises:
        ValueError: If tab_id or cwd is invalid.
    """
    if not isinstance(tab_id, int) or tab_id <= 0:
        raise ValueError(f"Invalid tab_id: {tab_id}")

    if not cwd or not isinstance(cwd, str):
        raise ValueError("CWD must be non-empty string")

    # Validate cwd is absolute path
    if not cwd.startswith('/'):
        raise ValueError(f"CWD must be absolute path: {cwd}")

    # Reject path traversal attempts
    if '/..' in cwd or cwd.startswith('..'):
        raise ValueError(f"Path traversal not allowed: {cwd}")

    # Limit length to prevent abuse
    if len(cwd) > 4096:
        raise ValueError("CWD path too long")

    target_path = get_cwd_file_path(tab_id)

    # Write to temp file, then atomic rename
    # This prevents race conditions from partial reads
    temp_fd, temp_path = tempfile.mkstemp(
        dir=get_temp_dir(),
        prefix=f'tab_{tab_id}_',
        suffix='.tmp'
    )

    try:
        # Write content
        os.write(temp_fd, cwd.encode('utf-8'))
        os.close(temp_fd)

        # Set restrictive permissions
        os.chmod(temp_path, 0o600)

        # Atomic rename
        os.rename(temp_path, target_path)
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise


def read_cwd_safe(tab_id: int) -> Optional[str]:
    """Safely read CWD from temp file with validation.

    Args:
        tab_id: Tab ID.

    Returns:
        CWD path or None if not found/invalid.
    """
    if not isinstance(tab_id, int) or tab_id <= 0:
        return None

    try:
        cwd_file = get_cwd_file_path(tab_id)

        if not cwd_file.exists():
            return None

        # Verify file ownership for security
        stat = cwd_file.stat()
        if stat.st_uid != os.getuid():
            # File owned by different user - potential attack
            return None

        # Verify permissions (should be 600)
        if stat.st_mode & 0o077:
            # File is readable by group/others - insecure
            return None

        # Read content
        cwd = cwd_file.read_text().strip()

        # Validate content
        if not cwd or not cwd.startswith('/'):
            return None

        if len(cwd) > 4096:
            return None

        return cwd

    except Exception as e:
        _log_debug_error(f"read_cwd_safe(tab_id={tab_id})", e)
        return None


def cleanup_temp_files() -> None:
    """Clean up all temp files created by Smart Tabs."""
    try:
        temp_dir = get_temp_dir()
        if temp_dir.exists():
            for file in temp_dir.glob('tab_*_cwd'):
                try:
                    file.unlink()
                except Exception as e:
                    _log_debug_error(f"cleanup_temp_files unlink {file}", e)
    except Exception as e:
        _log_debug_error("cleanup_temp_files", e)

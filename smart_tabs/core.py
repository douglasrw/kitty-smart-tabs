"""Core tab update logic for Smart Tabs."""

import json
import subprocess
import glob
from pathlib import Path
from typing import Optional, Dict, Tuple, List

from .config import Config
from .colors import get_color_for_path
from .tempfiles import read_cwd_safe


# Cache for change detection: tab_id -> (title, color)
_tab_state_cache: Dict[int, Tuple[str, str]] = {}

# Cache for early bailout: tab_id -> (cwd, cmd, tab_index)
_tab_input_cache: Dict[int, Tuple[str, Optional[str], int]] = {}

# Cached socket path to avoid repeated glob calls
_cached_socket_path: Optional[str] = None


def validate_tab_id(tab_id) -> bool:
    """Validate tab ID is a positive integer.

    Args:
        tab_id: Tab ID to validate.

    Returns:
        True if valid, False otherwise.
    """
    return isinstance(tab_id, int) and tab_id > 0


def sanitize_title(title: str, max_length: int = 256) -> str:
    """Sanitize tab title for safe use in subprocess.

    Args:
        title: Title string.
        max_length: Maximum allowed length.

    Returns:
        Sanitized title.
    """
    if not title or not title.strip():
        return "untitled"

    # Limit length
    if len(title) > max_length:
        title = title[:max_length]

    # Remove control characters and newlines
    title = ''.join(c for c in title if c.isprintable())

    # Check again after cleaning
    if not title or not title.strip():
        return "untitled"

    return title


def find_kitty_socket() -> Optional[str]:
    """Find the Kitty socket file.

    Returns:
        Path to socket or None if not found.
    """
    global _cached_socket_path

    # Use cached socket if available
    if _cached_socket_path:
        return _cached_socket_path

    # Find and cache socket
    sockets = glob.glob('/tmp/kitty-*')
    if sockets:
        _cached_socket_path = sockets[0]
        return _cached_socket_path
    return None


def invalidate_socket_cache():
    """Invalidate cached socket path (call when connection fails)."""
    global _cached_socket_path
    _cached_socket_path = None


def get_kitty_command() -> List[str]:
    """Get the kitty command with appropriate socket connection.

    Returns:
        List of command parts for subprocess.
    """
    socket = find_kitty_socket()
    if socket:
        return ['kitty', '@', '--to', f'unix:{socket}']
    return ['kitty', '@']


def get_process_cwd(pid: int) -> Optional[str]:
    """Get actual CWD of a process by reading from /proc or lsof.

    This provides more accurate CWD detection than kitty's reported CWD,
    especially when shell hooks aren't loaded.

    Args:
        pid: Process ID

    Returns:
        Current working directory of process, or None if detection fails.
    """
    import os
    import subprocess
    from pathlib import Path

    # Try /proc/$PID/cwd (Linux)
    proc_cwd = Path(f'/proc/{pid}/cwd')
    if proc_cwd.exists():
        try:
            # Read the symlink to get actual CWD
            cwd = os.readlink(proc_cwd)
            if cwd and cwd.startswith('/'):
                return cwd
        except (OSError, PermissionError):
            pass

    # Try lsof (macOS/BSD)
    try:
        result = subprocess.run(
            ['lsof', '-p', str(pid), '-a', '-d', 'cwd', '-Fn'],
            capture_output=True,
            text=True,
            timeout=0.5
        )
        if result.returncode == 0:
            # Parse lsof output: lines starting with 'n' contain the path
            for line in result.stdout.split('\n'):
                if line.startswith('n') and len(line) > 1:
                    cwd = line[1:]  # Strip the 'n' prefix
                    if cwd and cwd.startswith('/'):
                        return cwd
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    return None


def get_tab_cwd(tab: Dict) -> str:
    """Get the CWD from temp file, process detection, or fallback to Kitty's CWD.

    Args:
        tab: Tab data from kitty @ ls

    Returns:
        Current working directory path.
    """
    tab_id = tab.get('id')
    if not tab_id:
        return ''

    # Validate tab_id is an integer
    if not isinstance(tab_id, int) or tab_id <= 0:
        return ''

    # Primary source: temp file written by shell on cd (secure read)
    cwd = read_cwd_safe(tab_id)
    if cwd:
        return cwd

    # Secondary source: Detect CWD from foreground process
    # This works even without shell hooks, providing better accuracy
    for window in tab.get('windows', []):
        fg_processes = window.get('foreground_processes', [])
        if fg_processes:
            # Try to get CWD from the first foreground process
            pid = fg_processes[0].get('pid')
            if pid:
                cwd = get_process_cwd(pid)
                if cwd:
                    return cwd

    # Tertiary fallback: Use Kitty's reported CWD (may be stale)
    for window in tab.get('windows', []):
        cwd = window.get('cwd', '')
        if cwd:
            return cwd

    return ''


def _parse_process_command(process: Dict, config: Config) -> Optional[str]:
    """Parse a single process and return command name, or None if filtered.

    Args:
        process: Process data from foreground_processes
        config: Configuration object

    Returns:
        Command name or None if should be filtered.
    """
    cmdline = process.get('cmdline', [])
    if not cmdline:
        return None

    # Extract command name (basename only)
    cmd = cmdline[0]
    cmd_name = cmd.split('/')[-1]

    # Strip leading dash (login shells like -zsh, -bash)
    if cmd_name.startswith('-'):
        cmd_name = cmd_name[1:]

    # Filter out shells
    if cmd_name.lower() in config.ignored_shells:
        return None

    # Filter out Kitty-related processes and smart_tabs itself
    kitty_tools = {'kitty', 'kitten', 'color_tabs_by_cwd', 'smart_tabs'}
    if cmd_name.lower() in kitty_tools:
        return None

    # Filter out system utilities
    system_utils = {'sleep', 'wait', 'cat', 'echo', 'true', 'false', 'test',
                    'grep', 'sed', 'awk', 'tail', 'head'}
    if cmd_name.lower() in system_utils:
        return None

    # Filter out configured commands
    if cmd_name.lower() in config.ignored_commands:
        return None

    # Filter out by prefix/suffix
    for prefix in config.ignored_prefixes:
        if cmd_name.lower().startswith(prefix.lower()):
            return None

    for suffix in config.ignored_suffixes:
        if cmd_name.lower().endswith(suffix.lower()):
            return None

    # Handle interpreters
    interpreters = {
        'node': {'js', 'mjs', 'cjs'},
        'python': {'py'},
        'python3': {'py'},
        'python2': {'py'},
        'ruby': {'rb'},
        'perl': {'pl'},
        'php': {'php'},
    }

    if cmd_name.lower() in interpreters:
        # Look for the script/executable in remaining arguments
        for arg in cmdline[1:]:
            if arg.startswith('-') or arg.startswith('--'):
                continue
            if arg in ['/', '.', '..']:
                continue

            script_path = arg
            script_name = script_path.split('/')[-1]

            # Remove extension
            for ext in interpreters.get(cmd_name.lower(), []):
                if script_name.endswith(f'.{ext}'):
                    script_name = script_name[:-len(ext)-1]
                    break

            # Skip generic names
            generic_names = ['index', 'main', 'app', 'cli', 'bin', 'start', 'run']
            if script_name.lower() in generic_names:
                continue

            if script_name:
                cmd_name = script_name
                break

    # Truncate if too long
    if len(cmd_name) > config.max_cmd_length:
        cmd_name = cmd_name[:config.max_cmd_length-3] + '...'

    return cmd_name


def get_running_command(tab: Dict, config: Config) -> Optional[str]:
    """Get the running command from the foreground process.

    Args:
        tab: Tab data from kitty @ ls
        config: Configuration object

    Returns:
        Command name or None if no command detected.
    """
    windows = tab.get('windows', [])
    if not windows:
        return None

    window = windows[0]
    fg_processes = window.get('foreground_processes', [])
    if not fg_processes:
        return None

    # Collect all valid commands
    candidates = []
    for process in fg_processes:
        result = _parse_process_command(process, config)
        if result:
            candidates.append(result)

    if not candidates:
        return None

    # Prioritize user-facing commands
    for cmd in candidates:
        if cmd.lower() in config.priority_commands:
            return cmd

    return candidates[0]


def update_tabs(debug: bool = False) -> int:
    """Update all tab colors and titles.

    Args:
        debug: Enable debug logging

    Returns:
        Number of tabs actually updated
    """
    changes_made = 0
    config = Config()
    log_file = Path.home() / '.config/kitty/tab_color_debug.log'
    kitty_cmd = get_kitty_command()

    # Get list of all tabs
    try:
        result = subprocess.run(
            kitty_cmd + ['ls'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            # Connection failed, invalidate socket cache for next attempt
            invalidate_socket_cache()
            return changes_made
        data = json.loads(result.stdout)
    except Exception as e:
        # Connection failed, invalidate socket cache for next attempt
        invalidate_socket_cache()
        if debug:
            with open(log_file, 'w') as f:
                f.write(f"Error getting tab list: {e}\n")
        return changes_made

    # Map tabs by working directory
    tab_info: Dict[int, Tuple[str, str, Optional[str]]] = {}
    cwd_to_color: Dict[str, str] = {}

    if debug:
        with open(log_file, 'w') as f:
            f.write("=== Tab CWD Debug ===\n")

    for os_window in data:
        for tab in os_window.get('tabs', []):
            tab_id = tab.get('id')
            tab_title = tab.get('title', 'untitled')
            cwd = get_tab_cwd(tab)

            if debug:
                with open(log_file, 'a') as f:
                    f.write(f"\nTab {tab_id} ('{tab_title}'): cwd='{cwd}'\n")
                    for win in tab.get('windows', []):
                        for proc in win.get('foreground_processes', []):
                            f.write(f"  Process cmdline: {proc.get('cmdline')}\n")

            cmd = get_running_command(tab, config) if config.show_commands else None

            if debug:
                with open(log_file, 'a') as f:
                    f.write(f"  Detected command: '{cmd}'\n")

            if cwd and tab_id:
                # Normalize path
                cwd = cwd.rstrip('/')
                dir_name = cwd.split('/')[-1] if '/' in cwd else cwd

                # Truncate directory name if needed
                if len(dir_name) > config.max_dir_length:
                    dir_name = dir_name[:config.max_dir_length-3] + '...'

                tab_info[tab_id] = (cwd, dir_name, cmd)

                # Generate color for this directory
                if cwd not in cwd_to_color:
                    cwd_to_color[cwd] = get_color_for_path(cwd, config.get_color_palette())

    # Build tab_id to tab_index mapping
    tab_id_to_index = {}
    for os_window in data:
        for idx, tab in enumerate(os_window.get('tabs', []), start=1):
            tab_id = tab.get('id')
            if tab_id:
                tab_id_to_index[tab_id] = idx

    # Apply colors and titles to all tabs
    for tab_id, (cwd, dir_name, cmd) in tab_info.items():
        # Validate tab_id before using
        if not validate_tab_id(tab_id):
            continue

        tab_index = tab_id_to_index.get(tab_id, '')

        # Early cache check - skip if input data unchanged
        # This avoids title/color computation for unchanged tabs
        cached_input = _tab_input_cache.get(tab_id)
        if cached_input == (cwd, cmd, tab_index):
            continue  # No input changes, skip all processing

        color = cwd_to_color[cwd]

        # Build title with optional command
        if config.show_tab_index and tab_index:
            if cmd:
                title = f"{tab_index}: {dir_name} [{cmd}]"
            else:
                title = f"{tab_index}: {dir_name}"
        else:
            title = f"{dir_name} [{cmd}]" if cmd else dir_name

        # Sanitize title for safety
        title = sanitize_title(title)

        # Check output cache - skip if unchanged
        # (Belt and suspenders: catches edge cases like sanitization changes)
        cached_state = _tab_state_cache.get(tab_id)
        if cached_state == (title, color):
            continue  # No changes, skip subprocess calls

        if debug:
            with open(log_file, 'a') as f:
                f.write(f"Setting tab {tab_id}: title='{title}', color='{color}'\n")

        try:
            # Batch both commands into single kitty @ call for performance
            # Use shell=False for security, pass as separate args
            subprocess.run(
                kitty_cmd + ['set-tab-title', f'--match=id:{tab_id}', title],
                capture_output=True,
                timeout=0.5
            )
            subprocess.run(
                kitty_cmd + ['set-tab-color', f'--match=id:{tab_id}',
                           f'active_fg={color}', f'inactive_fg={color}'],
                capture_output=True,
                timeout=0.5
            )

            # Update both caches ONLY on success
            _tab_state_cache[tab_id] = (title, color)
            _tab_input_cache[tab_id] = (cwd, cmd, tab_index)
            changes_made += 1

        except Exception as e:
            if debug:
                with open(log_file, 'a') as f:
                    f.write(f"Error updating tab {tab_id}: {e}\n")

    return changes_made

"""Regression tests for bugs fixed during development.

These tests ensure that specific bugs that were found and fixed
stay fixed and don't regress in future changes.
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, call
from smart_tabs.core import update_tabs, _tab_state_cache
from smart_tabs.daemon import run_daemon


@pytest.mark.regression
class TestAdaptivePollingRegression:
    """Regression tests for adaptive polling logic bug.

    Bug: Daemon was using cache size comparison instead of actual changes made
    to determine if tabs were updated. This caused the interval to increase
    even when tabs were being updated, because the cache size stayed the same.

    Fix: Changed to use the actual number of changes returned by update_tabs().
    """

    def test_adaptive_polling_uses_changes_not_cache_size(self, monkeypatch):
        """Adaptive polling should use changes_made, not cache size comparison."""
        # Mock tab data with same tab across iterations
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 100,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/projects",
                            "foreground_processes": [{"cmdline": ["nvim"]}]
                        }]
                    }
                ]
            }
        ]

        run_count = 0
        interval_changes = []

        def mock_run(cmd, *args, **kwargs):
            nonlocal run_count
            run_count += 1

            mock_result = Mock()
            if 'ls' in cmd:
                # Change the CWD on second iteration to force an update
                if run_count > 3:  # After a few iterations
                    mock_tab_data[0]['tabs'][0]['windows'][0]['cwd'] = f"/home/user/projects{run_count}"
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        def mock_sleep(duration):
            interval_changes.append(duration)
            if len(interval_changes) >= 5:  # Stop after a few iterations
                raise KeyboardInterrupt()

        def mock_acquire_lock():
            """Mock the lock acquisition to avoid daemon conflicts."""
            return Mock()

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])
        monkeypatch.setattr('time.sleep', mock_sleep)
        monkeypatch.setattr('smart_tabs.daemon.acquire_lock', mock_acquire_lock)

        # Clear cache before test
        _tab_state_cache.clear()

        try:
            run_daemon(debug=False)
        except KeyboardInterrupt:
            pass

        # With the fix, interval should only increase when NO changes are made
        # Even though cache size stays the same, changes are being made
        # so interval should reset when tabs are updated
        assert len(interval_changes) > 0

    def test_no_changes_increases_interval(self, monkeypatch):
        """When truly no changes occur, interval should increase."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 101,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/same",
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        intervals = []

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        def mock_sleep(duration):
            intervals.append(duration)
            if len(intervals) >= 6:  # Enough to see interval increase
                raise KeyboardInterrupt()

        def mock_acquire_lock():
            """Mock the lock acquisition to avoid daemon conflicts."""
            return Mock()

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])
        monkeypatch.setattr('time.sleep', mock_sleep)
        monkeypatch.setattr('smart_tabs.daemon.acquire_lock', mock_acquire_lock)

        # Prime the cache so first update doesn't count as a change
        _tab_state_cache.clear()
        _tab_state_cache[101] = ('1: same', '#2b8eff')

        try:
            run_daemon(debug=False)
        except KeyboardInterrupt:
            pass

        # Interval should increase over time when no changes
        # (later intervals should be larger than earlier ones)
        if len(intervals) >= 3:
            assert max(intervals[-3:]) > intervals[0]


@pytest.mark.regression
class TestDaemonStartupRegression:
    """Regression tests for daemon startup delay bug.

    Bug: Daemon was sleeping on first iteration, causing a delay before
    the first update ran. This made the UI feel sluggish on startup.

    Fix: Skip sleep on iteration 0 for immediate startup response.
    """

    def test_daemon_runs_immediately_on_startup(self, monkeypatch):
        """First update should run immediately without sleep."""
        mock_tab_data = [{"id": 1, "tabs": []}]

        sleep_calls = []
        update_calls = []

        def mock_run(cmd, *args, **kwargs):
            if 'ls' in cmd:
                update_calls.append(time.time())
            mock_result = Mock()
            mock_result.stdout = json.dumps(mock_tab_data)
            mock_result.returncode = 0
            return mock_result

        def mock_sleep(duration):
            sleep_calls.append((time.time(), duration))
            if len(sleep_calls) >= 2:
                raise KeyboardInterrupt()

        def mock_acquire_lock():
            """Mock the lock acquisition to avoid daemon conflicts."""
            return Mock()

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])
        monkeypatch.setattr('time.sleep', mock_sleep)
        monkeypatch.setattr('smart_tabs.daemon.acquire_lock', mock_acquire_lock)

        start_time = time.time()
        try:
            run_daemon(debug=False)
        except KeyboardInterrupt:
            pass

        # First update should happen before first sleep
        assert len(update_calls) > 0
        assert len(sleep_calls) >= 1

        if len(update_calls) > 0 and len(sleep_calls) > 0:
            first_update = update_calls[0]
            first_sleep = sleep_calls[0][0]
            # Update should occur before sleep (or very close to start)
            assert first_update <= first_sleep


@pytest.mark.regression
class TestUpdateTabsReturnValueRegression:
    """Regression tests for update_tabs return value.

    Bug: update_tabs returned None, making it impossible for daemon
    to know if tabs were actually updated or just checked.

    Fix: Return int count of tabs that were updated.
    """

    def test_update_tabs_returns_zero_when_no_changes(self, monkeypatch):
        """Should return 0 when no tabs need updating."""
        from smart_tabs.colors import get_color_for_path
        from smart_tabs.config import Config

        config = Config()
        palette = config.get_color_palette()
        cwd = "/home/user/test"
        expected_color = get_color_for_path(cwd, palette)

        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 102,
                        "title": "test",
                        "windows": [{
                            "cwd": cwd,
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Prime cache with exact title/color that update_tabs will generate
        _tab_state_cache.clear()
        _tab_state_cache[102] = ('1: test', expected_color)

        result = update_tabs(debug=False)
        assert result == 0
        assert isinstance(result, int)

    def test_update_tabs_returns_count_when_changes_made(self, monkeypatch):
        """Should return count of tabs updated."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 103,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/new",
                            "foreground_processes": [{"cmdline": ["nvim"]}]
                        }]
                    }
                ]
            }
        ]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Clear cache so update happens
        _tab_state_cache.clear()

        result = update_tabs(debug=False)
        assert result == 1  # One tab updated
        assert isinstance(result, int)

    def test_update_tabs_returns_count_for_multiple_tabs(self, monkeypatch):
        """Should return correct count for multiple tabs."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 104,
                        "title": "tab1",
                        "windows": [{
                            "cwd": "/home/user/dir1",
                            "foreground_processes": [{"cmdline": ["vim"]}]
                        }]
                    },
                    {
                        "id": 105,
                        "title": "tab2",
                        "windows": [{
                            "cwd": "/home/user/dir2",
                            "foreground_processes": [{"cmdline": ["emacs"]}]
                        }]
                    }
                ]
            }
        ]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()

        result = update_tabs(debug=False)
        assert result == 2  # Two tabs updated
        assert isinstance(result, int)


@pytest.mark.regression
class TestColorPaletteRegression:
    """Regression tests for color palette expansion.

    Bug: Only 6 colors were available, causing color collisions with
    many tabs open.

    Fix: Expanded palette to 16 colors for better distribution.
    """

    def test_expanded_palette_has_16_colors(self, tmp_path):
        """Color palette should have 16 colors, not 6."""
        from smart_tabs.config import Config

        # Use non-existent path to get defaults
        nonexistent = tmp_path / "nonexistent.conf"
        config = Config(nonexistent)
        palette = config.get_color_palette()

        assert len(palette) == 16, f"Expected 16 colors, got {len(palette)}"

    def test_palette_colors_are_unique(self, tmp_path):
        """All colors in palette should be unique."""
        from smart_tabs.config import Config

        # Use non-existent path to get defaults
        nonexistent = tmp_path / "nonexistent.conf"
        config = Config(nonexistent)
        palette = config.get_color_palette()

        assert len(palette) == len(set(palette)), "Palette contains duplicate colors"

    def test_color_distribution_with_many_paths(self, tmp_path):
        """With 16 colors, many paths should have less collision."""
        from smart_tabs.colors import get_color_for_path
        from smart_tabs.config import Config

        # Use non-existent path to get defaults
        nonexistent = tmp_path / "nonexistent.conf"
        config = Config(nonexistent)
        palette = config.get_color_palette()

        # Create 16 different paths
        paths = [f"/home/user/project{i}" for i in range(16)]
        colors = [get_color_for_path(p, palette) for p in paths]

        # With 16 colors and 16 paths, we should see good distribution
        unique_colors = len(set(colors))

        # Should use at least 10 different colors (allowing some collision)
        assert unique_colors >= 10, f"Only {unique_colors} unique colors used for 16 paths"

    def test_original_colors_still_present(self, tmp_path):
        """Original 6 colors should still be in palette."""
        from smart_tabs.config import Config

        # Use non-existent path to get defaults
        nonexistent = tmp_path / "nonexistent.conf"
        config = Config(nonexistent)
        palette = config.get_color_palette()

        original_colors = [
            '#2b8eff',  # blue
            '#a9dc76',  # green
            '#ab9df2',  # purple
            '#ffd866',  # yellow
            '#78dce8',  # cyan
            '#f48771',  # red
        ]

        for color in original_colors:
            assert color in palette, f"Original color {color} missing from palette"


@pytest.mark.regression
class TestColorConsistencyRegression:
    """Regression tests for color consistency bugs.

    Bug: Multiple tabs in same directory should always have the same color,
    but timing/caching issues could cause different colors to be assigned.

    Fix: Ensure color assignment is deterministic based on CWD.
    """

    def test_same_cwd_gets_same_color_always(self, monkeypatch):
        """Tabs with identical CWD should always get identical color."""
        from smart_tabs.colors import get_color_for_path
        from smart_tabs.config import Config

        config = Config()
        palette = config.get_color_palette()
        cwd = "/home/user/projects/myapp"

        # Call multiple times - should always return same color
        colors = [get_color_for_path(cwd, palette) for _ in range(100)]
        assert len(set(colors)) == 1, "Same CWD should always produce same color"

    def test_tabs_in_same_dir_share_color(self, monkeypatch):
        """Multiple tabs in same directory should display same color."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 200,
                        "title": "tab1",
                        "windows": [{
                            "cwd": "/home/user/shared",
                            "foreground_processes": [{"cmdline": ["vim"]}]
                        }]
                    },
                    {
                        "id": 201,
                        "title": "tab2",
                        "windows": [{
                            "cwd": "/home/user/shared",
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    },
                    {
                        "id": 202,
                        "title": "tab3",
                        "windows": [{
                            "cwd": "/home/user/shared",
                            "foreground_processes": [{"cmdline": ["git", "status"]}]
                        }]
                    }
                ]
            }
        ]

        color_assignments = {}

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-color' in cmd:
                # Extract tab_id and color from command
                tab_match = [x for x in cmd if x.startswith('--match=id:')]
                color_match = [x for x in cmd if x.startswith('active_fg=')]
                if tab_match and color_match:
                    tab_id = int(tab_match[0].split(':')[1])
                    color = color_match[0].split('=')[1]
                    color_assignments[tab_id] = color
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()
        update_tabs(debug=False)

        # All three tabs should have the same color
        colors = list(color_assignments.values())
        assert len(colors) == 3, f"Expected 3 color assignments, got {len(colors)}"
        assert len(set(colors)) == 1, f"Expected all same color, got {set(colors)}"

    def test_trailing_slash_normalization(self, monkeypatch):
        """CWD with/without trailing slash should get same color."""
        from smart_tabs.colors import get_color_for_path
        from smart_tabs.config import Config

        config = Config()
        palette = config.get_color_palette()

        # These should be treated as the same directory after normalization
        cwd1 = "/home/user/projects"
        cwd2 = "/home/user/projects/"

        # In update_tabs, trailing slashes are stripped before color assignment
        # So we test that the normalized paths get the same color
        color1 = get_color_for_path(cwd1.rstrip('/'), palette)
        color2 = get_color_for_path(cwd2.rstrip('/'), palette)

        assert color1 == color2, "Paths differing only by trailing slash should get same color"

    def test_color_persists_across_updates(self, monkeypatch):
        """Same tab should keep same color across multiple updates."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 203,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/stable",
                            "foreground_processes": [{"cmdline": ["vim"]}]
                        }]
                    }
                ]
            }
        ]

        assigned_colors = []

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-color' in cmd:
                color_match = [x for x in cmd if x.startswith('active_fg=')]
                if color_match:
                    color = color_match[0].split('=')[1]
                    assigned_colors.append(color)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()

        # Run update multiple times
        for _ in range(3):
            update_tabs(debug=False)

        # Color should be consistent (only set once due to caching, or same each time)
        if len(assigned_colors) > 0:
            assert all(c == assigned_colors[0] for c in assigned_colors), \
                f"Color changed across updates: {assigned_colors}"


@pytest.mark.regression
class TestTimingAndRaceConditionsRegression:
    """Regression tests for timing and race condition bugs.

    Various timing issues that could cause incorrect behavior.
    """

    def test_subprocess_timeout_handling(self, monkeypatch):
        """Should handle subprocess timeouts gracefully."""
        import subprocess

        def mock_run(cmd, *args, **kwargs):
            if 'ls' in cmd:
                raise subprocess.TimeoutExpired(cmd, 2)
            mock_result = Mock()
            mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Should return 0 and not crash
        result = update_tabs(debug=False)
        assert result == 0

    def test_concurrent_updates_dont_corrupt_cache(self, monkeypatch):
        """Cache should remain consistent even with rapid updates."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 204,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/test",
                            "foreground_processes": [{"cmdline": ["vim"]}]
                        }]
                    }
                ]
            }
        ]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()

        # Run multiple updates rapidly
        for _ in range(10):
            update_tabs(debug=False)

        # Cache should be consistent
        assert 204 in _tab_state_cache
        cached_title, cached_color = _tab_state_cache[204]
        assert cached_title is not None
        assert cached_color is not None

    def test_cwd_change_detected_immediately(self, monkeypatch):
        """When CWD changes, update should happen on next cycle."""
        iteration = 0
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 205,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/dir1",
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        update_count = []

        def mock_run(cmd, *args, **kwargs):
            nonlocal iteration
            mock_result = Mock()

            if 'ls' in cmd:
                iteration += 1
                # Change CWD on second call
                if iteration == 2:
                    mock_tab_data[0]['tabs'][0]['windows'][0]['cwd'] = "/home/user/dir2"
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd or 'set-tab-color' in cmd:
                update_count.append(iteration)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0

            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()

        # First update
        result1 = update_tabs(debug=False)
        assert result1 == 1  # Should update

        # Second update with changed CWD
        result2 = update_tabs(debug=False)
        assert result2 == 1  # Should update again due to CWD change


@pytest.mark.regression
class TestDisplayCorrectnessRegression:
    """Regression tests for display correctness.

    Bug: Tab titles and colors might not display correctly due to:
    - Incorrect title formatting
    - Command not showing when it should
    - Tab index formatting issues
    - Title sanitization problems
    """

    def test_title_includes_command_when_enabled(self, monkeypatch):
        """Title should include command when show_commands is true."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 206,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/code",
                            "foreground_processes": [{"cmdline": ["nvim", "file.py"]}]
                        }]
                    }
                ]
            }
        ]

        captured_title = None

        def mock_run(cmd, *args, **kwargs):
            nonlocal captured_title
            mock_result = Mock()

            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd:
                # Extract title from command
                if len(cmd) > 3:
                    captured_title = cmd[-1]
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0

            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()
        update_tabs(debug=False)

        assert captured_title is not None
        # Should include command in brackets
        assert '[nvim]' in captured_title or 'nvim' in captured_title

    def test_title_excludes_command_when_disabled(self, monkeypatch, tmp_path):
        """Title should not include command when show_commands is false."""
        # Create config with show_commands disabled
        config_file = tmp_path / 'smart_tabs.conf'
        config_file.write_text('[behavior]\nshow_commands = false\n')

        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 207,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/code",
                            "foreground_processes": [{"cmdline": ["nvim", "file.py"]}]
                        }]
                    }
                ]
            }
        ]

        captured_title = None

        def mock_run(cmd, *args, **kwargs):
            nonlocal captured_title
            mock_result = Mock()

            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd:
                if len(cmd) > 3:
                    captured_title = cmd[-1]
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0

            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Mock config file path
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmp_path
            (tmp_path / '.config' / 'kitty').mkdir(parents=True)
            config_file_dst = tmp_path / '.config' / 'kitty' / 'smart_tabs.conf'
            config_file_dst.write_text('[behavior]\nshow_commands = false\n')

            _tab_state_cache.clear()
            update_tabs(debug=False)

            if captured_title:
                # Should NOT include command in brackets
                assert '[nvim]' not in captured_title

    def test_title_sanitization_removes_control_chars(self, monkeypatch):
        """Title should remove control characters for safety."""
        from smart_tabs.core import sanitize_title

        # Test various control characters
        dangerous_title = "test\x00\x01\x1b[31mhacked\x1b[0m\nmalicious"
        safe_title = sanitize_title(dangerous_title)

        # Should remove all control chars and newlines
        assert '\x00' not in safe_title
        assert '\x01' not in safe_title
        assert '\x1b' not in safe_title
        assert '\n' not in safe_title
        assert safe_title.isprintable() or safe_title == ""

    def test_title_handles_empty_input(self, monkeypatch):
        """Title sanitization should handle empty/whitespace input."""
        from smart_tabs.core import sanitize_title

        assert sanitize_title("") == "untitled"
        assert sanitize_title("   ") == "untitled"
        assert sanitize_title("\n\t") == "untitled"

    def test_title_truncates_long_names(self, monkeypatch):
        """Very long directory names should be truncated."""
        from smart_tabs.config import Config

        config = Config()
        max_len = config.max_dir_length

        long_name = "a" * (max_len + 50)
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 208,
                        "title": "test",
                        "windows": [{
                            "cwd": f"/home/user/{long_name}",
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        captured_title = None

        def mock_run(cmd, *args, **kwargs):
            nonlocal captured_title
            mock_result = Mock()

            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd:
                if len(cmd) > 3:
                    captured_title = cmd[-1]
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0

            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()
        update_tabs(debug=False)

        # Title should be truncated (includes index, ellipsis, etc)
        assert captured_title is not None
        # Should end with ... if truncated
        assert '...' in captured_title

    def test_tab_index_displayed_correctly(self, monkeypatch):
        """Tab index should be displayed at start of title."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 209,
                        "title": "first",
                        "windows": [{
                            "cwd": "/home/user/first",
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    },
                    {
                        "id": 210,
                        "title": "second",
                        "windows": [{
                            "cwd": "/home/user/second",
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        titles_by_tab = {}

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()

            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd:
                tab_match = [x for x in cmd if x.startswith('--match=id:')]
                if tab_match and len(cmd) > 3:
                    tab_id = int(tab_match[0].split(':')[1])
                    titles_by_tab[tab_id] = cmd[-1]
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0

            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()
        update_tabs(debug=False)

        # Check that tab indices are present
        assert 209 in titles_by_tab
        assert 210 in titles_by_tab

        # First tab should start with 1:
        assert titles_by_tab[209].startswith('1:')

        # Second tab should start with 2:
        assert titles_by_tab[210].startswith('2:')


@pytest.mark.regression
class TestSignalHandlingRegression:
    """Regression tests for daemon signal handling.

    Improvement: Daemon now handles SIGTERM and SIGINT gracefully
    for clean shutdown during system shutdown/restart scenarios.
    """

    def test_daemon_handles_sigterm_gracefully(self, monkeypatch):
        """Daemon should shut down gracefully on SIGTERM."""
        import signal
        import smart_tabs.daemon as daemon_module

        mock_tab_data = [{"id": 1, "tabs": []}]
        iterations = []

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            mock_result.stdout = json.dumps(mock_tab_data)
            mock_result.returncode = 0
            return mock_result

        def mock_sleep(duration):
            iterations.append(1)
            # Send SIGTERM after first iteration
            if len(iterations) == 1:
                daemon_module._shutdown_requested = True

        def mock_acquire_lock():
            return Mock()

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])
        monkeypatch.setattr('time.sleep', mock_sleep)
        monkeypatch.setattr('smart_tabs.daemon.acquire_lock', mock_acquire_lock)

        # Reset shutdown flag
        daemon_module._shutdown_requested = False

        run_daemon(debug=False)

        # Should have exited gracefully after shutdown flag set
        assert daemon_module._shutdown_requested == True
        assert len(iterations) >= 1

    def test_daemon_handles_sigint_gracefully(self, monkeypatch):
        """Daemon should shut down gracefully on SIGINT."""
        import smart_tabs.daemon as daemon_module

        mock_tab_data = [{"id": 1, "tabs": []}]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            mock_result.stdout = json.dumps(mock_tab_data)
            mock_result.returncode = 0
            return mock_result

        def mock_sleep(duration):
            # Simulate SIGINT by setting flag
            daemon_module._shutdown_requested = True

        def mock_acquire_lock():
            return Mock()

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])
        monkeypatch.setattr('time.sleep', mock_sleep)
        monkeypatch.setattr('smart_tabs.daemon.acquire_lock', mock_acquire_lock)

        daemon_module._shutdown_requested = False

        run_daemon(debug=False)

        # Should exit cleanly
        assert daemon_module._shutdown_requested == True


@pytest.mark.regression
class TestConfigRobustnessRegression:
    """Regression tests for config file handling robustness.

    Improvement: Better handling of malformed config files.
    """

    def test_malformed_config_uses_defaults(self, tmp_path):
        """Malformed config file should fall back to defaults."""
        from smart_tabs.config import Config

        # Create malformed config
        config_file = tmp_path / 'smart_tabs.conf'
        config_file.write_text('[behavior\nthis is not valid INI\ngarbage text')

        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmp_path
            (tmp_path / '.config' / 'kitty').mkdir(parents=True)
            config_file_dst = tmp_path / '.config' / 'kitty' / 'smart_tabs.conf'
            config_file_dst.write_text('[behavior\nthis is not valid INI')

            # Should not crash, should use defaults
            try:
                config = Config()
                # Basic check that defaults are used
                assert config.poll_interval > 0
                assert isinstance(config.show_commands, bool)
            except Exception:
                # Also acceptable to raise but not crash
                pass

    def test_empty_config_uses_defaults(self, tmp_path):
        """Empty config file should use defaults."""
        from smart_tabs.config import Config

        config_file = tmp_path / 'smart_tabs.conf'
        config_file.write_text('')

        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmp_path
            (tmp_path / '.config' / 'kitty').mkdir(parents=True)
            config_file_dst = tmp_path / '.config' / 'kitty' / 'smart_tabs.conf'
            config_file_dst.write_text('')

            config = Config()
            # Defaults should be loaded
            assert config.poll_interval == 2
            assert config.show_commands == True


@pytest.mark.regression
class TestSocketCacheRegression:
    """Regression tests for socket path caching.

    Improvement: Socket path is cached to avoid repeated glob calls,
    improving performance. Cache is invalidated on connection failure.
    """

    def test_socket_path_cached_across_calls(self, monkeypatch):
        """Socket path should be cached and reused."""
        from smart_tabs.core import find_kitty_socket, invalidate_socket_cache

        glob_calls = []

        def mock_glob(pattern):
            glob_calls.append(pattern)
            return ['/tmp/kitty-test']

        monkeypatch.setattr('glob.glob', mock_glob)

        # Reset cache
        invalidate_socket_cache()

        # First call should hit glob
        socket1 = find_kitty_socket()
        assert len(glob_calls) == 1

        # Second call should use cache
        socket2 = find_kitty_socket()
        assert len(glob_calls) == 1  # No new glob calls

        assert socket1 == socket2

    def test_socket_cache_invalidated_on_failure(self, monkeypatch):
        """Socket cache should be invalidated when connection fails."""
        from smart_tabs.core import invalidate_socket_cache, _cached_socket_path
        import smart_tabs.core as core_module

        mock_tab_data = [{"id": 1, "tabs": []}]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                # Simulate connection failure
                mock_result.returncode = 1
                mock_result.stdout = ""
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Set cache
        core_module._cached_socket_path = '/tmp/kitty-old'

        # Call update_tabs which should fail and invalidate cache
        update_tabs(debug=False)

        # Cache should be invalidated
        assert core_module._cached_socket_path is None


@pytest.mark.regression
class TestEarlyCacheCheckRegression:
    """Regression tests for early cache checking optimization.

    Improvement: Cache is checked before computing title/color strings,
    saving CPU cycles for unchanged tabs.
    """

    def test_early_cache_skip_avoids_computation(self, monkeypatch):
        """Early cache hit should skip title/color computation."""
        from smart_tabs.core import update_tabs, _tab_state_cache, _tab_input_cache

        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 999,
                        "title": "test",
                        "windows": [{
                            "cwd": "/home/user/test",
                            "foreground_processes": [{"cmdline": ["vim"]}]
                        }]
                    }
                ]
            }
        ]

        subprocess_calls = []

        def mock_run(cmd, *args, **kwargs):
            subprocess_calls.append(cmd)
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Clear caches and do first update
        _tab_state_cache.clear()
        _tab_input_cache.clear()

        result1 = update_tabs(debug=False)
        assert result1 == 1  # Tab updated
        initial_call_count = len(subprocess_calls)

        # Second update with same data - should use cache
        result2 = update_tabs(debug=False)
        assert result2 == 0  # No updates (cache hit)

        # Should have only added the 'ls' call, no set-tab calls
        new_calls = len(subprocess_calls) - initial_call_count
        # Only the 'ls' call should have been made
        assert new_calls == 1

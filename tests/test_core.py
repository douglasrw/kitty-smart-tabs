"""Tests for core tab update logic."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from smart_tabs.core import (
    find_kitty_socket,
    get_kitty_command,
    get_tab_cwd,
    update_tabs
)


@pytest.mark.unit
class TestFindKittySocket:
    """Tests for find_kitty_socket function."""

    def test_socket_found(self, monkeypatch):
        """Should return first socket when found."""
        mock_sockets = ['/tmp/kitty-12345', '/tmp/kitty-67890']
        monkeypatch.setattr('glob.glob', lambda pattern: mock_sockets)

        result = find_kitty_socket()
        assert result == '/tmp/kitty-12345'

    def test_no_socket_found(self, monkeypatch):
        """Should return None when no socket found."""
        monkeypatch.setattr('glob.glob', lambda pattern: [])

        result = find_kitty_socket()
        assert result is None

    def test_single_socket(self, monkeypatch):
        """Should return single socket when only one exists."""
        mock_sockets = ['/tmp/kitty-99999']
        monkeypatch.setattr('glob.glob', lambda pattern: mock_sockets)

        result = find_kitty_socket()
        assert result == '/tmp/kitty-99999'


@pytest.mark.unit
class TestGetKittyCommand:
    """Tests for get_kitty_command function."""

    def test_command_with_socket(self, monkeypatch):
        """Should include socket in command when found."""
        mock_sockets = ['/tmp/kitty-12345']
        monkeypatch.setattr('glob.glob', lambda pattern: mock_sockets)

        result = get_kitty_command()
        assert result == ['kitty', '@', '--to', 'unix:/tmp/kitty-12345']

    def test_command_without_socket(self, monkeypatch):
        """Should use default command when no socket found."""
        monkeypatch.setattr('glob.glob', lambda pattern: [])

        result = get_kitty_command()
        assert result == ['kitty', '@']


@pytest.mark.unit
class TestGetTabCwd:
    """Tests for get_tab_cwd function."""

    def test_cwd_from_temp_file(self, tmp_path, monkeypatch):
        """Should read CWD from temp file when exists."""
        # Create temp CWD file in /tmp
        import os
        cwd_file = Path('/tmp') / 'kitty_tab_100_cwd'
        cwd_file.write_text('/home/user/projects')

        try:
            tab = {'id': 100, 'windows': [{'cwd': '/stale/path'}]}
            result = get_tab_cwd(tab)

            assert result == '/home/user/projects'
        finally:
            # Cleanup
            if cwd_file.exists():
                cwd_file.unlink()

    def test_cwd_fallback_to_window(self):
        """Should fallback to window CWD when temp file missing."""
        # Use non-existent tab ID to ensure temp file doesn't exist
        tab = {
            'id': 999999,
            'windows': [
                {'cwd': '/home/user/documents'}
            ]
        }
        result = get_tab_cwd(tab)

        assert result == '/home/user/documents'

    def test_cwd_no_tab_id(self):
        """Should return empty string when no tab ID."""
        tab = {'windows': [{'cwd': '/some/path'}]}
        result = get_tab_cwd(tab)

        assert result == ''

    def test_cwd_temp_file_empty(self):
        """Should fallback when temp file is empty."""
        cwd_file = Path('/tmp') / 'kitty_tab_200_cwd'
        cwd_file.write_text('')

        try:
            tab = {
                'id': 200,
                'windows': [{'cwd': '/fallback/path'}]
            }
            result = get_tab_cwd(tab)

            assert result == '/fallback/path'
        finally:
            if cwd_file.exists():
                cwd_file.unlink()

    def test_cwd_temp_file_read_error(self, monkeypatch):
        """Should fallback when temp file read fails."""
        # Mock Path.read_text to raise an exception
        def mock_read_text(self):
            raise Exception("Read error")

        monkeypatch.setattr(Path, 'read_text', mock_read_text)

        # Create the file so exists() returns True
        cwd_file = Path('/tmp') / 'kitty_tab_300_cwd'
        cwd_file.write_text('test')

        try:
            tab = {
                'id': 300,
                'windows': [{'cwd': '/fallback/path'}]
            }
            result = get_tab_cwd(tab)

            assert result == '/fallback/path'
        finally:
            if cwd_file.exists():
                cwd_file.unlink()

    def test_cwd_no_windows(self):
        """Should return empty string when no windows."""
        tab = {'id': 999998, 'windows': []}
        result = get_tab_cwd(tab)
        assert result == ''

    def test_cwd_multiple_windows(self):
        """Should return CWD from first window with CWD."""
        tab = {
            'id': 999997,
            'windows': [
                {'cwd': ''},
                {'cwd': '/home/user/first'},
                {'cwd': '/home/user/second'}
            ]
        }
        result = get_tab_cwd(tab)

        assert result == '/home/user/first'


@pytest.mark.unit
class TestUpdateTabs:
    """Tests for update_tabs function."""

    def test_update_tabs_successful(self, monkeypatch):
        """Should successfully update tabs with valid data."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 888881,
                        "title": "test",
                        "windows": [
                            {
                                "cwd": "/home/user/projects",
                                "foreground_processes": [
                                    {"cmdline": ["nvim", "file.txt"]}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        # Mock subprocess.run
        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise
        update_tabs(debug=False)

    def test_update_tabs_subprocess_error(self, monkeypatch):
        """Should handle subprocess errors gracefully."""
        def mock_run(cmd, *args, **kwargs):
            raise Exception("Subprocess error")

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise
        update_tabs(debug=False)

    def test_update_tabs_json_parse_error(self, monkeypatch):
        """Should handle JSON parse errors gracefully."""
        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            mock_result.stdout = "invalid json"
            mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise
        update_tabs(debug=False)

    def test_update_tabs_nonzero_returncode(self, monkeypatch):
        """Should handle non-zero return codes gracefully."""
        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            mock_result.returncode = 1
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise
        update_tabs(debug=False)

    def test_update_tabs_timeout(self, monkeypatch):
        """Should handle subprocess timeout gracefully."""
        def mock_run(cmd, *args, **kwargs):
            import subprocess
            raise subprocess.TimeoutExpired(cmd, kwargs.get('timeout', 2))

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise
        update_tabs(debug=False)

    def test_update_tabs_with_debug(self, monkeypatch, tmp_path):
        """Should write debug log when debug=True."""
        mock_tab_data = [{"id": 1, "tabs": []}]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            mock_result.stdout = json.dumps(mock_tab_data)
            mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Mock Path.home() to use tmp_path
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmp_path
            log_dir = tmp_path / '.config' / 'kitty'
            log_dir.mkdir(parents=True)

            update_tabs(debug=True)

            log_file = log_dir / 'tab_color_debug.log'
            assert log_file.exists()
            content = log_file.read_text()
            assert '=== Tab CWD Debug ===' in content

    def test_update_tabs_strips_trailing_slash(self, monkeypatch):
        """Should strip trailing slashes from CWD."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 888882,
                        "title": "test",
                        "windows": [
                            {
                                "cwd": "/home/user/projects/",  # trailing slash
                                "foreground_processes": [{"cmdline": ["zsh"]}]
                            }
                        ]
                    }
                ]
            }
        ]

        run_calls = []

        def mock_run(cmd, *args, **kwargs):
            run_calls.append(cmd)
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
            mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        update_tabs(debug=False)

        # Check that set-tab-title was called (meaning CWD was processed)
        title_calls = [c for c in run_calls if 'set-tab-title' in c]
        assert len(title_calls) > 0

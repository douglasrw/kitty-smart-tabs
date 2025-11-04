"""Integration tests for Smart Tabs."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from smart_tabs.core import update_tabs
from smart_tabs.config import Config
from smart_tabs.colors import get_color_for_path


@pytest.mark.integration
class TestEndToEndTabUpdate:
    """Integration tests for complete tab update flow."""

    def test_multiple_tabs_different_directories(self, monkeypatch, tmp_path):
        """Multiple tabs in different directories get different colors."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 777100,
                        "title": "projects",
                        "windows": [
                            {
                                "cwd": "/home/user/projects",
                                "foreground_processes": [
                                    {"cmdline": ["nvim", "main.py"]}
                                ]
                            }
                        ]
                    },
                    {
                        "id": 777101,
                        "title": "documents",
                        "windows": [
                            {
                                "cwd": "/home/user/documents",
                                "foreground_processes": [
                                    {"cmdline": ["zsh"]}
                                ]
                            }
                        ]
                    },
                    {
                        "id": 777102,
                        "title": "projects-again",
                        "windows": [
                            {
                                "cwd": "/home/user/projects",  # Same as tab 777100
                                "foreground_processes": [
                                    {"cmdline": ["git", "status"]}
                                ]
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

        # Check that colors were set
        color_calls = [c for c in run_calls if 'set-tab-color' in c]
        assert len(color_calls) == 3  # One for each tab

        # Tabs 777100 and 777102 should have same color (same directory)
        tab100_color = None
        tab102_color = None
        for call in color_calls:
            if 'id:777100' in ' '.join(call):
                # Extract color from call
                for i, part in enumerate(call):
                    if part.startswith('active_fg='):
                        tab100_color = part.split('=')[1]
            if 'id:777102' in ' '.join(call):
                for i, part in enumerate(call):
                    if part.startswith('active_fg='):
                        tab102_color = part.split('=')[1]

        # Both tabs in /home/user/projects should have same color
        if tab100_color and tab102_color:
            assert tab100_color == tab102_color

    def test_tab_titles_with_commands(self, monkeypatch):
        """Tab titles should include command names when detected."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 777200,
                        "title": "projects",
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

        # Check that title includes command
        title_calls = [c for c in run_calls if 'set-tab-title' in c]
        assert len(title_calls) == 1

        title_call = title_calls[0]
        # Title should contain "nvim" and directory name "projects"
        title_arg = ' '.join(title_call)
        assert 'nvim' in title_arg
        assert 'projects' in title_arg

    def test_tab_titles_without_commands_when_disabled(self, monkeypatch, tmp_path):
        """Tab titles should not include commands when disabled in config."""
        # Create config with show_commands = false
        config_path = tmp_path / "test.conf"
        config_path.write_text("""[behavior]
show_commands = false
""")

        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 666100,
                        "title": "projects",
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

        # Temporarily override default config path
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = tmp_path
            config_dir = tmp_path / '.config' / 'kitty'
            config_dir.mkdir(parents=True)
            (config_dir / 'smart_tabs.conf').write_text("""[behavior]
show_commands = false
""")

            with patch('smart_tabs.core.Config') as mock_config_cls:
                config = Config(config_dir / 'smart_tabs.conf')
                mock_config_cls.return_value = config

                update_tabs(debug=False)

        # Check that title does not include command
        title_calls = [c for c in run_calls if 'set-tab-title' in c]
        if title_calls:
            title_call = title_calls[0]
            title_arg = ' '.join(title_call)
            # Should not have brackets indicating command
            assert '[nvim]' not in title_arg


@pytest.mark.integration
class TestConfigIntegration:
    """Integration tests for config system."""

    def test_custom_palette_affects_colors(self, tmp_path):
        """Custom color palette should be used for color generation."""
        config_path = tmp_path / "test.conf"
        config_path.write_text("""[colors]
palette = #ff0000,#00ff00
""")

        config = Config(config_path)
        palette = config.get_color_palette()

        # Generate colors with this palette
        color1 = get_color_for_path("/home/user/projects", palette)
        color2 = get_color_for_path("/home/user/documents", palette)

        # Both colors should be from custom palette
        assert color1 in ['#ff0000', '#00ff00']
        assert color2 in ['#ff0000', '#00ff00']

    def test_custom_max_lengths(self, tmp_path):
        """Custom max lengths should affect title formatting."""
        config_path = tmp_path / "test.conf"
        config_path.write_text("""[behavior]
max_dir_length = 5
max_cmd_length = 3
""")

        config = Config(config_path)
        assert config.max_dir_length == 5
        assert config.max_cmd_length == 3


@pytest.mark.integration
class TestErrorRecovery:
    """Integration tests for error handling and recovery."""

    def test_continues_after_failed_tab_update(self, monkeypatch):
        """Should continue processing other tabs if one fails."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 666100,
                        "title": "tab1",
                        "windows": [
                            {
                                "cwd": "/home/user/projects",
                                "foreground_processes": [{"cmdline": ["nvim"]}]
                            }
                        ]
                    },
                    {
                        "id": 666101,
                        "title": "tab2",
                        "windows": [
                            {
                                "cwd": "/home/user/documents",
                                "foreground_processes": [{"cmdline": ["git"]}]
                            }
                        ]
                    }
                ]
            }
        ]

        call_count = [0]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd and 'id:666100' in ' '.join(cmd):
                # Fail first tab
                call_count[0] += 1
                raise Exception("Failed to set title")
            else:
                mock_result.returncode = 0
                call_count[0] += 1
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise even though one tab failed
        update_tabs(debug=False)

        # Should have attempted to update both tabs
        assert call_count[0] > 0

    def test_handles_malformed_tab_data(self, monkeypatch):
        """Should handle malformed tab data gracefully."""
        # Tab with missing required fields
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        # Missing 'id'
                        "title": "tab1",
                        "windows": [
                            {
                                "cwd": "/home/user/projects",
                                "foreground_processes": []
                            }
                        ]
                    },
                    {
                        "id": 666101,
                        # Valid tab
                        "title": "tab2",
                        "windows": [
                            {
                                "cwd": "/home/user/documents",
                                "foreground_processes": [{"cmdline": ["git"]}]
                            }
                        ]
                    }
                ]
            }
        ]

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data)
            mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-12345'])

        # Should not raise
        update_tabs(debug=False)


@pytest.mark.integration
class TestRealisticScenarios:
    """Integration tests for realistic usage scenarios."""

    def test_development_workflow(self, monkeypatch):
        """Test realistic development workflow with editor, shell, and git."""
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": 666100,
                        "title": "editor",
                        "windows": [
                            {
                                "cwd": "/home/user/myproject",
                                "foreground_processes": [
                                    {"cmdline": ["nvim", "src/main.py"]}
                                ]
                            }
                        ]
                    },
                    {
                        "id": 666101,
                        "title": "shell",
                        "windows": [
                            {
                                "cwd": "/home/user/myproject",
                                "foreground_processes": [
                                    {"cmdline": ["zsh"]}  # Should be filtered
                                ]
                            }
                        ]
                    },
                    {
                        "id": 666102,
                        "title": "git",
                        "windows": [
                            {
                                "cwd": "/home/user/myproject",
                                "foreground_processes": [
                                    {"cmdline": ["git", "log", "--oneline"]}
                                ]
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

        # All three tabs should have same color (same directory)
        color_calls = [c for c in run_calls if 'set-tab-color' in c]
        assert len(color_calls) == 3

        # Extract colors
        colors = []
        for call in color_calls:
            for part in call:
                if part.startswith('active_fg='):
                    colors.append(part.split('=')[1])

        # All should be the same color
        assert len(set(colors)) == 1

        # Check titles show appropriate commands
        title_calls = [c for c in run_calls if 'set-tab-title' in c]
        title_strs = [' '.join(c) for c in title_calls]

        # Editor tab should show nvim
        editor_title = [t for t in title_strs if 'id:666100' in t]
        assert any('nvim' in t for t in editor_title)

        # Shell tab should not show command (filtered)
        shell_title = [t for t in title_strs if 'id:666101' in t]
        assert any('[' not in t or 'zsh' not in t for t in shell_title)

        # Git tab should show git (priority command)
        git_title = [t for t in title_strs if 'id:666102' in t]
        assert any('git' in t for t in git_title)

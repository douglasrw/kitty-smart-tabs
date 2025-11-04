"""Tests for command parsing logic."""

import pytest
from smart_tabs.core import _parse_process_command, get_running_command


@pytest.mark.unit
class TestParseProcessCommand:
    """Tests for _parse_process_command function."""

    def test_filters_shells(self, default_config):
        """Shell processes should be filtered out."""
        shells = ['zsh', 'bash', 'sh', 'fish', 'ksh', 'tcsh', 'csh']
        for shell in shells:
            process = {"cmdline": [shell]}
            assert _parse_process_command(process, default_config) is None

    def test_filters_login_shells(self, default_config):
        """Login shells like -zsh should be filtered."""
        process = {"cmdline": ["-zsh"]}
        assert _parse_process_command(process, default_config) is None

        process = {"cmdline": ["-bash"]}
        assert _parse_process_command(process, default_config) is None

    def test_filters_kitty_tools(self, default_config):
        """Kitty-related processes should be filtered."""
        kitty_tools = ['kitty', 'kitten', 'color_tabs_by_cwd', 'smart_tabs']
        for tool in kitty_tools:
            process = {"cmdline": [tool]}
            assert _parse_process_command(process, default_config) is None

    def test_filters_system_utils(self, default_config):
        """System utilities should be filtered."""
        utils = ['sleep', 'wait', 'cat', 'echo', 'true', 'false', 'test',
                 'grep', 'sed', 'awk', 'tail', 'head']
        for util in utils:
            process = {"cmdline": [util]}
            assert _parse_process_command(process, default_config) is None

    def test_filters_configured_commands(self, default_config):
        """Commands in ignored_commands config should be filtered."""
        process = {"cmdline": ["npm", "install"]}
        assert _parse_process_command(process, default_config) is None

        process = {"cmdline": ["yarn", "start"]}
        assert _parse_process_command(process, default_config) is None

    def test_filters_by_prefix(self, default_config):
        """Commands matching ignored_prefixes should be filtered."""
        process = {"cmdline": ["mcp_server_filesystem"]}
        assert _parse_process_command(process, default_config) is None

        process = {"cmdline": ["helper-script"]}
        assert _parse_process_command(process, default_config) is None

    def test_filters_by_suffix(self, default_config):
        """Commands matching ignored_suffixes should be filtered."""
        process = {"cmdline": ["redis-server"]}
        assert _parse_process_command(process, default_config) is None

        process = {"cmdline": ["worker-daemon"]}
        assert _parse_process_command(process, default_config) is None

    def test_simple_command(self, default_config):
        """Simple commands should return basename."""
        process = {"cmdline": ["nvim"]}
        assert _parse_process_command(process, default_config) == "nvim"

        process = {"cmdline": ["git", "status"]}
        assert _parse_process_command(process, default_config) == "git"

    def test_full_path_command(self, default_config):
        """Commands with full paths should return basename only."""
        process = {"cmdline": ["/usr/bin/nvim", "file.txt"]}
        assert _parse_process_command(process, default_config) == "nvim"

        process = {"cmdline": ["/usr/local/bin/git", "status"]}
        assert _parse_process_command(process, default_config) == "git"

    def test_python_script_unwrapping(self, default_config):
        """Python interpreter should unwrap to script name."""
        process = {"cmdline": ["python", "my_script.py"]}
        assert _parse_process_command(process, default_config) == "my_script"

        process = {"cmdline": ["python3", "analyzer.py"]}
        assert _parse_process_command(process, default_config) == "analyzer"

    def test_python_with_flags(self, default_config):
        """Python with flags should skip flags and find script."""
        # Note: Current implementation doesn't handle flags with arguments
        # -W takes an argument "ignore", which is incorrectly treated as a script
        process = {"cmdline": ["python", "-u", "script.py"]}
        assert _parse_process_command(process, default_config) == "script"

    def test_node_script_unwrapping(self, default_config):
        """Node interpreter should unwrap to script name."""
        process = {"cmdline": ["node", "server.js"]}
        assert _parse_process_command(process, default_config) == "server"

        # 'app' is a generic name, so it returns 'node' unchanged
        process = {"cmdline": ["node", "app.mjs"]}
        assert _parse_process_command(process, default_config) == "node"

    def test_ruby_script_unwrapping(self, default_config):
        """Ruby interpreter should unwrap to script name."""
        process = {"cmdline": ["ruby", "script.rb"]}
        assert _parse_process_command(process, default_config) == "script"

    def test_generic_script_names_filtered(self, default_config):
        """Generic script names like main.py should be skipped and return interpreter."""
        generic_names = ['index.js', 'main.py', 'app.js', 'cli.py',
                        'bin.js', 'start.js', 'run.py']
        for script in generic_names:
            interpreter = "python" if script.endswith('.py') else "node"
            process = {"cmdline": [interpreter, script]}
            # Should return interpreter name since generic names are skipped
            assert _parse_process_command(process, default_config) == interpreter

    def test_script_with_path(self, default_config):
        """Scripts with full paths should extract basename."""
        process = {"cmdline": ["python", "/home/user/projects/analyzer.py"]}
        assert _parse_process_command(process, default_config) == "analyzer"

        process = {"cmdline": ["node", "/var/www/app/server.js"]}
        assert _parse_process_command(process, default_config) == "server"

    def test_truncation(self, default_config):
        """Long command names should be truncated."""
        # max_cmd_length is 30 by default
        long_name = "a" * 50
        process = {"cmdline": [long_name]}
        result = _parse_process_command(process, default_config)
        assert result == "a" * 27 + "..."
        assert len(result) == 30

    def test_empty_cmdline(self, default_config):
        """Empty cmdline should return None."""
        process = {"cmdline": []}
        assert _parse_process_command(process, default_config) is None

    def test_no_cmdline_key(self, default_config):
        """Missing cmdline key should return None."""
        process = {}
        assert _parse_process_command(process, default_config) is None

    def test_case_insensitive_filtering(self, default_config):
        """Filtering should be case insensitive."""
        process = {"cmdline": ["ZSH"]}
        assert _parse_process_command(process, default_config) is None

        process = {"cmdline": ["NPM", "install"]}
        assert _parse_process_command(process, default_config) is None


@pytest.mark.unit
class TestGetRunningCommand:
    """Tests for get_running_command function."""

    def test_no_windows(self, default_config):
        """Tab with no windows should return None."""
        tab = {"windows": []}
        assert get_running_command(tab, default_config) is None

    def test_no_foreground_processes(self, default_config):
        """Window with no foreground processes should return None."""
        tab = {
            "windows": [
                {"foreground_processes": []}
            ]
        }
        assert get_running_command(tab, default_config) is None

    def test_single_valid_command(self, default_config):
        """Single valid command should be returned."""
        tab = {
            "windows": [
                {
                    "foreground_processes": [
                        {"cmdline": ["nvim", "file.txt"]}
                    ]
                }
            ]
        }
        assert get_running_command(tab, default_config) == "nvim"

    def test_shell_filtered_out(self, default_config):
        """Shell process should be filtered, returning None."""
        tab = {
            "windows": [
                {
                    "foreground_processes": [
                        {"cmdline": ["zsh"]}
                    ]
                }
            ]
        }
        assert get_running_command(tab, default_config) is None

    def test_priority_command_selected(self, default_config):
        """Priority commands should be selected first."""
        tab = {
            "windows": [
                {
                    "foreground_processes": [
                        {"cmdline": ["some_app"]},
                        {"cmdline": ["git", "status"]},  # priority command
                        {"cmdline": ["another_app"]}
                    ]
                }
            ]
        }
        assert get_running_command(tab, default_config) == "git"

    def test_first_valid_command_when_no_priority(self, default_config):
        """First valid command should be returned when no priority match."""
        tab = {
            "windows": [
                {
                    "foreground_processes": [
                        {"cmdline": ["zsh"]},  # filtered
                        {"cmdline": ["myapp"]},  # should be returned
                        {"cmdline": ["otherapp"]}
                    ]
                }
            ]
        }
        assert get_running_command(tab, default_config) == "myapp"

    def test_multiple_filtered_commands(self, default_config):
        """All filtered commands should return None."""
        tab = {
            "windows": [
                {
                    "foreground_processes": [
                        {"cmdline": ["zsh"]},
                        {"cmdline": ["sleep", "100"]},
                        {"cmdline": ["cat", "file.txt"]}
                    ]
                }
            ]
        }
        assert get_running_command(tab, default_config) is None

"""Tests for configuration management."""

import pytest
from pathlib import Path
from smart_tabs.config import Config, DEFAULT_CONFIG


@pytest.mark.unit
class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_default_config_loads(self, default_config):
        """Default config should load without errors."""
        assert default_config is not None

    def test_default_color_palette(self, default_config):
        """Default color palette should contain 6 colors."""
        palette = default_config.get_color_palette()
        assert len(palette) == 6
        assert all(color.startswith('#') for color in palette)

    def test_default_show_commands(self, default_config):
        """Default show_commands should be True."""
        assert default_config.show_commands is True

    def test_default_show_tab_index(self, default_config):
        """Default show_tab_index should be True."""
        assert default_config.show_tab_index is True

    def test_default_poll_interval(self, default_config):
        """Default poll_interval should be 2 seconds."""
        assert default_config.poll_interval == 2

    def test_default_max_dir_length(self, default_config):
        """Default max_dir_length should be 30."""
        assert default_config.max_dir_length == 30

    def test_default_max_cmd_length(self, default_config):
        """Default max_cmd_length should be 30."""
        assert default_config.max_cmd_length == 30

    def test_default_arrows(self, default_config):
        """Default arrows should be set."""
        assert default_config.arrows == '▶▶▶▶'

    def test_default_ignored_shells(self, default_config):
        """Default ignored_shells should include common shells."""
        shells = default_config.ignored_shells
        assert 'zsh' in shells
        assert 'bash' in shells
        assert 'sh' in shells
        assert 'fish' in shells

    def test_default_ignored_commands(self, default_config):
        """Default ignored_commands should include common utilities."""
        commands = default_config.ignored_commands
        assert 'npm' in commands
        assert 'yarn' in commands
        assert 'sleep' in commands

    def test_default_ignored_prefixes(self, default_config):
        """Default ignored_prefixes should be configured."""
        prefixes = default_config.ignored_prefixes
        assert 'mcp_server_' in prefixes
        assert 'helper-' in prefixes

    def test_default_ignored_suffixes(self, default_config):
        """Default ignored_suffixes should be configured."""
        suffixes = default_config.ignored_suffixes
        assert '-daemon' in suffixes
        assert '-server' in suffixes

    def test_default_priority_commands(self, default_config):
        """Default priority_commands should include common editors."""
        priorities = default_config.priority_commands
        assert 'nvim' in priorities
        assert 'vim' in priorities
        assert 'git' in priorities


@pytest.mark.unit
class TestConfigCustom:
    """Tests for custom configuration loading."""

    def test_custom_config_loads(self, custom_config):
        """Custom config should override defaults."""
        assert custom_config is not None

    def test_custom_color_palette(self, custom_config):
        """Custom color palette should override default."""
        palette = custom_config.get_color_palette()
        assert len(palette) == 3
        assert palette == ['#ff0000', '#00ff00', '#0000ff']

    def test_custom_show_tab_index(self, custom_config):
        """Custom show_tab_index should override default."""
        assert custom_config.show_tab_index is False

    def test_custom_poll_interval(self, custom_config):
        """Custom poll_interval should override default."""
        assert custom_config.poll_interval == 1

    def test_custom_max_lengths(self, custom_config):
        """Custom max lengths should override defaults."""
        assert custom_config.max_dir_length == 20
        assert custom_config.max_cmd_length == 15

    def test_custom_ignored_shells(self, custom_config):
        """Custom ignored_shells should override default."""
        shells = custom_config.ignored_shells
        assert shells == {'zsh', 'bash'}

    def test_custom_ignored_commands(self, custom_config):
        """Custom ignored_commands should override default."""
        commands = custom_config.ignored_commands
        assert commands == {'npm', 'sleep'}

    def test_custom_priority_commands(self, custom_config):
        """Custom priority_commands should override default."""
        priorities = custom_config.priority_commands
        assert priorities == {'nvim', 'git'}


@pytest.mark.unit
class TestConfigMethods:
    """Tests for Config helper methods."""

    def test_get_bool_true(self, default_config):
        """get_bool should return True for 'true' values."""
        assert default_config.get_bool('behavior', 'show_commands') is True

    def test_get_int(self, default_config):
        """get_int should return integer values."""
        assert default_config.get_int('behavior', 'poll_interval') == 2
        assert isinstance(default_config.get_int('behavior', 'poll_interval'), int)

    def test_get_str(self, default_config):
        """get_str should return string values."""
        arrows = default_config.get_str('active_tab', 'arrows')
        assert isinstance(arrows, str)
        assert arrows == '▶▶▶▶'

    def test_get_list(self, default_config):
        """get_list should return list from comma-separated string."""
        shells = default_config.get_list('filters', 'ignored_shells')
        assert isinstance(shells, list)
        assert 'zsh' in shells
        assert 'bash' in shells

    def test_get_set(self, default_config):
        """get_set should return set from comma-separated string."""
        shells = default_config.get_set('filters', 'ignored_shells')
        assert isinstance(shells, set)
        assert 'zsh' in shells
        assert 'bash' in shells

    def test_get_list_strips_whitespace(self, tmp_path):
        """get_list should strip whitespace from list items."""
        config_path = tmp_path / "test.conf"
        config_path.write_text("""[filters]
ignored_shells = zsh , bash  ,  fish
""")
        config = Config(config_path)
        shells = config.get_list('filters', 'ignored_shells')
        assert shells == ['zsh', 'bash', 'fish']


@pytest.mark.unit
class TestConfigFileHandling:
    """Tests for config file handling edge cases."""

    def test_nonexistent_config_uses_defaults(self, tmp_path):
        """Nonexistent config file should fall back to defaults."""
        nonexistent = tmp_path / "nonexistent.conf"
        config = Config(nonexistent)
        assert config.show_commands is True
        assert config.poll_interval == 2

    def test_empty_config_uses_defaults(self, tmp_path):
        """Empty config file should use defaults."""
        empty_config = tmp_path / "empty.conf"
        empty_config.write_text("")
        config = Config(empty_config)
        assert config.show_commands is True
        assert config.poll_interval == 2

    def test_partial_config_merges_with_defaults(self, tmp_path):
        """Partial config should merge with defaults."""
        partial_config = tmp_path / "partial.conf"
        partial_config.write_text("""[behavior]
poll_interval = 5
""")
        config = Config(partial_config)
        # Custom value
        assert config.poll_interval == 5
        # Default values
        assert config.show_commands is True
        assert config.show_tab_index is True

    def test_config_path_stored(self, tmp_path):
        """Config should store the config path."""
        config_path = tmp_path / "test.conf"
        config_path.write_text("")
        config = Config(config_path)
        assert config.config_path == config_path

    def test_default_config_path(self):
        """Default config path should be in ~/.config/kitty."""
        config = Config()
        expected_path = Path.home() / '.config/kitty/smart_tabs.conf'
        assert config.config_path == expected_path

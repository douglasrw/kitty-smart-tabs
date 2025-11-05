"""Configuration management for Smart Tabs."""

import configparser
from pathlib import Path
from typing import List, Dict, Any


DEFAULT_CONFIG = {
    'colors': {
        'palette': '#2b8eff,#a9dc76,#ab9df2,#ffd866,#78dce8,#f48771,#ff6188,#fc9867,#79dac8,#5ad4e6,#9ecd6f,#e0af68,#bb9af7,#7dcfff,#ff9e64,#7aa2f7'
    },
    'behavior': {
        'show_commands': 'true',
        'show_tab_index': 'true',
        'poll_interval': '2',
        'max_dir_length': '30',
        'max_cmd_length': '30'
    },
    'active_tab': {
        'arrows': '▶▶▶▶'
    },
    'filters': {
        'ignored_shells': 'zsh,bash,sh,fish,ksh,tcsh,csh',
        'ignored_commands': 'npm,yarn,sleep,cat,grep,sed,awk,pip,gem',
        'ignored_prefixes': 'mcp_server_,helper-,worker-,node_modules,ts-node',
        'ignored_suffixes': '-helper,-worker,-daemon,-service,-server',
        'priority_commands': 'nvim,vim,vi,emacs,code,nano,claude,git,docker,kubectl'
    }
}


class Config:
    """Configuration manager for Smart Tabs."""

    def __init__(self, config_path: Path = None):
        """Initialize config from file or defaults.

        Args:
            config_path: Path to config file. Uses default location if None.
        """
        if config_path is None:
            config_path = Path.home() / '.config/kitty/smart_tabs.conf'

        self.config_path = config_path
        self.parser = configparser.ConfigParser()

        # Load defaults
        self.parser.read_dict(DEFAULT_CONFIG)

        # Override with user config if exists
        if config_path.exists():
            self.parser.read(config_path)

    def get_color_palette(self) -> List[str]:
        """Get list of hex colors from config."""
        palette_str = self.parser.get('colors', 'palette')
        return [c.strip() for c in palette_str.split(',')]

    def get_bool(self, section: str, key: str) -> bool:
        """Get boolean value from config."""
        return self.parser.getboolean(section, key)

    def get_int(self, section: str, key: str) -> int:
        """Get integer value from config."""
        return self.parser.getint(section, key)

    def get_str(self, section: str, key: str) -> str:
        """Get string value from config."""
        return self.parser.get(section, key)

    def get_list(self, section: str, key: str) -> List[str]:
        """Get comma-separated list from config."""
        value = self.parser.get(section, key)
        return [item.strip() for item in value.split(',')]

    def get_set(self, section: str, key: str) -> set:
        """Get comma-separated list as set from config."""
        return set(self.get_list(section, key))

    @property
    def show_commands(self) -> bool:
        return self.get_bool('behavior', 'show_commands')

    @property
    def show_tab_index(self) -> bool:
        return self.get_bool('behavior', 'show_tab_index')

    @property
    def poll_interval(self) -> int:
        return self.get_int('behavior', 'poll_interval')

    @property
    def max_dir_length(self) -> int:
        return self.get_int('behavior', 'max_dir_length')

    @property
    def max_cmd_length(self) -> int:
        return self.get_int('behavior', 'max_cmd_length')

    @property
    def arrows(self) -> str:
        return self.get_str('active_tab', 'arrows')

    @property
    def ignored_shells(self) -> set:
        return self.get_set('filters', 'ignored_shells')

    @property
    def ignored_commands(self) -> set:
        return self.get_set('filters', 'ignored_commands')

    @property
    def ignored_prefixes(self) -> List[str]:
        return self.get_list('filters', 'ignored_prefixes')

    @property
    def ignored_suffixes(self) -> List[str]:
        return self.get_list('filters', 'ignored_suffixes')

    @property
    def priority_commands(self) -> set:
        return self.get_set('filters', 'priority_commands')

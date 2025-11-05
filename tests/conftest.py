"""Pytest fixtures for Smart Tabs tests."""

import json
import tempfile
from pathlib import Path
from typing import Dict, List
import pytest

from smart_tabs.config import Config


@pytest.fixture
def default_config(tmp_path):
    """Provide default Config instance without reading user config."""
    # Use non-existent path to force Config to use built-in defaults
    nonexistent = tmp_path / "nonexistent.conf"
    return Config(nonexistent)


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file."""
    config_path = tmp_path / "smart_tabs.conf"
    config_content = """[colors]
palette = #ff0000,#00ff00,#0000ff

[behavior]
show_commands = true
show_tab_index = false
poll_interval = 1
max_dir_length = 20
max_cmd_length = 15

[filters]
ignored_shells = zsh,bash
ignored_commands = npm,sleep
ignored_prefixes = test_
ignored_suffixes = _test
priority_commands = nvim,git
"""
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def custom_config(temp_config_file):
    """Provide Config instance with custom settings."""
    return Config(temp_config_file)


@pytest.fixture
def mock_tab_data():
    """Provide sample tab data structure from 'kitty @ ls'."""
    return [
        {
            "id": 1,
            "tabs": [
                {
                    "id": 100,
                    "title": "tab1",
                    "windows": [
                        {
                            "id": 1000,
                            "cwd": "/home/user/projects",
                            "foreground_processes": [
                                {
                                    "pid": 12345,
                                    "cmdline": ["zsh"]
                                }
                            ]
                        }
                    ]
                },
                {
                    "id": 101,
                    "title": "tab2",
                    "windows": [
                        {
                            "id": 1001,
                            "cwd": "/home/user/documents",
                            "foreground_processes": [
                                {
                                    "pid": 12346,
                                    "cmdline": ["nvim", "test.txt"]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]


@pytest.fixture
def mock_process_shell():
    """Mock shell process data."""
    return {"pid": 1, "cmdline": ["zsh"]}


@pytest.fixture
def mock_process_nvim():
    """Mock nvim process data."""
    return {"pid": 2, "cmdline": ["nvim", "test.txt"]}


@pytest.fixture
def mock_process_python():
    """Mock python script process data."""
    return {"pid": 3, "cmdline": ["python", "script.py"]}


@pytest.fixture
def mock_process_node():
    """Mock node script process data."""
    return {"pid": 4, "cmdline": ["node", "server.js"]}


@pytest.fixture
def temp_cwd_file(tmp_path):
    """Create temporary CWD tracking file."""
    def _create(tab_id: int, cwd: str) -> Path:
        cwd_file = Path(f"/tmp/kitty_tab_{tab_id}_cwd")
        cwd_file.write_text(cwd)
        return cwd_file
    return _create


@pytest.fixture
def mock_subprocess_run(monkeypatch):
    """Mock subprocess.run for testing without Kitty."""
    class MockResult:
        def __init__(self, stdout="", stderr="", returncode=0):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode

    results = {}

    def mock_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if "ls" in cmd:
            return results.get("ls", MockResult(stdout="[]", returncode=0))
        elif "set-tab-title" in cmd:
            return results.get("set-tab-title", MockResult(returncode=0))
        elif "set-tab-color" in cmd:
            return results.get("set-tab-color", MockResult(returncode=0))
        return MockResult(returncode=0)

    monkeypatch.setattr("subprocess.run", mock_run)
    return results

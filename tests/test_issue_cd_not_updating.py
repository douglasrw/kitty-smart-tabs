"""Test to verify tab title updates after cd into subdirectory.

Issue: When starting kitty in home dir, cd into ~/dev, then opening new tab,
the first tab still shows "dwalseth" instead of "dev".

Root cause: Shell hooks not loaded, so temp files aren't created on cd.
update_tabs relies on kitty's stale CWD instead of actual shell CWD.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock
from smart_tabs.core import update_tabs, _tab_state_cache, _tab_input_cache
from smart_tabs.tempfiles import write_cwd_atomic


@pytest.mark.integration
class TestCdNotUpdatingTitle:
    """Test that verifies the cd → new tab issue."""

    def test_without_shell_hooks_tab_shows_stale_cwd(self, monkeypatch, tmp_path):
        """Reproduce ACTUAL issue: Without shell hooks, temp files don't exist, shows stale CWD.

        Scenario:
        1. User starts kitty in /Users/dwalseth
        2. User cd's to /Users/dwalseth/dev
        3. Shell hook NOT loaded, so NO temp file written
        4. User opens new tab (Cmd+T)
        5. update_tabs runs, reads kitty's CWD (which is stale)
        6. Tab 1 incorrectly shows "dwalseth" instead of "dev"

        This test SHOULD FAIL to demonstrate the bug.
        """

        # Setup - NO temp file directory to simulate hooks not loaded
        monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))

        tab1_id = 1
        tab2_id = 2
        home_dir = "/Users/dwalseth"
        dev_dir = "/Users/dwalseth/dev"

        # DO NOT write temp file - simulating shell hooks not loaded
        # write_cwd_atomic(tab1_id, dev_dir)  # <-- This would fix it, but we DON'T do this

        captured_titles_by_tab = {}

        # Kitty's view of the world after user cd'd and opened new tab:
        # - Tab 1's CWD in kitty is STALE (still shows home_dir)
        # - Tab 2 inherits from shell, so it correctly shows dev_dir
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": tab1_id,
                        "title": "dwalseth",
                        "windows": [{
                            "cwd": home_dir,  # STALE - kitty doesn't know user cd'd
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    },
                    {
                        "id": tab2_id,
                        "title": "zsh",
                        "windows": [{
                            "cwd": dev_dir,  # Correct - new tab inherits current shell CWD
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
            elif 'set-tab-title' in cmd:
                tab_match = [x for x in cmd if x.startswith('--match=id:')]
                if tab_match and len(cmd) > 3:
                    tab_id = int(tab_match[0].split(':')[1])
                    title = cmd[-1]
                    captured_titles_by_tab[tab_id] = title
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        _tab_state_cache.clear()
        _tab_input_cache.clear()

        # Daemon polls after new tab opens
        update_tabs(debug=False)

        print(f"\nCaptured titles: {captured_titles_by_tab}")

        # THE BUG: Tab 1 shows "dwalseth" when it should show "dev"
        if tab1_id in captured_titles_by_tab:
            tab1_title = captured_titles_by_tab[tab1_id]
            print(f"Tab 1 title: {tab1_title}")

            # This assertion SHOULD FAIL, demonstrating the bug
            assert 'dev' in tab1_title, (
                f"BUG REPRODUCED: Tab 1 shows '{tab1_title}' instead of 'dev'. "
                f"Without shell hooks, temp file doesn't exist, so we get stale CWD from kitty. "
                f"User cd'd to ~/dev but tab still shows 'dwalseth'."
            )

        # Tab 2 will correctly show "dev" since it's a new tab
        if tab2_id in captured_titles_by_tab:
            tab2_title = captured_titles_by_tab[tab2_id]
            print(f"Tab 2 title: {tab2_title}")
            # This one should pass - new tabs get correct CWD
            assert 'dev' in tab2_title

    def test_tab_title_updates_after_cd_to_subdirectory(self, monkeypatch, tmp_path):
        """Reproduce: Start in /Users/dwalseth, cd to /Users/dwalseth/dev, verify title shows 'dev'."""

        # Setup temp file directory
        monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))

        tab_id = 1
        home_dir = "/Users/dwalseth"
        dev_dir = "/Users/dwalseth/dev"

        # Simulate tab initially in home directory
        mock_tab_data_home = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": tab_id,
                        "title": "dwalseth",
                        "windows": [{
                            "cwd": home_dir,
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        captured_titles = []

        def mock_run(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data_home)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd:
                if len(cmd) > 3:
                    captured_titles.append(cmd[-1])
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Clear caches
        _tab_state_cache.clear()
        _tab_input_cache.clear()

        # First update - tab should show "dwalseth"
        update_tabs(debug=False)

        assert len(captured_titles) == 1
        assert 'dwalseth' in captured_titles[0]
        print(f"Initial title: {captured_titles[0]}")

        # Now simulate user cd into ~/dev
        # Shell hook writes the new CWD to temp file
        write_cwd_atomic(tab_id, dev_dir)

        # Update mock to return dev_dir as the CWD
        mock_tab_data_dev = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": tab_id,
                        "title": "dwalseth",  # Still shows old title from kitty
                        "windows": [{
                            "cwd": home_dir,  # Kitty's CWD might be stale
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    }
                ]
            }
        ]

        def mock_run_after_cd(cmd, *args, **kwargs):
            mock_result = Mock()
            if 'ls' in cmd:
                mock_result.stdout = json.dumps(mock_tab_data_dev)
                mock_result.returncode = 0
            elif 'set-tab-title' in cmd:
                if len(cmd) > 3:
                    captured_titles.append(cmd[-1])
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run_after_cd)

        # Daemon polls and runs update_tabs
        # This should read from temp file and update to "dev"
        captured_titles.clear()
        update_tabs(debug=False)

        # Verify title was updated to show "dev"
        print(f"After cd titles captured: {captured_titles}")

        if len(captured_titles) > 0:
            latest_title = captured_titles[-1]
            print(f"Latest title: {latest_title}")

            # THE TEST: Title should show "dev" not "dwalseth"
            assert 'dev' in latest_title, f"Expected 'dev' in title, got: {latest_title}"
            assert 'dwalseth' not in latest_title, f"Title should not contain 'dwalseth', got: {latest_title}"
        else:
            # If no title update captured, it means cache prevented update
            # This is the bug - title should have updated
            pytest.fail("No title update occurred after cd to subdirectory. Title should have changed from 'dwalseth' to 'dev'")

    def test_tab_shows_correct_dir_when_opening_second_tab(self, monkeypatch, tmp_path):
        """Reproduce exact user scenario: cd ~/dev, then Cmd+T to open new tab."""

        monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))

        tab1_id = 100
        tab2_id = 101
        home_dir = "/Users/dwalseth"
        dev_dir = "/Users/dwalseth/dev"

        captured_titles_by_tab = {}

        # Initial state: Tab 1 in home dir
        _tab_state_cache.clear()
        _tab_input_cache.clear()

        # User cd's to ~/dev in tab 1
        write_cwd_atomic(tab1_id, dev_dir)

        # Now user opens new tab (tab 2) - this triggers an update
        # Tab 2 is also in dev dir (inherits from tab 1)
        mock_tab_data = [
            {
                "id": 1,
                "tabs": [
                    {
                        "id": tab1_id,
                        "title": "dwalseth",  # Old title
                        "windows": [{
                            "cwd": home_dir,  # Kitty's stale CWD
                            "foreground_processes": [{"cmdline": ["zsh"]}]
                        }]
                    },
                    {
                        "id": tab2_id,
                        "title": "zsh",  # New tab default title
                        "windows": [{
                            "cwd": dev_dir,  # New tab inherits current dir
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
            elif 'set-tab-title' in cmd:
                # Extract which tab
                tab_match = [x for x in cmd if x.startswith('--match=id:')]
                if tab_match and len(cmd) > 3:
                    tab_id = int(tab_match[0].split(':')[1])
                    title = cmd[-1]
                    captured_titles_by_tab[tab_id] = title
                mock_result.returncode = 0
            else:
                mock_result.returncode = 0
            return mock_result

        monkeypatch.setattr('subprocess.run', mock_run)
        monkeypatch.setattr('glob.glob', lambda p: ['/tmp/kitty-test'])

        # Daemon runs update after new tab opens
        update_tabs(debug=False)

        print(f"Captured titles: {captured_titles_by_tab}")

        # Check tab 1 - should show "dev" since we wrote it to temp file
        if tab1_id in captured_titles_by_tab:
            tab1_title = captured_titles_by_tab[tab1_id]
            print(f"Tab 1 title: {tab1_title}")

            # THE BUG: Tab 1 should show "dev" not "dwalseth"
            assert 'dev' in tab1_title, f"Tab 1 should show 'dev', got: {tab1_title}"
        else:
            pytest.fail(f"Tab 1 (id={tab1_id}) was not updated. This is the bug - it should show 'dev'")

        # Tab 2 should also show "dev"
        if tab2_id in captured_titles_by_tab:
            tab2_title = captured_titles_by_tab[tab2_id]
            print(f"Tab 2 title: {tab2_title}")
            assert 'dev' in tab2_title, f"Tab 2 should show 'dev', got: {tab2_title}"

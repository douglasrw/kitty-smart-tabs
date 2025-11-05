"""Security-focused tests for Smart Tabs."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from smart_tabs import tempfiles
from smart_tabs.core import validate_tab_id, sanitize_title


class TestTempFileSecurity:
    """Test temp file security measures."""

    def test_temp_dir_uses_xdg_runtime_when_available(self, tmp_path):
        """Should use XDG_RUNTIME_DIR when available."""
        xdg_dir = tmp_path / 'xdg_runtime'
        xdg_dir.mkdir()
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(xdg_dir)}):
            temp_dir = tempfiles.get_temp_dir()
            assert str(xdg_dir) in str(temp_dir)
            assert 'kitty-smart-tabs' in str(temp_dir)

    def test_temp_dir_falls_back_to_cache(self):
        """Should fall back to ~/.cache when XDG_RUNTIME_DIR not set."""
        env = os.environ.copy()
        env.pop('XDG_RUNTIME_DIR', None)
        with patch.dict(os.environ, env, clear=True):
            with patch('os.environ', env):
                temp_dir = tempfiles.get_temp_dir()
                assert '.cache/kitty-smart-tabs' in str(temp_dir)

    def test_temp_dir_has_secure_permissions(self, tmp_path):
        """Temp directory should have mode 700."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            temp_dir = tempfiles.get_temp_dir()
            stat = temp_dir.stat()
            # Check owner has rwx, group and others have no access
            assert stat.st_mode & 0o777 == 0o700

    def test_write_cwd_rejects_invalid_tab_id(self):
        """Should reject invalid tab IDs."""
        with pytest.raises(ValueError, match="Invalid tab_id"):
            tempfiles.write_cwd_atomic(-1, "/home/user")

        with pytest.raises(ValueError, match="Invalid tab_id"):
            tempfiles.write_cwd_atomic(0, "/home/user")

        with pytest.raises(ValueError, match="Invalid tab_id"):
            tempfiles.write_cwd_atomic("not_an_int", "/home/user")

    def test_write_cwd_rejects_relative_paths(self):
        """Should reject relative paths."""
        with pytest.raises(ValueError, match="absolute path"):
            tempfiles.write_cwd_atomic(1, "relative/path")

    def test_write_cwd_rejects_empty_cwd(self):
        """Should reject empty CWD."""
        with pytest.raises(ValueError, match="non-empty"):
            tempfiles.write_cwd_atomic(1, "")

    def test_write_cwd_rejects_too_long_paths(self):
        """Should reject paths over 4096 chars."""
        long_path = "/" + "a" * 5000
        with pytest.raises(ValueError, match="too long"):
            tempfiles.write_cwd_atomic(1, long_path)

    def test_write_cwd_creates_file_with_secure_permissions(self, tmp_path):
        """Written files should have mode 600."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            tempfiles.write_cwd_atomic(1, "/home/user/test")
            cwd_file = tempfiles.get_cwd_file_path(1)
            stat = cwd_file.stat()
            # Owner read/write only
            assert stat.st_mode & 0o777 == 0o600

    def test_write_cwd_is_atomic(self, tmp_path):
        """Write should be atomic (no partial reads)."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            # Write a path
            tempfiles.write_cwd_atomic(1, "/home/user/test")
            cwd_file = tempfiles.get_cwd_file_path(1)

            # File should exist and contain complete content
            assert cwd_file.exists()
            assert cwd_file.read_text() == "/home/user/test"

            # No temp files left behind
            temp_dir = tempfiles.get_temp_dir()
            assert len(list(temp_dir.glob('*.tmp'))) == 0

    def test_read_cwd_rejects_invalid_tab_id(self):
        """Should reject invalid tab IDs."""
        assert tempfiles.read_cwd_safe(-1) is None
        assert tempfiles.read_cwd_safe(0) is None
        assert tempfiles.read_cwd_safe("not_an_int") is None

    def test_read_cwd_returns_none_for_nonexistent_file(self):
        """Should return None if file doesn't exist."""
        assert tempfiles.read_cwd_safe(99999) is None

    def test_read_cwd_verifies_file_ownership(self, tmp_path):
        """Should reject files not owned by current user."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            # Write a file
            tempfiles.write_cwd_atomic(1, "/home/user/test")
            cwd_file = tempfiles.get_cwd_file_path(1)

            # Mock stat to return different owner
            original_stat = cwd_file.stat
            def fake_stat():
                s = original_stat()
                # Create a new stat_result with different uid
                import os
                fake_s = os.stat_result((
                    s.st_mode, s.st_ino, s.st_dev, s.st_nlink,
                    99999,  # Different uid
                    s.st_gid, s.st_size, s.st_atime, s.st_mtime, s.st_ctime
                ))
                return fake_s

            with patch.object(Path, 'stat', fake_stat):
                result = tempfiles.read_cwd_safe(1)
                assert result is None

    def test_read_cwd_verifies_permissions(self, tmp_path):
        """Should reject files with insecure permissions."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            # Write a file
            tempfiles.write_cwd_atomic(1, "/home/user/test")
            cwd_file = tempfiles.get_cwd_file_path(1)

            # Make it world-readable (insecure)
            cwd_file.chmod(0o644)

            result = tempfiles.read_cwd_safe(1)
            assert result is None

    def test_read_cwd_rejects_relative_paths(self, tmp_path):
        """Should reject relative paths in file content."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            cwd_file = tempfiles.get_cwd_file_path(1)
            cwd_file.parent.mkdir(parents=True, exist_ok=True)
            cwd_file.write_text("relative/path")
            cwd_file.chmod(0o600)

            result = tempfiles.read_cwd_safe(1)
            assert result is None

    def test_read_cwd_rejects_too_long_content(self, tmp_path):
        """Should reject content over 4096 chars."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            long_path = "/" + "a" * 5000
            cwd_file = tempfiles.get_cwd_file_path(1)
            cwd_file.parent.mkdir(parents=True, exist_ok=True)
            cwd_file.write_text(long_path)
            cwd_file.chmod(0o600)

            result = tempfiles.read_cwd_safe(1)
            assert result is None


class TestInputValidation:
    """Test input validation functions."""

    def test_validate_tab_id_accepts_positive_integers(self):
        """Should accept positive integers."""
        assert validate_tab_id(1) is True
        assert validate_tab_id(100) is True
        assert validate_tab_id(99999) is True

    def test_validate_tab_id_rejects_invalid_values(self):
        """Should reject invalid tab IDs."""
        assert validate_tab_id(0) is False
        assert validate_tab_id(-1) is False
        assert validate_tab_id(-100) is False
        assert validate_tab_id("1") is False
        assert validate_tab_id(1.5) is False
        assert validate_tab_id(None) is False
        assert validate_tab_id([1]) is False

    def test_sanitize_title_removes_control_characters(self):
        """Should remove control characters."""
        title = "test\x00\x01\x1ftitle"
        result = sanitize_title(title)
        assert "\x00" not in result
        assert "\x01" not in result
        assert "\x1f" not in result

    def test_sanitize_title_removes_newlines(self):
        """Should remove newlines."""
        title = "test\ntitle\r\nmore"
        result = sanitize_title(title)
        assert "\n" not in result
        assert "\r" not in result

    def test_sanitize_title_limits_length(self):
        """Should limit title length."""
        long_title = "a" * 500
        result = sanitize_title(long_title, max_length=256)
        assert len(result) == 256

    def test_sanitize_title_handles_empty_input(self):
        """Should handle empty input."""
        assert sanitize_title("") == "untitled"
        assert sanitize_title("   ") == "untitled"

    def test_sanitize_title_preserves_valid_content(self):
        """Should preserve valid printable characters."""
        title = "test: dir [cmd]"
        result = sanitize_title(title)
        assert result == title


class TestCommandInjection:
    """Test for command injection vulnerabilities."""

    def test_kitty_window_id_not_interpolated(self):
        """Shell hooks should not interpolate KITTY_WINDOW_ID into Python code."""
        # Read shell hooks and verify they don't use direct interpolation
        zsh_hook = Path(__file__).parent.parent / 'shell_hooks' / 'zsh.sh'
        bash_hook = Path(__file__).parent.parent / 'shell_hooks' / 'bash.sh'

        for hook_file in [zsh_hook, bash_hook]:
            if hook_file.exists():
                content = hook_file.read_text()
                # Should use os.environ instead of direct interpolation
                assert 'os.environ' in content
                # Should NOT have $KITTY_WINDOW_ID inside Python string
                assert 'window_id = $KITTY_WINDOW_ID' not in content

    def test_tab_id_validation_in_subprocess_calls(self):
        """Tab IDs should be validated before subprocess calls."""
        from smart_tabs.core import update_tabs

        # Mock subprocess and kitty @ ls to return malicious tab ID
        with patch('smart_tabs.core.subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = '[{"tabs": [{"id": "1; rm -rf /", "windows": [{"cwd": "/tmp"}]}]}]'
            mock_run.return_value = mock_result

            # Should not raise exception, should handle gracefully
            update_tabs(debug=False)

            # Verify no subprocess calls were made with malicious ID
            for call in mock_run.call_args_list[1:]:  # Skip the ls call
                args = call[0][0]
                for arg in args:
                    assert "rm -rf" not in str(arg)


class TestPathTraversal:
    """Test for path traversal vulnerabilities."""

    def test_cwd_path_validation(self, tmp_path):
        """CWD paths should be validated."""
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(tmp_path)}):
            # Should reject path traversal attempts
            with pytest.raises(ValueError):
                tempfiles.write_cwd_atomic(1, "../../etc/passwd")

            with pytest.raises(ValueError):
                tempfiles.write_cwd_atomic(1, "/tmp/../../../etc/passwd")

    def test_temp_file_path_validation(self):
        """Temp file paths should not allow traversal."""
        # Tab ID should be validated to prevent path traversal
        with pytest.raises(ValueError):
            tempfiles.get_cwd_file_path("../etc/passwd")

        with pytest.raises(ValueError):
            tempfiles.get_cwd_file_path(-1)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

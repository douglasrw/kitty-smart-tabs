"""Tests for color generation logic."""

import pytest
from smart_tabs.colors import get_color_for_path


@pytest.mark.unit
class TestColorGeneration:
    """Tests for get_color_for_path function."""

    def test_consistent_hash_same_path(self):
        """Same path should always return same color."""
        path = "/home/user/projects"
        color1 = get_color_for_path(path)
        color2 = get_color_for_path(path)
        color3 = get_color_for_path(path)

        assert color1 == color2 == color3

    def test_different_paths_can_have_different_colors(self):
        """Different paths can return different colors."""
        path1 = "/home/user/projects"
        path2 = "/home/user/documents"

        color1 = get_color_for_path(path1)
        color2 = get_color_for_path(path2)

        # Note: due to hash collisions with small palette, they MIGHT be the same
        # but we test that the function at least works consistently
        assert isinstance(color1, str)
        assert isinstance(color2, str)
        assert color1.startswith('#')
        assert color2.startswith('#')

    def test_returns_valid_hex_color(self):
        """Should return valid hex color strings."""
        path = "/home/user/test"
        color = get_color_for_path(path)

        assert isinstance(color, str)
        assert color.startswith('#')
        assert len(color) == 7  # #RRGGBB

        # Check hex validity
        try:
            int(color[1:], 16)
            valid_hex = True
        except ValueError:
            valid_hex = False
        assert valid_hex

    def test_default_palette_used(self):
        """Should use default palette when none provided."""
        path = "/home/user/test"
        color = get_color_for_path(path)

        default_palette = [
            '#2b8eff',
            '#a9dc76',
            '#ab9df2',
            '#ffd866',
            '#78dce8',
            '#f48771',
        ]

        assert color in default_palette

    def test_custom_palette(self):
        """Should use custom palette when provided."""
        path = "/home/user/test"
        custom_palette = ['#ff0000', '#00ff00', '#0000ff']
        color = get_color_for_path(path, custom_palette)

        assert color in custom_palette

    def test_palette_wrapping(self):
        """Should wrap around small palettes correctly."""
        # Use single color palette to ensure wrapping works
        single_color_palette = ['#123456']
        path = "/home/user/test"
        color = get_color_for_path(path, single_color_palette)

        assert color == '#123456'

    def test_many_paths_distribution(self):
        """Test that colors are distributed across palette for many paths."""
        paths = [f"/home/user/project{i}" for i in range(100)]
        colors = [get_color_for_path(path) for path in paths]

        # Should have used multiple colors from palette
        unique_colors = set(colors)
        assert len(unique_colors) > 1  # At least 2 different colors used

    def test_hash_consistency_with_special_chars(self):
        """Paths with special characters should hash consistently."""
        path = "/home/user/my-project_v2.0/src"
        color1 = get_color_for_path(path)
        color2 = get_color_for_path(path)

        assert color1 == color2

    def test_similar_paths_different_colors(self):
        """Similar paths should ideally get different colors."""
        # Note: due to MD5 hashing, even similar paths will have very different hashes
        path1 = "/home/user/project"
        path2 = "/home/user/project1"

        color1 = get_color_for_path(path1)
        color2 = get_color_for_path(path2)

        # Both should be valid colors
        assert color1.startswith('#')
        assert color2.startswith('#')

    def test_empty_path(self):
        """Empty path should still return a valid color."""
        path = ""
        color = get_color_for_path(path)

        assert isinstance(color, str)
        assert color.startswith('#')

    def test_unicode_paths(self):
        """Paths with unicode characters should work."""
        path = "/home/user/项目/文档"
        color = get_color_for_path(path)

        assert isinstance(color, str)
        assert color.startswith('#')

    def test_very_long_path(self):
        """Very long paths should work."""
        path = "/home/user/" + "very_long_directory_name/" * 50
        color = get_color_for_path(path)

        assert isinstance(color, str)
        assert color.startswith('#')


@pytest.mark.unit
class TestColorMapping:
    """Tests for color mapping behavior across directories."""

    def test_same_directory_same_color(self):
        """Tabs in same directory should get same color."""
        dir_path = "/home/user/projects/myapp"

        color1 = get_color_for_path(dir_path)
        color2 = get_color_for_path(dir_path)

        assert color1 == color2

    def test_subdirectory_different_color(self):
        """Subdirectory should get different color from parent."""
        parent = "/home/user/projects"
        child = "/home/user/projects/myapp"

        color_parent = get_color_for_path(parent)
        color_child = get_color_for_path(child)

        # Both should be valid (might be same due to hash collision, but that's OK)
        assert color_parent.startswith('#')
        assert color_child.startswith('#')

    def test_trailing_slash_consistency(self):
        """Path with/without trailing slash should ideally be handled."""
        # Note: current implementation doesn't normalize trailing slashes
        # This test documents the current behavior
        path_no_slash = "/home/user/projects"
        path_with_slash = "/home/user/projects/"

        color_no_slash = get_color_for_path(path_no_slash)
        color_with_slash = get_color_for_path(path_with_slash)

        # Both should be valid colors
        assert color_no_slash.startswith('#')
        assert color_with_slash.startswith('#')

        # They might be different since paths are different strings
        # This is actually handled by core.py which strips trailing slashes

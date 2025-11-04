"""Color generation for tab directories."""

import hashlib


def get_color_for_path(path, color_palette=None):
    """Generate consistent color based on path hash.

    Args:
        path: Directory path string
        color_palette: Optional list of hex colors. Uses default if None.

    Returns:
        Hex color string (e.g., '#2b8eff')
    """
    if color_palette is None:
        color_palette = [
            '#2b8eff',  # blue
            '#a9dc76',  # green
            '#ab9df2',  # magenta
            '#ffd866',  # yellow
            '#78dce8',  # cyan
            '#f48771',  # red
        ]

    hash_val = int(hashlib.md5(path.encode()).hexdigest(), 16)
    return color_palette[hash_val % len(color_palette)]

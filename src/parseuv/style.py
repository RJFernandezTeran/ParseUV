"""
Plotting style manager for parseUV.

Applies Matplotlib style files (.mplstyle) configured with TeX Gyre Heros,
Helvetica, and Arial fonts, custom label sizes, tick pad settings, and line styling.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib.pyplot as plt

_STYLES_DIR = Path(__file__).resolve().parent / "plot_styles"

_PROFILE_FILES = {
    "regular": "HLV_plt.mplstyle",
}


def get_style_path(profile: str = "regular") -> Path:
    """Returns the absolute path to the regular .mplstyle file."""
    profile_lower = profile.lower()
    filename = _PROFILE_FILES.get(profile_lower, "HLV_plt.mplstyle")
    path = _STYLES_DIR / filename
    if not path.exists():
        path = _STYLES_DIR / "HLV_plt.mplstyle"
    return path


def apply_style(profile: str = "regular", custom_style_path: str | None = None) -> None:
    """
    Applies the regular matplotlib style profile.

    Args:
        profile (str): Style profile name ('regular').
        custom_style_path (str, optional): Custom path to a .mplstyle file.
    """
    if custom_style_path and os.path.exists(custom_style_path):
        target_path = Path(custom_style_path)
    else:
        target_path = get_style_path(profile)

    if target_path.exists():
        plt.style.use(str(target_path))

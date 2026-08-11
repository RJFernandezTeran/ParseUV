"""
Font installation helper for parseUV.

Locates TeX Gyre Heros fonts from a MiKTeX or TeX Live installation and
copies them into Matplotlib's font directory, then clears the font cache.

Usage
-----
From command line::

    parseuv-install-fonts

Or from Python::

    from parseuv.fonts import install_fonts
    install_fonts()
"""

from __future__ import annotations

import shutil
from functools import cache
from pathlib import Path

# Preferred fonts, in priority order.
PREFERRED_FONTS = ["TeX Gyre Heros", "Helvetica", "Arial"]


@cache
def available_preferred_fonts() -> list[str]:
    """Return which of PREFERRED_FONTS Matplotlib can currently resolve."""
    import matplotlib.font_manager as fm

    available = {f.name for f in fm.fontManager.ttflist}
    return [name for name in PREFERRED_FONTS if name in available]


def _find_miktex_heros() -> list[Path]:
    """Search common MiKTeX / TeX Live locations for TeX Gyre Heros font files."""
    home = Path.home()
    search_roots = [
        # MiKTeX - system-wide and per-user
        Path(r"C:\Program Files\MiKTeX"),
        Path(r"C:\Program Files (x86)\MiKTeX"),
        home / "AppData" / "Local" / "Programs" / "MiKTeX",
        home / "AppData" / "Roaming" / "MiKTeX",
        # TeX Live - common install paths
        Path(r"C:\texlive"),
        Path("/usr/share/texmf"),
        Path("/usr/local/texlive"),
        home / "texlive",
    ]
    patterns = ["**/texgyreheros-*.otf", "**/texgyreheros-*.ttf"]
    found: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        for pattern in patterns:
            found.extend(root.glob(pattern))
    return found


def install_fonts() -> None:
    """Copy TeX Gyre Heros fonts into Matplotlib's font directory and clear the cache."""
    import matplotlib
    import matplotlib.font_manager as fm

    fonts = _find_miktex_heros()
    if not fonts:
        print(
            "No TeX Gyre Heros fonts found.\n"
            "Check that MiKTeX or TeX Live is installed, then re-run:\n"
            "    parseuv-install-fonts"
        )
        return

    mpl_font_dir = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    print(f"Installing to: {mpl_font_dir}")

    for src in fonts:
        dst = mpl_font_dir / src.name
        shutil.copy2(src, dst)
        print(f"  Copied: {src.name}")

    # Clear font cache so Matplotlib picks up the new files.
    cache_dir = Path(matplotlib.get_cachedir())
    for f in cache_dir.glob("fontlist-*.json"):
        try:
            f.unlink()
            print(f"  Deleted cache: {f.name}")
        except Exception as e:
            print(f"  Could not delete cache {f.name}: {e}")

    # Rebuild in this session.
    fm._load_fontmanager(try_read_cache=False)
    available_preferred_fonts.cache_clear()

    found = [f.name for f in fm.fontManager.ttflist if "Heros" in f.name]
    if found:
        print(f"\nSuccess - Matplotlib now sees: {found}")
    else:
        print("\nFonts copied but not yet detected. Restart your Python session.")


def main() -> None:
    install_fonts()


if __name__ == "__main__":
    main()

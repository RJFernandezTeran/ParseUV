"""
parseuv - A Python library for reading Varian/Agilent Cary (.DSW, .BSW) and Shimadzu (.SPC) binary spectrometer files.
"""

from .__about__ import __author__, __email__, __version__
from .batch import batch_process_folder, process_file
from .fonts import install_fonts
from .gui import launch_gui
from .parser import CaryFile, parse_uv, read_cary, read_uv
from .spectrum import Spectrum
from .style import apply_style

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "parse_uv",
    "read_uv",
    "read_cary",
    "CaryFile",
    "Spectrum",
    "batch_process_folder",
    "process_file",
    "launch_gui",
    "apply_style",
    "install_fonts",
]

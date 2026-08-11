# parseUV

[![PyPI version](https://img.shields.io/pypi/v/parseuv.svg)](https://pypi.org/project/parseuv/)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](LICENSE)

A Python package and PyQt6 GUI application for reading, visualizing, and exporting proprietary binary files from:
- **Varian / Agilent Cary** UV-Vis-NIR spectrophotometers (`.DSW`, `.BSW`)
- **Shimadzu** UV-Vis-NIR spectrophotometers (`.SPC`)

---

## Features

- **Direct Binary Parsing**: Reads proprietary `.DSW`, `.BSW`, and `.SPC` files natively in Python without requiring proprietary software.
- **Drag-and-Drop PyQt6 GUI**: Interactive desktop GUI app with Matplotlib plotting widgets, sample/background spectrum categorization, CSV export, and instant reset.
- **Batch Processing Tool**: Command-line and programmatic batch processor to convert all spectrometer files in a directory to CSV and high-resolution plots (`.png`, `.pdf`, `.svg`).
- **Publication-Ready Styling**: Includes custom `.mplstyle` profile styled with **TeX Gyre Heros**, **Helvetica**, and **Arial** fonts.
- **Font Installer**: Automated helper script (`parseuv-install-fonts`) to discover and register TeX Gyre Heros fonts from MiKTeX or TeX Live into Matplotlib.
- **Pandas Integration**: Converts spectra into clean `pandas.DataFrame` objects aligned by wavelength.

---

## Supported Formats

| Manufacturer | Instrument | File Extensions | Description |
| :--- | :--- | :--- | :--- |
| **Varian / Agilent** | Cary 50 / UV-Vis-NIR | `.DSW`, `.BSW` | Single spectrum (`.DSW`) and batch spectra (`.BSW`) binary files |
| **Shimadzu** | UVProbe / UV-Vis-NIR | `.SPC` | OLE2 Compound binary container (`.SPC`) and Galactic GRAMS binary files |

---

## Installation

The package is available on [PyPI](https://pypi.org/project/parseuv/).

### Using `pip`

```bash
pip install parseuv
```

### Using `uv` (Recommended)

```bash
uv add parseuv
```

### Development Install (from source)

```bash
git clone https://github.com/RJFernandezTeran/ParseUV.git
cd ParseUV
uv pip install -e .
```

Or with standard pip:

```bash
pip install -e .
```

---

## Font & Style Configuration

### 1. Install TeX Gyre Heros Fonts (Optional, Recommended)

To install TeX Gyre Heros fonts into Matplotlib's font manager from a local MiKTeX or TeX Live installation:

```bash
parseuv-install-fonts
```

Or from Python:

```python
from parseuv.fonts import install_fonts

install_fonts()
```

### 2. Apply Custom Plotting Style

```python
from parseuv import apply_style, parse_uv

# Apply the regular style profile (TeX Gyre Heros / Helvetica / Arial)
apply_style("regular")

data = parse_uv("path/to/file.DSW")
data.plot()
```

Available style profile:
- `'regular'` (`HLV_plt.mplstyle`): Regular publication profile (18pt bold labels, sans-serif fonts).

---

## Usage

### 1. PyQt6 Drag-and-Drop GUI

Launch the interactive desktop GUI application:

```bash
parseuv-gui
# or
python run_gui.py
# or
parseuv --gui
```

Features:
- Drag and drop `.BSW`, `.DSW`, or `.SPC` files into the drop zone.
- File selection dialog filter: `Varian/Agilent Cary (*.DSW, *.BSW)` or `Shimadzu UV-Vis-NIR (*.SPC)`.
- 2-row subplot layout with 3:1 height ratio (main absorption spectra vs baselines).
- **Export Spectra as CSV**: Exports sample spectra to a `CSV/` subfolder.
- **Export Background as CSV**: Exports background/baseline recordings.
- **Reset**: Clears all data and returns to the drop zone.

---

### 2. Python API

```python
from parseuv import parse_uv, apply_style

apply_style("regular")

# Read a single Varian Cary spectrum file (.DSW)
cary_file = parse_uv("path/to/file.DSW")
print(cary_file)  # <CaryFile 'file.DSW' (DSW) | 1 spectra>

# Read a Shimadzu spectrum file (.SPC)
spc_file = parse_uv("path/to/file.spc")
print(spc_file)  # <CaryFile 'file.spc' (SPC) | 1 spectra>

spectrum = spc_file[0]
print(spectrum.title)  # 'Sample Title'
print(spectrum.num_points)  # 601
print(spectrum.start_wavelength)  # 800.0
print(spectrum.end_wavelength)  # 200.0

# Export to CSV
spc_file.to_csv("spectrum.csv")

# Read a batch spectrum file (.BSW)
cary_bsw = parse_uv("path/to/file.BSW")
df = cary_bsw.to_dataframe()
print(df.head())

# Plot all spectra automatically
cary_bsw.plot(save_path="spectra.png")
```

#### Manually Plotting a Specific Spectrum from a Multi-Spectrum File

To manually extract the X (wavelengths) and Y (absorbances) coordinates, title, and metadata for custom plotting:

```python
import matplotlib.pyplot as plt
from parseuv import apply_style, parse_uv

# Apply regular publication plot style
apply_style("regular")

# Read a multi-spectrum file (.BSW or batch .SPC)
cary_bsw = parse_uv("path/to/file.BSW")

# Select a specific spectrum by index (e.g. 0) or by title
spectrum = cary_bsw[0]  # or cary_bsw["Spectrum Title"]

# Get X (wavelengths in nm) and Y (absorbance) arrays directly
x_wavelengths = spectrum.wavelengths  # 1D numpy array
y_absorbances = spectrum.absorbances  # 1D numpy array
title = spectrum.title
metadata = spectrum.metadata

print(f"Plotting '{title}' with {spectrum.num_points} data points.")

# Custom plot using Matplotlib
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(x_wavelengths, y_absorbances, label=title, color="#1f77b4", linewidth=2.0)
ax.set_xlabel("Wavelength (nm)", fontweight="bold")
ax.set_ylabel("Absorbance", fontweight="bold")
ax.set_title(f"Manual Plot: {title}", fontweight="bold")
ax.legend(loc="best")
plt.tight_layout()
plt.savefig("manual_spectrum_plot.png", dpi=300)
plt.show()
```

---

### 3. Batch Processing Tool

Process an entire folder of `.BSW`, `.DSW`, and `.SPC` files:

```bash
python batch_process.py path/to/folder -f png
```

Or interactively select format (`png`, `pdf`, `svg`):

```bash
python batch_process.py
```

Outputs are automatically organized into format-specific subfolders:
- `CSV/`
- `PNG/` (or `PDF/`, `SVG/`)

---

### 4. Command Line Interface (CLI)

```bash
# Convert a single binary file to CSV and PNG plot
parseuv path/to/file.spc -o output.csv -p plot.png

# Run batch mode on a directory
parseuv --batch path/to/folder -f pdf
```

---

## Technical Specifications

### 1. Varian / Agilent Cary Binary Format (`.DSW`, `.BSW`)

Supports both standard fixed-step Cary files and newer **Cary WinUV version 3.00+** `.DSW` (single spectrum) and `.BSW` (batch spectra) binary files:

- **Header Magic**: Starts at offset `0x00` with the Pascal string `Varian UV-VIS-NIR` (length byte `0x11` = 17 followed by ASCII text `Varian UV-VIS-NIR`).
- **Global Header**: Offset `0x5D..0x71` contains legacy initial start wavelength (`float32`), end wavelength (`float32`), and total point count (`int32`).
- **Text Metadata Blocks**:
  - Located `256 bytes` prior to each spectral data stream (`data_offset - 256`).
  - Contains null-terminated ASCII parameters: `Sample Title`, `Collection Time` / `Date/Time stamp`, `Scan Software Version` (e.g. `Scan Software Version: 3.00(182)`), `Instrument` (e.g. `Cary 50`), `Start (nm)` and `Stop (nm)`, `UV-Vis Scan Rate (nm/min)`, `UV-Vis Data Interval (nm)`, and `Baseline Correction` parameters.
- **Spectral Data Points Stream**:
  - Sequential 8-byte little-endian IEEE `float32` pairs: `(wavelength_nm, absorbance)`.
  - **Wavelength Encoding Variants**:
    - **Arithmetic Fixed Step**: Exact arithmetic integer or fractional steps (e.g., `-1.0 nm`, `-0.5 nm`, `+1.0 nm`).
    - **Empirical Monochromator Encoder Values (WinUV v3.00+)**: Hardware monochromator encoder readings per point (e.g., `799.998`, `799.026`, `798.053`, ..., `199.968 nm`) accounting for physical motor positioning tolerances.
  - **Variable Sampling Intervals**: Supports standard step sizes (`0.05`, `0.1`, `0.5`, `1.0`, `2.0 nm`) as well as fast custom sampling intervals (up to `25.0 nm` interval, e.g., `5.0 nm` step yielding `121` points from `800` to `200 nm`).
  - **Sweep Direction & Bounds**: Supports decreasing (`start > stop`) and increasing (`start < stop`) wavelength sweeps between `190.0` and `1100.0 nm`.

### 2. Shimadzu Binary Format (`.SPC`)

- **OLE2 Compound Document Container**: Microsoft OLE2 Compound Container (`0xD0CF11E0A1B11AE1`) generated by Shimadzu UVProbe software.
- **Data Streams**: Extracts streams `DataSpectrumStorage/Data/X Data.N` (wavelengths) and `Y Data.N` (absorbances) stored as 64-bit IEEE `float64` (`double`) arrays.
- **Galactic GRAMS SPC Fallback**: Direct parsing of Galactic SPC headers (version `0x4B` / `0x4D`) reading `fnpts`, `ffirst`, `flast`, and `float32` absorbance arrays.

---

## Code Quality & Development

Format and lint code using `ruff`:

```bash
uv run ruff format .
uv run ruff check .
```

Run test suite:

```bash
uv run pytest
```

---

## Author & License

- **Author**: Dr. Ricardo J. Fernández-Terán
- **Contact**: ricardo.fernandezteran[at]unige.ch
- **License**: Distributed under the **BSD 3-Clause License**. See [`LICENSE`](LICENSE) for details.

---

## Acknowledgements

Special thanks and acknowledgement to **SpectraGryph** (optical spectroscopy software developed by Dr. Friedrich Menges, [effemm2.de/spectragryph/](https://www.effemm2.de/spectragryph/)) for serving as an explicit inspiration for format discovery, conversion workflows, and spectroscopy tooling design.

Copyright (c) 2026, Dr. Ricardo J. Fernández-Terán.

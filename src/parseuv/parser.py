"""
Binary parser for Varian / Agilent Cary 50 (.DSW, .BSW) and Shimadzu UV-Vis-NIR (.SPC) files.
"""

import os
import struct
from typing import Any, Optional, Union

import olefile
import pandas as pd

from .spectrum import Spectrum


class CaryFile:
    """
    Parser for Varian / Agilent Cary (.DSW, .BSW) and Shimadzu UV-Vis-NIR (.SPC) binary files.

    Supports legacy fixed-step Cary files as well as newer Cary WinUV (v3.00+) files with:
      - Empirical hardware monochromator encoder wavelength arrays (e.g. 799.998, 799.026 nm)
      - Variable data sampling intervals (from 0.05 nm up to 25.0 nm intervals)
      - Embedded 256-byte ASCII metadata blocks preceding spectral data runs
      - Shimadzu OLE2 Compound File Binary Containers (.SPC) and Galactic GRAMS SPC binaries

    Attributes:
        filepath (str): Absolute path to the binary spectrometer file.
        file_type (str): Format type ('DSW', 'BSW', or 'SPC').
        header (dict): Extracted header metadata (magic, instrument, software, date/time, scan rate).
        spectra (List[Spectrum]): List of parsed Spectrum objects.
    """

    def __init__(self, filepath: str):
        self.filepath = os.path.abspath(filepath)
        if not os.path.isfile(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")

        ext = os.path.splitext(self.filepath)[1].upper()
        if ext == ".BSW":
            self.file_type = "BSW"
        elif ext == ".DSW":
            self.file_type = "DSW"
        elif ext == ".SPC":
            self.file_type = "SPC"
        else:
            self.file_type = "CARY"

        with open(self.filepath, "rb") as f:
            self._data = f.read()

        if self.file_type == "SPC" or self._data.startswith(b"\xd0\xcf\x11\xe0"):
            self.file_type = "SPC"
            self.header = {
                "magic": "Shimadzu SPC / OLE2",
                "filepath": self.filepath,
                "filename": os.path.basename(self.filepath),
                "file_type": "SPC",
            }
            self.spectra = self._parse_spc_file()
        else:
            self.header = self._parse_header()
            self.spectra = self._parse_spectra()

    def _extract_cary_text_metadata(self, data: bytes) -> dict[str, Any]:
        """Extracts acquisition date, software version, instrument model, scan rate, and slit width from Cary files."""
        import re

        meta: dict[str, Any] = {}
        ascii_blocks = [
            x.decode("ascii", errors="ignore").strip() for x in re.findall(b"[\x20-\x7e]{4,}", data)
        ]

        for item in ascii_blocks:
            if "Scan Rate (nm/min)" in item:
                val = item.split("Scan Rate (nm/min)")[-1].strip(" .\t\r\n")
                m_val = re.search(r"[\d\.]+", val)
                if m_val:
                    meta["scan_rate"] = f"{float(m_val.group(0)):.2f} nm/min"
            elif "Ave. Time (sec)" in item or "Average Time (sec)" in item:
                val = item.split("(sec)")[-1].strip(" .\t\r\n")
                m_val = re.search(r"[\d\.]+", val)
                if m_val:
                    meta["ave_time"] = f"{float(m_val.group(0)):.4f} s"
            elif "SBW (nm)" in item:
                val = item.split("SBW (nm)")[-1].strip(" .\t\r\n")
                m_val = re.search(r"[\d\.]+", val)
                if m_val:
                    meta["sbw"] = f"{float(m_val.group(0)):.2f} nm"
                    meta["slit_width"] = meta["sbw"]
            elif item.startswith("Instrument") and "Cary" in item:
                val = item.replace("Instrument", "").strip(" .\t\r\n")
                if val:
                    meta["instrument"] = val
            elif "Date/Time stamp:" in item:
                val = item.split("Date/Time stamp:")[-1].strip(" .\t\r\n")
                if val:
                    meta["date_time"] = val
            elif not meta.get("date_time"):
                m = re.search(
                    r"\b\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s+[AP]M)?)?\b",
                    item,
                )
                if m:
                    meta["date_time"] = m.group(0)

        if not meta.get("instrument"):
            if b"Cary 5000" in data:
                meta["instrument"] = "Cary 5000"
            elif b"Cary 50" in data:
                meta["instrument"] = "Cary 50"
            elif b"Cary" in data:
                meta["instrument"] = "Varian Cary"

        meta["software"] = "Varian Cary WinUV"
        return meta

    def _parse_header(self) -> dict[str, Any]:
        """Validates the file magic bytes and extracts default parameters for Cary files."""
        if len(self._data) < 18:
            raise ValueError(
                f"File too small to be a valid Cary spectrometer file: {self.filepath}"
            )

        str_len = self._data[0]
        magic = self._data[1 : 1 + str_len].decode("ascii", errors="ignore")
        if not magic.startswith("Varian UV-VIS"):
            raise ValueError(
                f"Invalid file format (header magic: '{magic}'). Expected 'Varian UV-VIS...'."
            )

        start_w, end_w, n_pts = None, None, None
        try:
            v1 = struct.unpack("<f", self._data[0x5D:0x61])[0]
            v2 = struct.unpack("<f", self._data[0x61:0x65])[0]
            v3 = struct.unpack("<i", self._data[0x6D:0x71])[0]
            if 190 <= v1 <= 1100 and 190 <= v2 <= 1100 and 1 <= v3 <= 10000:
                end_w, start_w, n_pts = v1, v2, v3
        except Exception:
            pass

        step_size = None
        sweep_direction = None
        if start_w is not None and end_w is not None and n_pts and n_pts > 1:
            step_size = (end_w - start_w) / (n_pts - 1)
            sweep_direction = "Decreasing" if end_w < start_w else "Increasing"

        scan_mode = (
            "Continuous Wavelength Sweep (TContinuumStore)"
            if b"TContinuumStore" in self._data
            else "Wavelength Scan"
        )

        header_dict = {
            "magic": magic,
            "filepath": self.filepath,
            "filename": os.path.basename(self.filepath),
            "file_type": self.file_type,
            "scan_mode": scan_mode,
            "default_start_wavelength": start_w,
            "default_end_wavelength": end_w,
            "default_num_points": n_pts,
            "default_step_size": step_size,
            "sweep_direction": sweep_direction,
        }
        cary_text_meta = self._extract_cary_text_metadata(self._data)
        header_dict.update(cary_text_meta)
        return header_dict

    def _parse_spectra(self) -> list[Spectrum]:
        """
        Scans the binary stream for Cary spectral data blocks and metadata headers.

        Handles both fixed arithmetic wavelength steps and empirical monochromator encoder
        wavelength arrays across variable sampling intervals (0.01 nm to 25.0 nm step sizes).
        """
        data = self._data
        blocks = []

        i = 0
        while i <= len(data) - 16:
            w0, y0 = struct.unpack("<ff", data[i : i + 8])
            w1, y1 = struct.unpack("<ff", data[i + 8 : i + 16])

            dw = w1 - w0
            # Valid wavelength range between 190 and 1100 nm, step between 0.01 and 25.0 nm
            if (
                190.0 <= w0 <= 1100.0
                and 190.0 <= w1 <= 1100.0
                and (0.01 <= abs(dw) <= 25.0)
                and (-10.0 <= y0 <= 100.0)
                and (-10.0 <= y1 <= 100.0)
            ):
                pts_w = [round(w0, 3), round(w1, 3)]
                pts_y = [y0, y1]
                curr = i + 16
                is_decreasing = dw < 0

                while curr + 8 <= len(data):
                    cw, cy = struct.unpack("<ff", data[curr : curr + 8])
                    prev_w = pts_w[-1]
                    step = cw - prev_w

                    if 190.0 <= cw <= 1100.0 and -10.0 <= cy <= 1000.0:
                        if is_decreasing and (-30.0 <= step <= -0.001):
                            pts_w.append(round(cw, 3))
                            pts_y.append(cy)
                            curr += 8
                        elif (not is_decreasing) and (0.001 <= step <= 30.0):
                            pts_w.append(round(cw, 3))
                            pts_y.append(cy)
                            curr += 8
                        else:
                            break
                    else:
                        break

                if len(pts_w) >= 30:
                    title = f"Spectrum_{len(blocks) + 1}"
                    title_offset = i - 256
                    if title_offset >= 0:
                        try:
                            raw_slice = data[title_offset : title_offset + 128]
                            null_idx = raw_slice.find(b"\x00")
                            raw_title = raw_slice[:null_idx] if null_idx != -1 else raw_slice
                            if all(32 <= b <= 126 for b in raw_title):
                                s = raw_title.decode("ascii").strip()
                                if s and any(c.isalnum() for c in s):
                                    title = s
                        except Exception:
                            pass

                    blocks.append(
                        {
                            "title": title,
                            "offset": i,
                            "end_offset": curr,
                            "num_points": len(pts_w),
                            "start_wavelength": pts_w[0],
                            "end_wavelength": pts_w[-1],
                            "wavelengths": pts_w,
                            "absorbances": pts_y,
                        }
                    )
                    i = curr - 1
            i += 1

        unique_blocks = []
        for b in sorted(blocks, key=lambda x: x["offset"]):
            if not unique_blocks:
                unique_blocks.append(b)
            else:
                prev = unique_blocks[-1]
                if b["offset"] < prev["end_offset"]:
                    if b["num_points"] > prev["num_points"]:
                        unique_blocks[-1] = b
                else:
                    unique_blocks.append(b)

        spectra_list = []
        title_counts: dict[str, int] = {}
        for b in unique_blocks:
            t = b["title"]
            if t in title_counts:
                title_counts[t] += 1
                unique_title = f"{t}_{title_counts[t]}"
            else:
                title_counts[t] = 1
                unique_title = t

            step_s = (
                (b["end_wavelength"] - b["start_wavelength"]) / (b["num_points"] - 1)
                if b["num_points"] > 1
                else 0.0
            )
            sweep_dir = (
                "Decreasing" if b["end_wavelength"] < b["start_wavelength"] else "Increasing"
            )
            scan_m = (
                "Continuous Wavelength Sweep (TContinuumStore)"
                if b"TContinuumStore" in self._data
                else "Wavelength Scan"
            )

            spec_meta = {
                "file_offset": b["offset"],
                "data_bytes": (b["end_offset"] - b["offset"]),
                "start_wavelength": b["start_wavelength"],
                "end_wavelength": b["end_wavelength"],
                "num_points": b["num_points"],
                "step_size": step_s,
                "sweep_direction": sweep_dir,
                "scan_mode": scan_m,
                "min_absorbance": float(min(b["absorbances"])),
                "max_absorbance": float(max(b["absorbances"])),
                "file_type": self.file_type,
            }
            spec_meta.update(self.header)

            spectrum = Spectrum(
                title=unique_title,
                wavelengths=b["wavelengths"],
                absorbances=b["absorbances"],
                metadata=spec_meta,
            )
            spectra_list.append(spectrum)

        return spectra_list

    def _extract_spc_ole_metadata(self, ole: olefile.OleFileIO) -> dict[str, Any]:
        """Extracts instrumental methods, properties, and header metadata from Shimadzu OLE2 files."""
        import re

        metadata: dict[str, Any] = {}
        method_props: dict[str, str] = {}
        header_info: list[str] = []

        try:
            for s in ole.listdir():
                path = "/".join(s)
                if "DataSetHeaderInfo" in path:
                    try:
                        data = ole.openstream(path).read()
                        matches = [
                            x.decode("ascii", errors="ignore").strip()
                            for x in re.findall(b"[\x20-\x7e]{2,}", data)
                            if x.decode("ascii", errors="ignore").strip()
                        ]
                        header_info.extend(matches)
                    except Exception:
                        pass
                elif "MethodStorage/PageTexts" in path:
                    try:
                        data = ole.openstream(path).read()
                        matches = [
                            x.decode("ascii", errors="ignore").strip()
                            for x in re.findall(b"[\x20-\x7e]{2,}", data)
                            if x.decode("ascii", errors="ignore").strip()
                        ]
                        i = 0
                        while i < len(matches):
                            item = matches[i]
                            if item.endswith(":") and (i + 1) < len(matches):
                                val = matches[i + 1]
                                if not val.startswith("[") and not val.endswith(":"):
                                    key = item[:-1].strip()
                                    method_props[key] = val
                                    i += 1
                            i += 1
                    except Exception:
                        pass
                elif "DataSetHistory" in path:
                    try:
                        data = ole.openstream(path).read()
                        hist = [
                            x.decode("ascii", errors="ignore").strip()
                            for x in re.findall(b"[\x20-\x7e]{3,}", data)
                            if x.decode("ascii", errors="ignore").strip()
                        ]
                        if hist:
                            metadata["history"] = hist
                    except Exception:
                        pass
        except Exception:
            pass

        if method_props:
            metadata["method_properties"] = method_props
            for k, v in method_props.items():
                clean_key = (
                    k.lower().replace(" ", "_").replace(".", "").replace("(", "").replace(")", "")
                )
                metadata[clean_key] = v

        if header_info:
            metadata["header_info"] = header_info

        return metadata

    def _parse_spc_file(self) -> list[Spectrum]:
        """Parses Shimadzu OLE2 Compound (.SPC) files and Galactic GRAMS (.SPC) binary files."""
        # 1. Try OLE2 Compound Storage Format (Shimadzu UVProbe)
        if self._data.startswith(b"\xd0\xcf\x11\xe0"):
            try:
                ole = olefile.OleFileIO(self.filepath)
                ole_meta = self._extract_spc_ole_metadata(ole)
                self.header.update(ole_meta)

                streams = ["/".join(s) for s in ole.listdir()]

                dataset_paths = set()
                for s in streams:
                    if "DataSpectrumStorage/Data/X Data." in s:
                        prefix = s.split("DataSpectrumStorage/Data/X Data.")[0]
                        num = s.split("DataSpectrumStorage/Data/X Data.")[1]
                        dataset_paths.add((prefix, num))

                if dataset_paths:
                    spectra = []
                    base_name = os.path.splitext(os.path.basename(self.filepath))[0]

                    for _idx, (prefix, num) in enumerate(sorted(dataset_paths), 1):
                        x_stream_name = f"{prefix}DataSpectrumStorage/Data/X Data.{num}"
                        y_stream_name = f"{prefix}DataSpectrumStorage/Data/Y Data.{num}"

                        title = base_name if len(dataset_paths) == 1 else f"{base_name}_{num}"

                        x_data = ole.openstream(x_stream_name).read()
                        y_data = ole.openstream(y_stream_name).read()

                        n_x = len(x_data) // 8
                        n_y = len(y_data) // 8

                        x_vals = list(struct.unpack(f"<{n_x}d", x_data[: n_x * 8]))
                        y_vals = list(struct.unpack(f"<{n_y}d", y_data[: n_y * 8]))

                        spec_meta = {
                            "stream_index": num,
                            "file_type": "Shimadzu_SPC",
                            "start_wavelength": float(x_vals[0]) if x_vals else 0.0,
                            "end_wavelength": float(x_vals[-1]) if x_vals else 0.0,
                            "num_points": len(x_vals),
                            "min_absorbance": float(min(y_vals)) if y_vals else 0.0,
                            "max_absorbance": float(max(y_vals)) if y_vals else 0.0,
                        }
                        spec_meta.update(ole_meta)

                        spectrum = Spectrum(
                            title=title,
                            wavelengths=x_vals,
                            absorbances=y_vals,
                            metadata=spec_meta,
                        )
                        spectra.append(spectrum)

                    return spectra
            except Exception:
                pass

        # 2. Fallback: Galactic GRAMS Binary SPC Format (version 75 / 77)
        try:
            data = self._data
            if len(data) >= 160:
                fnpts = struct.unpack("<i", data[4:8])[0]
                ffirst = struct.unpack("<d", data[8:16])[0]
                flast = struct.unpack("<d", data[16:24])[0]
                if 1 <= fnpts <= 100000 and 100 <= ffirst <= 10000 and 100 <= flast <= 10000:
                    dw = (flast - ffirst) / (fnpts - 1) if fnpts > 1 else 0.0
                    wavelengths = [round(ffirst + k * dw, 4) for k in range(fnpts)]
                    pts_offset = 544 if len(data) >= 544 + fnpts * 4 else 512
                    absorbances = list(
                        struct.unpack(f"<{fnpts}f", data[pts_offset : pts_offset + fnpts * 4])
                    )
                    title = os.path.splitext(os.path.basename(self.filepath))[0]
                    return [Spectrum(title=title, wavelengths=wavelengths, absorbances=absorbances)]
        except Exception:
            pass

        raise ValueError(f"Unable to parse Shimadzu/Galactic SPC file: {self.filepath}")

    def to_dataframe(self) -> pd.DataFrame:
        """
        Combines all spectra in the file into a single pandas DataFrame aligned by wavelength.
        """
        if not self.spectra:
            return pd.DataFrame()

        df = self.spectra[0].to_dataframe()
        for s in self.spectra[1:]:
            s_df = s.to_dataframe()
            df = pd.merge(df, s_df, on="Wavelength (nm)", how="outer")

        ascending = self.spectra[0].start_wavelength < self.spectra[0].end_wavelength
        df = df.sort_values(by="Wavelength (nm)", ascending=ascending).reset_index(drop=True)
        return df

    def to_csv(self, filepath: str, index: bool = False) -> None:
        """Exports all spectra to a single combined CSV file."""
        df = self.to_dataframe()
        df.to_csv(filepath, index=index)

    def plot(
        self,
        show: bool = True,
        save_path: Optional[str] = None,
        title: Optional[str] = None,
        ax: Optional[Any] = None,
    ):
        """
        Plots all spectra in the file using matplotlib.
        """
        import matplotlib.pyplot as plt

        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
            created_fig = True

        for s in self.spectra:
            ax.plot(s.wavelengths, s.absorbances, label=s.title)

        ax.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
        ax.set_xlabel("Wavelength (nm)", fontweight="bold")
        ax.set_ylabel("Absorbance", fontweight="bold")
        plot_title = title or f"{self.file_type} Spectra - {self.header['filename']}"
        ax.set_title(plot_title, fontweight="bold")
        ax.legend()

        if created_fig:
            fig.subplots_adjust(top=0.93, bottom=0.150, left=0.1, right=0.96)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")

        if show and created_fig:
            plt.show()

        return ax

    def __len__(self) -> int:
        return len(self.spectra)

    def __getitem__(self, item: Union[int, str]) -> Spectrum:
        if isinstance(item, int):
            return self.spectra[item]
        elif isinstance(item, str):
            for s in self.spectra:
                if s.title.lower() == item.lower():
                    return s
            raise KeyError(f"No spectrum found with title '{item}'")
        raise TypeError(f"Invalid index type: {type(item)}")

    def __repr__(self) -> str:
        return (
            f"<CaryFile '{self.header['filename']}' ({self.file_type}) | "
            f"{len(self.spectra)} spectra>"
        )


def parse_uv(filepath: str) -> CaryFile:
    """
    Main function to parse a Cary (.DSW, .BSW) or Shimadzu (.SPC) binary file.

    Args:
        filepath (str): Path to the spectrometer file.

    Returns:
        CaryFile: Parsed spectrometer file object.
    """
    return CaryFile(filepath)


read_uv = parse_uv
read_cary = parse_uv

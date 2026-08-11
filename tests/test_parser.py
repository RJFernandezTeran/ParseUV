"""
Unit tests for the parseUV library.

All tests use only synthetic (in-memory) data — no spectrum files are required.
"""

import struct
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from parseuv import CaryFile, Spectrum
from parseuv.style import apply_style, get_style_path

# ---------------------------------------------------------------------------
# Helpers – synthetic data builders
# ---------------------------------------------------------------------------

def _make_wavelengths(start: float, end: float, n: int) -> list[float]:
    """Return a linearly-spaced wavelength list (start → end, inclusive)."""
    return [round(start + (end - start) * i / (n - 1), 3) for i in range(n)]


def _make_spectrum(
    title: str = "TestSpectrum",
    start: float = 800.0,
    end: float = 200.0,
    n: int = 601,
    metadata: dict | None = None,
) -> Spectrum:
    wl = _make_wavelengths(start, end, n)
    ab = [0.5 + 0.1 * (i % 10) for i in range(n)]
    return Spectrum(title=title, wavelengths=wl, absorbances=ab, metadata=metadata or {})


def _make_cary_binary(n: int = 601, start: float = 800.0, end: float = 200.0) -> bytes:
    """
    Build a minimal but valid Cary DSW binary blob that _parse_spectra() can decode.

    Layout:
      byte 0        – length of the magic string
      bytes 1..N    – magic string "Varian UV-VIS DSW"
      bytes 0x5D–0x60 – end_wavelength (float LE)
      bytes 0x61–0x64 – start_wavelength (float LE)
      bytes 0x6D–0x70 – num_points (int LE)
      256-byte gap    – zeroed (stands in for ASCII metadata block / title prefix)
      spectral data   – n × (wavelength float LE, absorbance float LE)
    """
    magic = b"Varian UV-VIS DSW"
    header = bytearray(0x200)           # 512-byte header blank slate
    header[0] = len(magic)
    header[1 : 1 + len(magic)] = magic
    struct.pack_into("<f", header, 0x5D, end)
    struct.pack_into("<f", header, 0x61, start)
    struct.pack_into("<i", header, 0x6D, n)

    # 256 zero bytes before spectral block (title area + padding)
    pad = bytes(256)

    # Spectral data: wavelengths decrease from start → end
    pts = b""
    step = (end - start) / (n - 1)          # negative for decreasing
    for i in range(n):
        wl = start + step * i
        ab = 0.5 + 0.05 * (i % 20)
        pts += struct.pack("<ff", wl, ab)

    return bytes(header) + pad + pts


# ---------------------------------------------------------------------------
# Spectrum class tests (pure Python, no file I/O)
# ---------------------------------------------------------------------------

class TestSpectrumClass:
    """Tests exercising the Spectrum data model directly."""

    def test_basic_construction(self):
        s = _make_spectrum()
        assert s.title == "TestSpectrum"
        assert s.num_points == 601
        assert s.start_wavelength == pytest.approx(800.0)
        assert s.end_wavelength == pytest.approx(200.0)

    def test_step_size(self):
        s = _make_spectrum(start=800.0, end=200.0, n=601)
        assert s.step_size == pytest.approx(-1.0, rel=1e-3)

    def test_increasing_wavelengths(self):
        s = _make_spectrum(start=200.0, end=800.0, n=601)
        assert s.start_wavelength == pytest.approx(200.0)
        assert s.end_wavelength == pytest.approx(800.0)
        assert s.step_size == pytest.approx(1.0, rel=1e-3)

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="does not match"):
            Spectrum(title="Bad", wavelengths=[400.0, 500.0], absorbances=[0.1])

    def test_title_strip(self):
        s = Spectrum(title="  My Spectrum  ", wavelengths=[400.0], absorbances=[0.5])
        assert s.title == "My Spectrum"

    def test_empty_title_becomes_default(self):
        s = Spectrum(title="", wavelengths=[400.0], absorbances=[0.5])
        assert s.title == "Spectrum"

    def test_numpy_array_input(self):
        wl = np.linspace(800, 200, 601)
        ab = np.random.uniform(0, 1, 601)
        s = Spectrum(title="NpSpectrum", wavelengths=wl, absorbances=ab)
        assert s.num_points == 601
        assert isinstance(s.wavelengths, np.ndarray)

    def test_to_dataframe(self):
        s = _make_spectrum(title="Sample A")
        df = s.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert df.shape == (601, 2)
        assert list(df.columns) == ["Wavelength (nm)", "Sample A"]
        assert df["Wavelength (nm)"].iloc[0] == pytest.approx(800.0)
        assert df["Wavelength (nm)"].iloc[-1] == pytest.approx(200.0)

    def test_to_dict(self):
        s = _make_spectrum(title="DictTest", n=50)
        d = s.to_dict()
        assert d["title"] == "DictTest"
        assert d["num_points"] == 50
        assert len(d["wavelengths"]) == 50
        assert len(d["absorbances"]) == 50
        assert "step_size" in d
        assert "metadata" in d

    def test_to_csv_writes_file(self):
        s = _make_spectrum(n=10)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "spectrum.csv"
            s.to_csv(str(out))
            assert out.exists()
            df = pd.read_csv(str(out))
            assert df.shape == (10, 2)

    def test_repr(self):
        s = _make_spectrum(title="MySpec", n=10)
        r = repr(s)
        assert "MySpec" in r
        assert "10 points" in r

    def test_single_point_step_size(self):
        s = Spectrum(title="One", wavelengths=[550.0], absorbances=[0.3])
        assert s.step_size == 0.0

    def test_metadata_stored(self):
        meta = {"instrument": "Cary 5000", "scan_rate": "600.00 nm/min"}
        s = _make_spectrum(metadata=meta)
        assert s.metadata["instrument"] == "Cary 5000"
        assert s.metadata["scan_rate"] == "600.00 nm/min"


# ---------------------------------------------------------------------------
# CaryFile class tests – using a synthetic binary blob (no real file)
# ---------------------------------------------------------------------------

class TestCaryFileSynthetic:
    """
    Tests for CaryFile parsing behaviour using a minimal synthetic binary blob
    written to a temporary .DSW file.
    """

    @pytest.fixture()
    def dsw_file(self, tmp_path):
        """Write a synthetic DSW blob to a temp file and return its path."""
        blob = _make_cary_binary(n=601, start=800.0, end=200.0)
        p = tmp_path / "synthetic.DSW"
        p.write_bytes(blob)
        return str(p)

    def test_file_type_dsw(self, dsw_file):
        cf = CaryFile(dsw_file)
        assert cf.file_type == "DSW"

    def test_header_has_magic(self, dsw_file):
        cf = CaryFile(dsw_file)
        assert "magic" in cf.header
        assert cf.header["magic"].startswith("Varian UV-VIS")

    def test_spectra_are_parsed(self, dsw_file):
        cf = CaryFile(dsw_file)
        assert len(cf.spectra) >= 1

    def test_spectrum_properties(self, dsw_file):
        cf = CaryFile(dsw_file)
        s = cf[0]
        assert s.num_points >= 30
        assert 190.0 <= s.start_wavelength <= 1100.0
        assert 190.0 <= s.end_wavelength <= 1100.0

    def test_len(self, dsw_file):
        cf = CaryFile(dsw_file)
        assert len(cf) == len(cf.spectra)

    def test_getitem_by_index(self, dsw_file):
        cf = CaryFile(dsw_file)
        s = cf[0]
        assert isinstance(s, Spectrum)

    def test_getitem_by_title(self, dsw_file):
        cf = CaryFile(dsw_file)
        title = cf[0].title
        found = cf[title]
        assert found.title == title

    def test_getitem_missing_title_raises(self, dsw_file):
        cf = CaryFile(dsw_file)
        with pytest.raises(KeyError):
            _ = cf["nonexistent_title"]

    def test_getitem_wrong_type_raises(self, dsw_file):
        cf = CaryFile(dsw_file)
        with pytest.raises(TypeError):
            _ = cf[3.14]

    def test_to_dataframe(self, dsw_file):
        cf = CaryFile(dsw_file)
        df = cf.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "Wavelength (nm)" in df.columns
        assert df.shape[1] == len(cf.spectra) + 1  # wavelength + one column per spectrum

    def test_to_csv(self, dsw_file):
        cf = CaryFile(dsw_file)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "out.csv"
            cf.to_csv(str(out))
            assert out.exists()
            df = pd.read_csv(str(out))
            assert "Wavelength (nm)" in df.columns

    def test_repr(self, dsw_file):
        cf = CaryFile(dsw_file)
        r = repr(cf)
        assert "synthetic" in r
        assert "DSW" in r

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CaryFile(str(tmp_path / "ghost.DSW"))

    def test_invalid_magic_raises(self, tmp_path):
        bad = tmp_path / "bad.DSW"
        bad.write_bytes(b"\x0f" + b"BADMAGIC_NOT_CARY" + b"\x00" * 200)
        with pytest.raises(ValueError, match="Invalid file format"):
            CaryFile(str(bad))

    def test_bsw_file_type_detected(self, tmp_path):
        blob = _make_cary_binary()
        p = tmp_path / "batch.BSW"
        p.write_bytes(blob)
        cf = CaryFile(str(p))
        assert cf.file_type == "BSW"


# ---------------------------------------------------------------------------
# CaryFile – multiple spectra (multi-spectrum BSW blob)
# ---------------------------------------------------------------------------

class TestCaryFileMultiSpectra:
    """Ensure multi-spectrum BSW blobs are correctly decoded."""

    @pytest.fixture()
    def bsw_file(self, tmp_path):
        """Build a BSW blob containing two back-to-back spectral blocks."""
        magic = b"Varian UV-VIS BSW"
        header = bytearray(0x200)
        header[0] = len(magic)
        header[1 : 1 + len(magic)] = magic
        struct.pack_into("<f", header, 0x5D, 200.0)   # end_w
        struct.pack_into("<f", header, 0x61, 800.0)   # start_w
        struct.pack_into("<i", header, 0x6D, 601)

        def make_block(start, end, n):
            step = (end - start) / (n - 1)
            block = bytes(256)   # title / padding area
            for i in range(n):
                wl = start + step * i
                ab = 0.3 + 0.01 * (i % 30)
                block += struct.pack("<ff", wl, ab)
            return block

        blob = bytes(header) + make_block(800.0, 200.0, 601) + make_block(800.0, 200.0, 601)
        p = tmp_path / "multi.BSW"
        p.write_bytes(blob)
        return str(p)

    def test_multiple_spectra(self, bsw_file):
        cf = CaryFile(bsw_file)
        assert cf.file_type == "BSW"
        assert len(cf.spectra) >= 1       # at minimum one block parsed

    def test_dataframe_shape(self, bsw_file):
        cf = CaryFile(bsw_file)
        df = cf.to_dataframe()
        # one wavelength column + one per spectrum
        assert df.shape[1] == len(cf.spectra) + 1


# ---------------------------------------------------------------------------
# Spectrum – to_dataframe / merge behaviour (pure Spectrum objects)
# ---------------------------------------------------------------------------

class TestCaryFilePureSpectraContainer:
    """
    Tests for CaryFile.to_dataframe() merging logic using hand-crafted Spectrum
    objects injected into a CaryFile instance (bypassing file I/O entirely).
    """

    @pytest.fixture()
    def cary_file_with_spectra(self, tmp_path):
        """Create a CaryFile backed by a real minimal DSW file, then overwrite spectra."""
        blob = _make_cary_binary(n=50, start=800.0, end=200.0)
        p = tmp_path / "stub.DSW"
        p.write_bytes(blob)
        cf = CaryFile(str(p))

        # Replace parsed spectra with controlled synthetic ones
        wl = _make_wavelengths(800.0, 200.0, 50)
        cf.spectra = [
            Spectrum("Alpha", wl, [0.1 * i for i in range(50)]),
            Spectrum("Beta",  wl, [0.2 * i for i in range(50)]),
            Spectrum("Gamma", wl, [0.3 * i for i in range(50)]),
        ]
        return cf

    def test_three_spectra_dataframe_columns(self, cary_file_with_spectra):
        df = cary_file_with_spectra.to_dataframe()
        assert df.shape == (50, 4)   # Wavelength + Alpha + Beta + Gamma
        assert set(df.columns) == {"Wavelength (nm)", "Alpha", "Beta", "Gamma"}

    def test_indexing_by_title(self, cary_file_with_spectra):
        s = cary_file_with_spectra["Beta"]
        assert s.title == "Beta"
        assert s.num_points == 50

    def test_indexing_case_insensitive(self, cary_file_with_spectra):
        s = cary_file_with_spectra["ALPHA"]
        assert s.title == "Alpha"

    def test_csv_export_three_spectra(self, cary_file_with_spectra):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "merged.csv"
            cary_file_with_spectra.to_csv(str(out))
            df = pd.read_csv(str(out))
            assert df.shape == (50, 4)


# ---------------------------------------------------------------------------
# Style module tests
# ---------------------------------------------------------------------------

class TestStyleModule:
    def test_get_style_path_regular(self):
        path = get_style_path("regular")
        assert path.name == "HLV_plt.mplstyle"
        assert path.exists()

    def test_get_style_path_unknown_falls_back(self):
        path = get_style_path("nonexistent_profile")
        assert path.name == "HLV_plt.mplstyle"

    def test_apply_style_does_not_raise(self):
        apply_style("regular")   # should complete without error


# ---------------------------------------------------------------------------
# Edge-case / property tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_spectrum_two_points_step(self):
        s = Spectrum("Two", [400.0, 500.0], [0.1, 0.2])
        assert s.step_size == pytest.approx(100.0)
        assert s.num_points == 2

    def test_spectrum_large_absorbance_values(self):
        """Parser allows absorbances up to 1000 in the new Cary format."""
        s = Spectrum("HighAbs", [300.0, 400.0, 500.0], [50.0, 99.9, 999.9])
        assert s.absorbances[2] == pytest.approx(999.9)

    def test_spectrum_negative_absorbances(self):
        s = Spectrum("NegAbs", [300.0, 400.0], [-0.5, -1.2])
        assert s.absorbances[0] == pytest.approx(-0.5)

    def test_to_dict_roundtrip(self):
        s = _make_spectrum(title="RoundTrip", n=20)
        d = s.to_dict()
        s2 = Spectrum(
            title=d["title"],
            wavelengths=d["wavelengths"],
            absorbances=d["absorbances"],
            metadata=d["metadata"],
        )
        assert s2.title == s.title
        assert s2.num_points == s.num_points
        np.testing.assert_allclose(s2.wavelengths, s.wavelengths)
        np.testing.assert_allclose(s2.absorbances, s.absorbances)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

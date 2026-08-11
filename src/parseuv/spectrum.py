"""
Spectrum class representation for single spectrum recordings.
"""

from typing import Any, Optional, Union

import numpy as np
import pandas as pd


class Spectrum:
    """
    Represents a single spectrometer recording with wavelength and absorbance data.

    Attributes:
        title (str): Title or sample identifier for the spectrum.
        wavelengths (np.ndarray): 1D array of wavelength values (nm).
        absorbances (np.ndarray): 1D array of absorbance values.
        metadata (dict): Extracted header parameters (e.g. scan speed, resolution).
    """

    def __init__(
        self,
        title: str,
        wavelengths: Union[list[float], np.ndarray],
        absorbances: Union[list[float], np.ndarray],
        metadata: Optional[dict[str, Any]] = None,
    ):
        self.title = title.strip() if title else "Spectrum"
        self.wavelengths = np.asarray(wavelengths, dtype=np.float64)
        self.absorbances = np.asarray(absorbances, dtype=np.float64)
        self.metadata = metadata or {}

        if len(self.wavelengths) != len(self.absorbances):
            raise ValueError(
                f"Wavelengths length ({len(self.wavelengths)}) does not match "
                f"absorbances length ({len(self.absorbances)}) for '{self.title}'"
            )

    @property
    def num_points(self) -> int:
        """Returns total number of data points."""
        return len(self.wavelengths)

    @property
    def start_wavelength(self) -> float:
        """Returns the first recorded wavelength value (nm)."""
        return float(self.wavelengths[0]) if self.num_points > 0 else 0.0

    @property
    def end_wavelength(self) -> float:
        """Returns the last recorded wavelength value (nm)."""
        return float(self.wavelengths[-1]) if self.num_points > 0 else 0.0

    @property
    def step_size(self) -> float:
        """Returns calculated wavelength step size (nm)."""
        if self.num_points < 2:
            return 0.0
        return float((self.end_wavelength - self.start_wavelength) / (self.num_points - 1))

    def to_dataframe(self) -> pd.DataFrame:
        """Returns a pandas DataFrame representation of the spectrum."""
        return pd.DataFrame({"Wavelength (nm)": self.wavelengths, self.title: self.absorbances})

    def to_dict(self) -> dict[str, Any]:
        """Returns a dictionary representation of the spectrum."""
        return {
            "title": self.title,
            "num_points": self.num_points,
            "start_wavelength": self.start_wavelength,
            "end_wavelength": self.end_wavelength,
            "step_size": self.step_size,
            "wavelengths": self.wavelengths.tolist(),
            "absorbances": self.absorbances.tolist(),
            "metadata": self.metadata,
        }

    def to_csv(self, filepath: str, index: bool = False) -> None:
        """Exports the spectrum data to a CSV file."""
        df = self.to_dataframe()
        df.to_csv(filepath, index=index)

    def plot(
        self,
        show: bool = True,
        save_path: Optional[str] = None,
        title: Optional[str] = None,
        ax: Optional[Any] = None,
        color: Optional[str] = None,
        **kwargs,
    ):
        """Plots the spectrum using matplotlib."""
        import matplotlib.pyplot as plt

        created_fig = False
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 5))
            created_fig = True

        line_kwargs = {"label": self.title, "linewidth": 1.8}
        line_kwargs.update(kwargs)
        if color:
            line_kwargs["color"] = color

        ax.plot(self.wavelengths, self.absorbances, **line_kwargs)
        ax.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
        ax.set_xlabel("Wavelength (nm)", fontweight="bold")
        ax.set_ylabel("Absorbance", fontweight="bold")
        plot_title = title or f"Spectrum: {self.title}"
        ax.set_title(plot_title, fontweight="bold")
        ax.legend()

        if created_fig:
            fig.subplots_adjust(top=0.93, bottom=0.150, left=0.1, right=0.96)

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")

        if show and created_fig:
            plt.show()

        return ax

    def __repr__(self) -> str:
        return (
            f"<Spectrum '{self.title}' | {self.num_points} points "
            f"({self.start_wavelength} -> {self.end_wavelength} nm)>"
        )

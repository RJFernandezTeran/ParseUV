"""
Batch processing module to process and plot all .BSW, .DSW, and .SPC files in a folder.
"""

import argparse
import os
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from .parser import parse_uv
from .spectrum import Spectrum
from .style import apply_style


def spectra_to_df(spectra: list[Spectrum]) -> pd.DataFrame:
    """Helper to convert a list of Spectrum objects into a single DataFrame aligned by wavelength."""
    if not spectra:
        return pd.DataFrame()
    df = spectra[0].to_dataframe()
    for s in spectra[1:]:
        df = pd.merge(df, s.to_dataframe(), on="Wavelength (nm)", how="outer")
    ascending = spectra[0].start_wavelength < spectra[0].end_wavelength
    df = df.sort_values(by="Wavelength (nm)", ascending=ascending).reset_index(drop=True)
    return df


def process_file(filepath: str, output_dir: Optional[str] = None, plot_format: str = "png") -> dict:
    """
    Processes a single .BSW, .DSW, or .SPC file:
    - Exports CSV files to a 'CSV/' subfolder.
    - Exports plot figures to an extension-named subfolder (e.g. 'PNG/', 'PDF/', 'SVG/').
    """
    apply_style("regular")
    cary_file = parse_uv(filepath)
    filename = os.path.basename(filepath)
    basename = os.path.splitext(filename)[0]

    base_out_dir = output_dir or os.path.dirname(filepath) or "."

    # Separate subfolders for CSV and Plots
    plot_ext_upper = plot_format.lstrip(".").upper()
    csv_dir = os.path.join(base_out_dir, "CSV")
    plot_dir = os.path.join(base_out_dir, plot_ext_upper)

    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(plot_dir, exist_ok=True)

    sample_spectra = []
    bg_spectra = []

    for s in cary_file.spectra:
        t_lower = s.title.lower()
        if "baseline" in t_lower or "background" in t_lower or "dark" in t_lower:
            bg_spectra.append(s)
        else:
            sample_spectra.append(s)

    # 1. Save CSV exports in CSV/ subfolder
    sample_csv_path = os.path.join(csv_dir, f"{basename}_spectra.csv")
    if sample_spectra:
        df_sample = spectra_to_df(sample_spectra)
        df_sample.to_csv(sample_csv_path, index=False)
    else:
        cary_file.to_csv(sample_csv_path)

    bg_csv_path = None
    if bg_spectra:
        bg_csv_path = os.path.join(csv_dir, f"{basename}_background.csv")
        df_bg = spectra_to_df(bg_spectra)
        df_bg.to_csv(bg_csv_path, index=False)

    # 2. Save plot image in <FORMAT>/ subfolder
    plot_ext_lower = plot_format.lstrip(".").lower()
    plot_path = os.path.join(plot_dir, f"{basename}.{plot_ext_lower}")

    sample_colors = [
        "#1f77b4",
        "#ff7f0e",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#17becf",
    ]
    bg_colors = ["#2ca02c", "#7f7f7f", "#bcbd22", "#4b5563"]

    if bg_spectra:
        fig = plt.figure(figsize=(9, 7))
        gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.08)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1], sharex=ax1)

        for idx, s in enumerate(sample_spectra):
            c = sample_colors[idx % len(sample_colors)]
            ax1.plot(s.wavelengths, s.absorbances, label=s.title, color=c, linewidth=1.8)

        ax1.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
        ax1.set_ylabel("Absorbance", fontweight="bold")
        ax1.set_title(f"{cary_file.file_type} Spectra - {filename}", fontweight="bold")
        if sample_spectra:
            ax1.legend(loc="best")
        plt.setp(ax1.get_xticklabels(), visible=False)

        for idx, s in enumerate(bg_spectra):
            c = bg_colors[idx % len(bg_colors)]
            ax2.plot(
                s.wavelengths,
                s.absorbances,
                label=s.title,
                color=c,
                linestyle="--",
                linewidth=1.4,
            )

        ax2.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
        ax2.set_xlabel("Wavelength (nm)", fontweight="bold")
        ax2.set_ylabel("Baseline Abs.", fontweight="bold")
        ax2.legend(loc="best")

        fig.subplots_adjust(top=0.93, bottom=0.150, left=0.1, right=0.96, hspace=0.08)
        fig.align_ylabels([ax1, ax2])
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

    else:
        fig, ax1 = plt.subplots(figsize=(9, 6))
        for idx, s in enumerate(sample_spectra):
            c = sample_colors[idx % len(sample_colors)]
            ax1.plot(s.wavelengths, s.absorbances, label=s.title, color=c, linewidth=1.8)

        ax1.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
        ax1.set_xlabel("Wavelength (nm)", fontweight="bold")
        ax1.set_ylabel("Absorbance", fontweight="bold")
        ax1.set_title(f"{cary_file.file_type} Spectra - {filename}", fontweight="bold")
        if sample_spectra:
            ax1.legend(loc="best")

        fig.subplots_adjust(top=0.93, bottom=0.150, left=0.1, right=0.96)
        plt.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

    return {
        "file": filename,
        "type": cary_file.file_type,
        "total_spectra": len(cary_file.spectra),
        "samples_count": len(sample_spectra),
        "background_count": len(bg_spectra),
        "sample_csv": sample_csv_path,
        "bg_csv": bg_csv_path,
        "plot": plot_path,
    }


def batch_process_folder(
    folder_path: str, output_dir: Optional[str] = None, plot_format: str = "png"
) -> list[dict]:
    """
    Processes all .BSW, .DSW, and .SPC files found in folder_path.
    Exports CSVs to 'CSV/' subfolder and plots to '<FORMAT>/' subfolder.
    """
    folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(folder_path):
        raise NotADirectoryError(f"Directory not found: {folder_path}")

    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith((".bsw", ".dsw", ".spc"))
    ]

    if not files:
        print(f"No .BSW, .DSW, or .SPC files found in '{folder_path}'.")
        return []

    print("=" * 80)
    print(f"BATCH PROCESSING {len(files)} SPECTROMETER FILES")
    print(f"Target Directory: {folder_path}")
    print(f"Plot Format:      .{plot_format.lstrip('.').lower()}")
    print("=" * 80)

    results = []
    for idx, fp in enumerate(files, 1):
        try:
            res = process_file(fp, output_dir=output_dir, plot_format=plot_format)
            results.append(res)
            print(f"[{idx}/{len(files)}] Processed '{res['file']}' ({res['type']}):")
            print(f"    - CSV:  CSV/{os.path.basename(res['sample_csv'])}")
            if res["bg_csv"]:
                print(f"    - CSV:  CSV/{os.path.basename(res['bg_csv'])}")
            print(f"    - Plot: {plot_format.upper()}/{os.path.basename(res['plot'])}")
        except Exception as e:
            print(f"[{idx}/{len(files)}] Error processing '{os.path.basename(fp)}': {e}")

    print("=" * 80)
    print(f"BATCH PROCESSING COMPLETED: {len(results)}/{len(files)} files processed successfully.")
    print("=" * 80)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Batch process all .BSW, .DSW, and .SPC Cary/Shimadzu spectrometer files in a folder."
    )
    parser.add_argument(
        "folder",
        nargs="?",
        default=None,
        help="Folder containing .BSW, .DSW, and .SPC files (default: prompt user or ./Spectra)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["png", "pdf", "svg", "PNG", "PDF", "SVG"],
        default=None,
        help="Plot image format (default: prompt user, fallback PNG)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Directory to save generated CSVs and plots (default: same as input files)",
    )

    args = parser.parse_args()

    folder = args.folder
    if not folder:
        default_dir = os.path.abspath("Spectra") if os.path.exists("Spectra") else os.getcwd()
        inp_dir = input(f"Enter folder path containing files [default: {default_dir}]: ").strip()
        folder = inp_dir if inp_dir else default_dir

    plot_format = args.format
    if not plot_format:
        print("\nSelect plot export format:")
        print("  [1] PNG (.png)  [DEFAULT]")
        print("  [2] PDF (.pdf)")
        print("  [3] SVG (.svg)")
        choice = input("Enter choice (1-3) [default: 1]: ").strip()
        if choice == "2":
            plot_format = "pdf"
        elif choice == "3":
            plot_format = "svg"
        else:
            plot_format = "png"

    batch_process_folder(folder, output_dir=args.output_dir, plot_format=plot_format)


if __name__ == "__main__":
    main()

"""
Demo script showing how to use the parseUV library to parse, export, and plot
Varian/Agilent Cary (.DSW, .BSW) and Shimadzu (.SPC) spectrometer binary files.
"""

import os

import matplotlib.pyplot as plt

from parseuv import parse_uv


def run_demo():
    print("=" * 80)
    print("                  PARSEUV LIBRARY DEMONSTRATION")
    print("=" * 80)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    spectra_dir = os.path.join(base_dir, "Spectra")

    dsw_matches = [
        os.path.join(spectra_dir, f) for f in os.listdir(spectra_dir) if f.lower().endswith(".dsw")
    ]
    bsw_matches = [
        os.path.join(spectra_dir, f) for f in os.listdir(spectra_dir) if f.lower().endswith(".bsw")
    ]
    spc_matches = [
        os.path.join(spectra_dir, f) for f in os.listdir(spectra_dir) if f.lower().endswith(".spc")
    ]

    dsw_file = dsw_matches[0] if dsw_matches else None
    bsw_file = bsw_matches[0] if bsw_matches else None
    spc_file = spc_matches[0] if spc_matches else None

    if dsw_file:
        print(f"\n[1] Reading Cary Spectrum File (.DSW): {os.path.basename(dsw_file)}")
        cary_dsw = parse_uv(dsw_file)
        print(f"    File type: {cary_dsw.file_type}")
        print(f"    Spectra count: {len(cary_dsw.spectra)}")

        spectrum = cary_dsw[0]
        print(f"    Title: '{spectrum.title}'")
        print(
            f"    Wavelength Range: {spectrum.start_wavelength} nm -> {spectrum.end_wavelength} nm"
        )
        print(f"    Data Points: {spectrum.num_points} (step: {spectrum.step_size} nm)")
        print(
            f"    Absorbance Range: {spectrum.absorbances.min():.4f} to {spectrum.absorbances.max():.4f}"
        )

        dsw_csv = "dsw_exported.csv"
        cary_dsw.to_csv(dsw_csv)
        print(f"    Saved CSV export to: {os.path.abspath(dsw_csv)}")

        dsw_plot_path = "dsw_spectrum_plot.png"
        fig, ax = plt.subplots(figsize=(8, 5))
        spectrum.plot(show=False, ax=ax, color="#1f77b4")
        ax.set_title(f"Cary Spectrum: {spectrum.title}", fontsize=13, fontweight="bold")
        plt.tight_layout()
        plt.savefig(dsw_plot_path, dpi=300, bbox_inches="tight")
        print(f"    Saved DSW plot figure to: {os.path.abspath(dsw_plot_path)}")
        plt.close(fig)

    if bsw_file:
        print(f"\n[2] Reading Batch Spectra File (.BSW): {os.path.basename(bsw_file)}")
        cary_bsw = parse_uv(bsw_file)
        print(f"    File type: {cary_bsw.file_type}")
        print(f"    Spectra count: {len(cary_bsw.spectra)}")

        for idx, s in enumerate(cary_bsw.spectra, 1):
            print(
                f"    Spectrum #{idx}: '{s.title}' | {s.num_points} pts | {s.start_wavelength} -> {s.end_wavelength} nm"
            )

        bsw_csv = "bsw_exported.csv"
        cary_bsw.to_csv(bsw_csv)
        print(f"    Saved CSV export to: {os.path.abspath(bsw_csv)}")

    bsw_plot_path = "bsw_spectra_plot.png"
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    ax1.plot(
        cary_bsw[0].wavelengths,
        cary_bsw[0].absorbances,
        label=cary_bsw[0].title,
        color="#d62728",
        linewidth=1.8,
    )
    ax1.plot(
        cary_bsw[1].wavelengths,
        cary_bsw[1].absorbances,
        label=cary_bsw[1].title,
        color="#ff7f0e",
        linestyle="--",
        linewidth=1.8,
    )
    ax1.set_ylabel("Absorbance", fontsize=11, fontweight="bold")
    ax1.set_title("Cary 50 BSW Batch Spectra - Sample Measurements", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(loc="upper right")

    ax2.plot(
        cary_bsw[2].wavelengths,
        cary_bsw[2].absorbances,
        label=cary_bsw[2].title,
        color="#2ca02c",
        linewidth=1.5,
    )
    ax2.plot(
        cary_bsw[3].wavelengths,
        cary_bsw[3].absorbances,
        label=cary_bsw[3].title,
        color="#9467bd",
        linestyle=":",
        linewidth=1.5,
    )
    ax2.set_xlabel("Wavelength (nm)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Absorbance", fontsize=11, fontweight="bold")
    ax2.set_title("Baseline Recordings (100%T & 0%T)", fontsize=11, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(bsw_plot_path, dpi=300, bbox_inches="tight")
    print(f"    Saved BSW plot figure to: {os.path.abspath(bsw_plot_path)}")
    plt.close(fig)

    print(f"\n[3] Reading Shimadzu File (.SPC): {os.path.basename(spc_file)}")
    spc_obj = parse_uv(spc_file)
    print(f"    File type: {spc_obj.file_type}")
    print(f"    Spectrum Title: '{spc_obj[0].title}' ({spc_obj[0].num_points} points)")

    print(f"\n[4] Auto-Detecting Any File Format: {os.path.basename(bsw_file)}")
    auto_file = parse_uv(bsw_file)
    print(f"    Auto-detected file type: {auto_file.file_type}")

    print("\n" + "=" * 80)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("Exported files created:")
    print(f"  - {dsw_csv}")
    print(f"  - {bsw_csv}")
    print(f"  - {dsw_plot_path}")
    print(f"  - {bsw_plot_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()

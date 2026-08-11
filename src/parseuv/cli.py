"""
Command-line interface (CLI) for the parseUV library.
"""

import argparse
import os
import sys

from .batch import batch_process_folder
from .parser import parse_uv


def main():
    parser = argparse.ArgumentParser(
        description="parseUV: Convert, batch process, or inspect Varian/Agilent Cary (.DSW, .BSW) and Shimadzu (.SPC) binary files."
    )
    parser.add_argument(
        "filepath",
        nargs="?",
        default=None,
        help="Path to a spectrometer binary file (.DSW, .BSW, .SPC) or directory for batch mode",
    )
    parser.add_argument(
        "--gui", action="store_true", help="Launch the parseUV PyQt6 Drag-and-Drop GUI application"
    )
    parser.add_argument("--batch", action="store_true", help="Run batch mode on a target folder")
    parser.add_argument(
        "-f",
        "--format",
        choices=["png", "pdf", "svg"],
        default="png",
        help="Plot output image format for batch mode (png, pdf, svg)",
    )
    parser.add_argument("-o", "--output", help="Output CSV file or export directory")
    parser.add_argument("-p", "--plot", help="Path to save output plot figure (e.g. plot.png)")
    parser.add_argument("--show-plot", action="store_true", help="Display interactive plot window")

    args = parser.parse_args()

    if args.gui:
        from .gui import launch_gui

        launch_gui()
        return

    if args.batch or (args.filepath and os.path.isdir(args.filepath)):
        target_dir = (
            args.filepath if (args.filepath and os.path.isdir(args.filepath)) else "Spectra"
        )
        batch_process_folder(target_dir, output_dir=args.output, plot_format=args.format)
        return

    if not args.filepath:
        parser.print_help()
        sys.exit(1)

    try:
        cary_file = parse_uv(args.filepath)
        print(f"Successfully read '{cary_file.header['filename']}' ({cary_file.file_type})")
        print(f"Found {len(cary_file.spectra)} spectra:")
        for idx, s in enumerate(cary_file.spectra, 1):
            print(
                f"  [{idx}] '{s.title}': {s.num_points} points ({s.start_wavelength} -> {s.end_wavelength} nm)"
            )

        if args.output:
            cary_file.to_csv(args.output)
            print(f"Exported CSV to: {os.path.abspath(args.output)}")

        if args.plot or args.show_plot:
            cary_file.plot(show=args.show_plot, save_path=args.plot)
            if args.plot:
                print(f"Saved plot image to: {os.path.abspath(args.plot)}")

    except Exception as e:
        print(f"Error reading '{args.filepath}': {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

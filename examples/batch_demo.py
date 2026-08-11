"""
Batch processing demo script to convert and plot all .BSW, .DSW, and .SPC files in a directory.
"""

import os

from parseuv.batch import batch_process_folder


def run_batch_demo():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    spectra_dir = os.path.join(base_dir, "Spectra")

    print("Running batch processing on Spectra directory...")
    batch_process_folder(spectra_dir, plot_format="png")


if __name__ == "__main__":
    run_batch_demo()

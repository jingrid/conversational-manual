"""Render every page of the manual PDF to a PNG.

Usage: .venv/bin/python ingest/render_pages.py [--config configs/ocr_compare.yaml]

Output: data/pages/page_001.png, ... numbered by PDF page, starting at 1.
"""

import argparse  # Reads options from the command line, such as --config.
from pathlib import Path  # Joins and inspects file paths safely.

import pymupdf  # Opens PDFs and draws their pages as images.
import yaml  # Reads settings from the YAML file in configs/.

# __file__ is this script: ingest/render_pages.py. Going up two levels gives the
# project root, so the script works no matter which folder you run it from.
ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    """Read the settings, then save each PDF page as one PNG file."""
    # Define the command-line options. The description text comes from the
    # docstring at the top of this file and appears when you pass --help.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/ocr_compare.yaml")
    args = parser.parse_args()

    # safe_load turns the YAML text into ordinary Python dicts and lists.
    # Keeping settings there lets you run experiments without editing code.
    config = yaml.safe_load((ROOT / args.config).read_text())
    dpi = config["render"]["dpi"]

    # A colorspace says how pixels store color: RGB has three channels and gray
    # has one. This script defaults to RGB because red markings carry meaning in
    # this manual.
    colorspace = pymupdf.csGRAY if config["render"]["colorspace"] == "gray" else pymupdf.csRGB

    # Create the output folder. parents=True also creates any missing parent
    # folders, and exist_ok=True means an existing folder is not an error.
    pages_dir = ROOT / config["pages_dir"]
    pages_dir.mkdir(parents=True, exist_ok=True)

    # "with" closes the PDF automatically when this block ends.
    with pymupdf.open(ROOT / config["pdf"]) as doc:
        # Looping over a PDF gives one page at a time. start=1 makes the file
        # numbers match PDF page numbers, which people count from 1.
        for number, page in enumerate(doc, start=1):
            # A pixmap is a grid of pixels in memory. PDF sizes are measured in
            # points (72 per inch), so a 420-point-wide page at 200 DPI becomes
            # about 420 / 72 * 200 = 1167 pixels wide.
            # alpha=False skips a transparency channel, which a scan doesn't need.
            pixmap = page.get_pixmap(dpi=dpi, colorspace=colorspace, alpha=False)

            # :03d pads the number to three digits (page_007), so the files sort
            # in page order by name.
            path = pages_dir / f"page_{number:03d}.png"
            pixmap.save(path)
            print(f"{path.name}  {pixmap.width}x{pixmap.height}  {path.stat().st_size / 1e6:.2f} MB")
        print(f"Rendered {doc.page_count} pages at {dpi} DPI to {pages_dir}")


# This is true only when you run the file directly. It stops main() from running
# if another script imports this file.
if __name__ == "__main__":
    main()

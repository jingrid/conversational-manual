"""Build data/compare/report.html from existing ocr_compare.py outputs.

Usage: .venv/bin/python ingest/make_compare_report.py [--config configs/ocr_compare.yaml]

One row per compared page: page image, Apple OCR text with confidence, Claude text.
The report makes no API calls and does not score or rank the two outputs.
"""

import argparse  # Reads options from the command line, such as --config.
import html  # Escapes text so characters like < display safely in a web page.
import json  # Reads the OCR results saved by ocr_compare.py.
import os  # Provides relpath, used to build a relative image link.
import statistics  # Calculates the mean OCR confidence.
from pathlib import Path  # Joins and inspects file paths safely.

import yaml  # Reads settings from the YAML file in configs/.

# The project root, two levels above this file.
ROOT = Path(__file__).resolve().parent.parent

# The overall web page. Each {name} is filled in by .format(), and CSS braces are
# doubled ({{ }}) so .format() leaves them alone. The .wrap div lets the wide
# table scroll sideways on a narrow screen.
PAGE_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OCR vs Claude report</title>
<style>
  body {{ font: 14px system-ui, sans-serif; margin: 16px; color: #1a1a1a; background: #fff; }}
  .wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 960px; table-layout: fixed; }}
  th, td {{ border: 1px solid #ccc; padding: 10px; vertical-align: top; text-align: left; }}
  thead th {{ position: sticky; top: 0; background: #f2f2f2; }}
  img {{ width: 100%; display: block; }}
  pre {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; }}
  .meta {{ margin: 0 0 8px; font-weight: 600; }}
  .score {{ color: #666; }}
</style>
<h1>OCR vs Claude report</h1>
<p>{page_count} pages. PDF page numbers. Scores appear beside OCR lines below {threshold}.</p>
<div class="wrap">
<table>
  <thead><tr><th>Page image</th><th>Apple OCR text</th><th>Claude vision text</th></tr></thead>
  <tbody>
{rows}
  </tbody>
</table>
</div>
"""

# One table row for one page: image, OCR text, Claude text. The row's id lets you
# jump straight to a page by adding #page-12 to the report's address.
ROW_TEMPLATE = """    <tr id="page-{page}">
      <td><p class="meta">PDF page {page}</p><a href="{image}"><img src="{image}" alt="Scan of PDF page {page}"></a></td>
      <td><p class="meta">{confidence}</p><pre>{ocr}</pre></td>
      <td><pre>{claude}</pre></td>
    </tr>"""


def confidence_summary(lines: list[dict]) -> str:
    """Summarize a page's OCR confidence scores as one line of text."""
    if not lines:
        return "No text detected"
    scores = [line["confidence"] for line in lines]
    # The mean describes the whole page, while the minimum reveals a single
    # shaky line that a high mean can hide.
    return f"Confidence: mean {statistics.mean(scores):.3f}, min {min(scores):.3f}, {len(scores)} lines"


def format_ocr_lines(lines: list[dict], threshold: float) -> str:
    """Return the OCR text as HTML, with scores beside low-confidence lines."""
    formatted = []
    for line in lines:
        # Escape first, so OCR text can't be mistaken for HTML. The score span
        # is added afterward because it is meant to be real HTML.
        text = html.escape(line["text"])
        if line["confidence"] < threshold:
            text += f' <span class="score">({line["confidence"]:.2f})</span>'
        formatted.append(text)
    return "\n".join(formatted)


def main() -> None:
    """Read the saved outputs for each page and write the combined report."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/ocr_compare.yaml")
    args = parser.parse_args()

    # Find the folders and the confidence display cutoff in the settings.
    config = yaml.safe_load((ROOT / args.config).read_text())
    compare_dir = ROOT / config["compare_dir"]
    pages_dir = ROOT / config["pages_dir"]
    threshold = config["report"]["show_line_confidence_below"]

    # glob finds every matching OCR file, and sorted puts them in page order, so
    # the report automatically covers whichever pages have been compared.
    rows = []
    for ocr_path in sorted(compare_dir.glob("page_*.ocr.json")):
        # Turn "page_012.ocr.json" into "page_012", the shared name of its files.
        stem = ocr_path.name.removesuffix(".ocr.json")
        claude_path = compare_dir / f"{stem}.claude.md"
        if not claude_path.exists():
            print(f"Skipping {stem}: no Claude output")
            continue
        lines = json.loads(ocr_path.read_text())

        # Fill in one row. The image link is relative to the report's folder
        # (../pages/...), so the images load from your local project.
        rows.append(
            ROW_TEMPLATE.format(
                page=int(stem.removeprefix("page_")),
                image=html.escape(Path(os.path.relpath(pages_dir / f"{stem}.png", compare_dir)).as_posix()),
                confidence=html.escape(confidence_summary(lines)),
                ocr=format_ocr_lines(lines, threshold),
                claude=html.escape(claude_path.read_text().strip()),
            )
        )

    # Join the rows, place them in the page template, and save the report.
    report_path = compare_dir / "report.html"
    report_path.write_text(
        PAGE_TEMPLATE.format(page_count=len(rows), threshold=threshold, rows="\n".join(rows))
    )
    print(f"Wrote {report_path} with {len(rows)} rows")


# This is true only when you run the file directly, not when it's imported.
if __name__ == "__main__":
    main()

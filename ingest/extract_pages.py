"""Transcribe every manual page with Claude vision into one markdown file per page.

Usage: .venv/bin/python ingest/extract_pages.py [--force] [--config configs/ocr_compare.yaml]

Reads data/pages/page_NNN.png (from render_pages.py) and writes
data/parsed/page_NNN.md. Follows the rule in DECISIONS.md: Claude vision for
every page except those listed in extract.exclude_pages.

Pages that already have a file are skipped, so an interrupted run can be
resumed without paying for finished pages again. Pass --force to redo them.
"""

import argparse  # Reads options from the command line, such as --force.
from pathlib import Path  # Joins and inspects file paths safely.

import anthropic  # Official Python SDK for calling the Claude API.
import yaml  # Reads settings from the YAML file in configs/.
from dotenv import load_dotenv  # Loads the API key from .env into the environment.

# Reuse the exact request used in the OCR comparison, so the extraction method
# is the one that was evaluated. This import works because Python adds this
# script's folder (ingest/) to its search path when you run the script.
from ocr_compare import run_claude

# The project root, two levels above this file.
ROOT = Path(__file__).resolve().parent.parent

# Rates for claude-opus-5-5 in dollars per token, used only for the cost
# printout. Update them if you change the model in the config.
INPUT_PRICE = 4 / 1_000_000
OUTPUT_PRICE = 20 / 1_000_000


def page_number(image_path: Path) -> int:
    """Turn data/pages/page_012.png into the number 12."""
    return int(image_path.stem.removeprefix("page_"))


def front_matter(page: int, image_path: Path, model: str) -> str:
    """Build the header that records where this page's text came from.

    The block between the --- lines is YAML "front matter", a common convention
    for metadata at the top of a markdown file. Later steps, such as chunking,
    can read it to cite the page an answer came from.
    """
    return (
        "---\n"
        f"pdf_page: {page}\n"
        f"source_image: {image_path.relative_to(ROOT).as_posix()}\n"
        "method: claude_vision\n"
        f"model: {model}\n"
        "---\n\n"
    )


def main() -> None:
    """Transcribe each page that needs it and report the total cost."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="redo pages that already have a file")
    parser.add_argument("--config", default="configs/ocr_compare.yaml")
    args = parser.parse_args()

    config = yaml.safe_load((ROOT / args.config).read_text())
    parsed_dir = ROOT / config["extract"]["parsed_dir"]
    parsed_dir.mkdir(parents=True, exist_ok=True)
    excluded = set(config["extract"]["exclude_pages"])

    # load_dotenv puts ANTHROPIC_API_KEY from .env where Anthropic() looks for it.
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()

    input_tokens = output_tokens = 0
    for image_path in sorted((ROOT / config["pages_dir"]).glob("page_*.png")):
        page = page_number(image_path)
        out_path = parsed_dir / f"{image_path.stem}.md"

        if page in excluded:
            print(f"page {page}: excluded by config")
            continue
        if out_path.exists() and not args.force:
            print(f"page {page}: already parsed, skipping")
            continue

        response = run_claude(client, image_path, config["claude"])
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens

        # Anything other than end_turn, such as max_tokens, means the text may be
        # cut off. Don't save it, so the next run retries this page.
        if response.stop_reason != "end_turn":
            print(f"page {page}: NOT SAVED, stop_reason={response.stop_reason}")
            continue

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        out_path.write_text(front_matter(page, image_path, response.model) + text + "\n")
        print(f"page {page}: saved {out_path.name} ({response.usage.output_tokens} output tokens)")

    cost = input_tokens * INPUT_PRICE + output_tokens * OUTPUT_PRICE
    print(f"Done. {input_tokens} input / {output_tokens} output tokens, about ${cost:.2f}")


# This is true only when you run the file directly, not when it's imported.
if __name__ == "__main__":
    main()

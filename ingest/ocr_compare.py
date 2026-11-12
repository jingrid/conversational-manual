"""Compare Apple Vision OCR with a Claude transcription on selected pages.

Usage: .venv/bin/python ingest/ocr_compare.py 3 9 14 [--config configs/ocr_compare.yaml]

Page numbers are PDF page numbers, matching data/pages/page_NNN.png.
Run ingest/render_pages.py first. For each page, data/compare/ receives:
  page_NNN.ocr.txt     OCR text in Vision's reading order
  page_NNN.ocr.json    OCR text with confidence and bounding box
  page_NNN.claude.md   Claude's markdown transcription
  page_NNN.html        scan, OCR, and Claude side by side
"""

import argparse  # Reads the page numbers and options from the command line.
import base64  # Encodes image bytes as text so they can go in a JSON request.
import html  # Escapes text so characters like < display safely in a web page.
import json  # Saves OCR results in a structured file.
import statistics  # Calculates the mean OCR confidence.
from pathlib import Path  # Joins and inspects file paths safely.

import anthropic  # Official Python SDK for calling the Claude API.
import yaml  # Reads settings from the YAML file in configs/.
from dotenv import load_dotenv  # Loads the API key from .env into the environment.
from ocrmac import ocrmac  # Python wrapper around Apple's built-in OCR.

# The project root, two levels above this file. Using it keeps paths correct no
# matter which folder you run the script from.
ROOT = Path(__file__).resolve().parent.parent

# The web page saved for each compared page. Each {name} is filled in later by
# .format(). CSS braces are doubled ({{ }}) so .format() leaves them alone.
HTML_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>Page {page}: OCR vs Claude</title>
<style>
  body {{ font: 14px system-ui, sans-serif; margin: 16px; }}
  main {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
  img {{ width: 100%; }}
  pre {{ white-space: pre-wrap; font-size: 13px; }}
</style>
<h1>Page {page}</h1>
<p>{ocr_summary} | {claude_summary}</p>
<main>
  <section><h2>Scan</h2><img src="../pages/{image_name}" alt="Scan of page {page}"></section>
  <section><h2>Apple Vision OCR</h2><pre>{ocr_text}</pre></section>
  <section><h2>Claude ({model})</h2><pre>{claude_text}</pre></section>
</main>
"""


def run_ocr(image_path: Path, settings: dict) -> list[dict]:
    """Return Vision's detected lines with confidence and normalized bounding box."""
    # This runs locally on your Mac, so it is free and the image stays on the
    # machine. recognition_level trades speed for accuracy, and
    # language_preference tells Vision which languages to expect.
    annotations = ocrmac.OCR(
        str(image_path),
        recognition_level=settings["recognition_level"],
        language_preference=settings["languages"],
    ).recognize()

    # recognize() returns one (text, confidence, bbox) tuple per detected piece
    # of text. Confidence runs from 0 to 1 and is Vision's own estimate, not a
    # measured accuracy. The bbox locates the text as fractions of the image
    # size, so it stays valid if the image is resized. Dicts save cleanly as JSON.
    return [
        {"text": text, "confidence": confidence, "bbox": list(bbox)}
        for text, confidence, bbox in annotations
    ]


def run_claude(client: anthropic.Anthropic, image_path: Path, settings: dict):
    """Send one page image to Claude and return the API response."""
    # JSON can't hold raw image bytes, so base64 rewrites them as plain text.
    # The final decode turns base64's bytes into the string the API expects.
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")

    # The SDK sends this as one HTTP request and returns the finished response.
    # It uses client.beta because the "fallbacks" option is a beta feature.
    return client.beta.messages.create(
        model=settings["model"],
        # A ceiling on generated tokens. Hitting it cuts the output off, which
        # compare_page detects through stop_reason.
        max_tokens=settings["max_tokens"],
        # Lets the model decide how much reasoning each page needs.
        thinking={"type": "adaptive"},
        # Higher effort allows more thoroughness and usually uses more tokens.
        output_config={"effort": settings["effort"]},
        # If safety filters decline a request by mistake, the API can route it
        # to a fallback model instead of returning no transcription.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        # One user message containing two blocks: the image, then the instructions.
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": image_data},
                    },
                    {"type": "text", "text": settings["prompt"]},
                ],
            }
        ],
    )


def compare_page(page: int, config: dict, client: anthropic.Anthropic) -> None:
    """Run OCR and Claude on one page, then save all four output files."""
    # Find the rendered image for this page and stop with a clear message if
    # the render step hasn't been run.
    stem = f"page_{page:03d}"
    image_path = ROOT / config["pages_dir"] / f"{stem}.png"
    if not image_path.exists():
        raise SystemExit(f"{image_path} not found. Run ingest/render_pages.py first.")
    out_dir = ROOT / config["compare_dir"]

    # Step 1: Apple OCR. Save plain text for reading, and JSON so the confidence
    # scores and text positions are available to later scripts.
    lines = run_ocr(image_path, config["ocr"])
    ocr_text = "\n".join(line["text"] for line in lines)
    (out_dir / f"{stem}.ocr.txt").write_text(ocr_text + "\n")
    (out_dir / f"{stem}.ocr.json").write_text(json.dumps(lines, indent=2) + "\n")

    # The "if lines else 0.0" avoids an error on a page where OCR finds no text.
    mean_confidence = statistics.mean(l["confidence"] for l in lines) if lines else 0.0
    ocr_summary = f"OCR: {len(lines)} lines, mean confidence {mean_confidence:.3f}"

    # Step 2: Claude. "end_turn" means the model finished normally. Anything
    # else, such as "max_tokens", means the text may be cut off, so warn.
    response = run_claude(client, image_path, config["claude"])
    if response.stop_reason != "end_turn":
        print(f"WARNING page {page}: stop_reason={response.stop_reason}, output may be incomplete")

    # A response is a list of content blocks and can include non-text blocks
    # such as thinking. Keep only the text.
    claude_text = "".join(block.text for block in response.content if block.type == "text")
    (out_dir / f"{stem}.claude.md").write_text(claude_text + "\n")

    # Token counts determine what the API call costs. Images count as input.
    claude_summary = (
        f"Claude: {response.usage.input_tokens} input / {response.usage.output_tokens} output tokens, "
        f"stop_reason={response.stop_reason}"
    )

    # Step 3: build the side-by-side page. html.escape keeps characters such as
    # < or & in the text from being treated as HTML. response.model records the
    # model that actually answered.
    (out_dir / f"{stem}.html").write_text(
        HTML_TEMPLATE.format(
            page=page,
            image_name=image_path.name,
            ocr_summary=html.escape(ocr_summary),
            claude_summary=html.escape(claude_summary),
            ocr_text=html.escape(ocr_text),
            claude_text=html.escape(claude_text),
            model=html.escape(response.model),
        )
    )
    print(f"page {page}: {ocr_summary} | {claude_summary}")


def main() -> None:
    """Read the command line and settings, then process each requested page."""
    # nargs="+" requires at least one page number and collects them into a list.
    # type=int converts each one from text to a number.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pages", nargs="+", type=int, help="PDF page numbers, starting at 1")
    parser.add_argument("--config", default="configs/ocr_compare.yaml")
    args = parser.parse_args()

    # Load the settings and make sure the output folder exists.
    config = yaml.safe_load((ROOT / args.config).read_text())
    (ROOT / config["compare_dir"]).mkdir(parents=True, exist_ok=True)

    # load_dotenv copies ANTHROPIC_API_KEY from .env into the environment, where
    # Anthropic() finds it. The key never has to appear in the code.
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic()

    # Each page is independent. Note that an error stops the run, while pages
    # already finished keep their saved files.
    for page in args.pages:
        compare_page(page, config, client)


# This is true only when you run the file directly, not when it's imported.
if __name__ == "__main__":
    main()

# Decisions

## 2026-11-08: Claude vision for pages with images

Page numbers below are PDF page numbers, matching `data/pages/page_NNN.png`.
Printed page numbers differ: printed page 9 is PDF page 12.

### Rule

| Pages | Method |
|---|---|
| Every page with a diagram, photo, or illustration: 2 and 4–28 | Claude vision |
| 3: text only, in two columns | Claude vision, because Apple OCR mixed up columns on page 22 |
| 1: scanner's notice, not part of the manual | Exclude |

Apple OCR is not used as a source for these pages. It remains available as a
free local cross-check.

### Why

Apple OCR can't follow formatting such as columns, and it does nothing to
understand images.

Claude vision handles this well. It puts images in context, including color,
which is an important part of the diagrams in this manual. It also deals well
with text formatting and understands what is going on across the page.

### What each method got wrong

Tested on PDF pages 5, 12, 13, 14, 19, 20, and 22. These come from targeted
checks against the scans, not a full proofread, so other errors may exist.

**Apple OCR**

| Page | Problem |
|---|---|
| 5 | Mixed the diagram's callout numbers into the parts legend |
| 12 | Captured nothing from the red/white indicator grid; garbled the nameplate as `MADE IN SWEDEN SY YICTOR HASSELBLAD ALS` |
| 13 | Read "film" as `tilm` |
| 14 | Returned only step numbers (missing 1) and the stray text `Ozldi`; captured nothing from the eight illustrated steps |
| 19 | Read an upside-down nameplate as `BAT SISTIN` (confidence 0.30) |
| 20 | Dropped the instructions for attaching the winding crank, leaving only `locks on.`, placed after the flash section |
| 22 | Alternated lines from the two columns; read the lens marking `4,5/38` as `4,8/38` |
| Several | Left line-end hyphens in words, such as `progressi-` / `vely` |

OCR confidence did not flag most of these: pages 5, 12, 13, 20, and 22 all
averaged 1.000.

**Claude vision**

| Page | Problem |
|---|---|
| 14 | Described the step 8 arrow as counterclockwise. The arrow shows clockwise, as does printed step 8 on page 13 |
| 5 | Described the film magazine as attached at the rear; the drawing appears to show it separated from the body |
| 5, 13, 20, 22 | Joined line-end hyphenated words even though the prompt asked for text exactly as printed. This helps search but is not literal |

Unresolved:

- Page 12: Claude read the nameplate as `MADE IN SWEDEN BY VICTOR HASSELBLAD AB`.
  The print is too small to confirm every letter.
- Page 22: the lens marking looks like `Blogon` in the photo, while the body text
  says `Biogon`. Claude wrote `Biogon`.

Claude's bracketed descriptions are generated text, not printed text, and they
can be wrong. Page 14 shows that a direction can be wrong while reading
convincingly.

### Cost per page for Claude vision

Model: `claude-opus-5-5`, effort `high`, at $4 per million input tokens and $20
per million output tokens. Output tokens include billed thinking.

| Page | Input tokens | Output tokens | Cost |
|---|---|---|---|
| 5 | 3,178 | 1,413 | $0.041 |
| 12 | 1,985 | 804 | $0.024 |
| 13 | 1,985 | 775 | $0.023 |
| 14 | 1,985 | 1,417 | $0.036 |
| 19 | 1,985 | 323 | $0.014 |
| 20 | 1,985 | 485 | $0.018 |
| 22 | 1,985 | 451 | $0.017 |
| **Total** | **15,088** | **5,668** | **$0.17** |

The average is about $0.025 per page, with a range of $0.014 to $0.041. At that
average, the 27 pages covered by the rule would cost about $0.67.

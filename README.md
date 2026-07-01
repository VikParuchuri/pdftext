# PDFText

Text extraction like [PyMuPDF](https://github.com/pymupdf/PyMuPDF), but without the AGPL license.  PDFText extracts plain text or structured blocks and lines.  It's built on [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), so it's [fast, accurate](#benchmarks), and Apache licensed.

## Community

[Discord](https://discord.gg//KuZwXNGnfH) is where we discuss future development.

# Installation

You'll need python 3.10+ first.  Then run `pip install pdftext`.

# Usage

- Inspect the settings in `pdftext/settings.py`.  You can override any settings with environment variables.

## Plain text

This command will write out a text file with the extracted plain text.

```shell
pdftext PDF_PATH --out_path output.txt
```

- `PDF_PATH` must be a single pdf file.
- `--out_path` path to the output txt file.  If not specified, will write to stdout.
- `--sort` will attempt to sort in reading order if specified.
- `--keep_hyphens` will keep hyphens in the output (they will be stripped and words joined otherwise)
- `--page_range` will specify pages (comma separated) to extract.  Like `0,5-10,12`.
- `--workers` specifies the number of parallel workers to use
- `--flatten_pdf` merges form fields into the PDF
- `--password` password for encrypted PDFs

## JSON

This command outputs structured blocks and lines with font and other information.

```shell
pdftext PDF_PATH --out_path output.txt --json
```

- `PDF_PATH` must be a single pdf file.
- `--out_path` path to the output txt file.  If not specified, will write to stdout.
- `--json` specifies json output
- `--sort` will attempt to sort in reading order if specified.
- `--page_range` will specify pages (comma separated) to extract.  Like `0,5-10,12`.
- `--keep_chars` will keep individual characters in the json output
- `--workers` specifies the number of parallel workers to use
- `--flatten_pdf` merges form fields into the PDF
- `--password` password for encrypted PDFs

The output will be a json list, with each item in the list corresponding to a single page in the input pdf (in order).  Each page will include the following keys:

- `bbox` - the page bbox, in `[x1, y1, x2, y2]` format
- `rotation` - how much the page is rotated, in degrees (`0`, `90`, `180`, or `270`)
- `page` - the index of the page
- `blocks` - the blocks that make up the text in the pdf.  Approximately equal to a paragraph.
  - `bbox` - the block bbox, in `[x1, y1, x2, y2]` format
  - `lines` - the lines inside the block
    - `bbox` - the line bbox, in `[x1, y1, x2, y2]` format
    - `spans` - the individual text spans in the line (text spans have the same font/weight/etc)
      - `text` - the text in the span, encoded in utf-8
      - `rotation` - how much the span is rotated, in radians (from pdfium's character angle)
      - `bbox` - the span bbox, in `[x1, y1, x2, y2]` format
      - `char_start_idx` - the start index of the first span character in the pdf
      - `char_end_idx` - the end index of the last span character in the pdf
      - `font` this is font info straight from the pdf, see [this pdfium code](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_text.h)
        - `size` - the size of the font used for the text
        - `weight` - font weight
        - `name` - font name, may be None
        - `flags` - font flags, in the format of the `PDF spec 1.7 Section 5.7.1 Font Descriptor Flags`

If the pdf is rotated, the bboxes will be relative to the rotated page (they're rotated after being extracted).

# Programmatic usage

Extract plain text:

```python
from pdftext.extraction import plain_text_output

text = plain_text_output(PDF_PATH, sort=False, hyphens=False, page_range=[1,2,3]) # Optional arguments explained above
```

Extract structured blocks and lines:

```python
from pdftext.extraction import dictionary_output

text = dictionary_output(PDF_PATH, sort=False, page_range=[1,2,3], keep_chars=False) # Optional arguments explained above
```

Extract text from table cells:

```python
from pdftext.extraction import table_output

table_inputs = [
  # Each dictionary entry is a single page
  {
    "tables": [[5,10,10,20]], # Coordinates for tables on the page
    "img_size": [512, 512] # The size of the image the tables were detected in
  }
]
text = table_output(PDF_PATH, table_inputs, page_range=[1,2,3])

```

Encrypted PDFs can be opened by passing `password=` to any of the functions above (or `--password` on the CLI).

If you want more customization, check out the `pdftext.extraction._get_pages` function for a starting point to dig deeper.  pdftext is a pretty thin wrapper around [pypdfium2](https://pypdfium2.readthedocs.io/en/stable/), so you might want to look at the documentation for that as well.

# Language support

pdftext extracts whatever character ordering and Unicode mapping the PDF (via pdfium) provides:

- CJK, Cyrillic, Greek, Vietnamese, and other left-to-right scripts extract correctly.
- Right-to-left scripts (Arabic, Hebrew) are returned in the order pdfium reports them — usually visual order, i.e. reversed relative to logical reading order.  pdfium does not perform bidi reordering (PyMuPDF does, which is the main extraction-quality difference between the two for RTL documents).
- Complex-script fidelity (e.g. Indic conjuncts) and emoji depend entirely on the PDF's ToUnicode map; a broken map produces the same garbled output in any extractor.

# Concurrency

pdfium is **not thread-safe** — do not call pdftext from multiple threads at once, even on different files; extractions will fail or corrupt each other.  For parallelism, use the built-in `workers=` option (process-based) or your own process pool.

Notes on `workers=`:

- Parallel extraction only kicks in when each worker would get at least 10 pages (configurable via the `PDFTEXT_WORKER_PAGE_THRESHOLD` env var); smaller documents run serially regardless of `workers`.
- On macOS and Windows (spawn start method), scripts that call pdftext with `workers=` must be wrapped in an `if __name__ == "__main__":` guard, per the standard `multiprocessing` rules.
- File-like inputs can't be sent to workers; they run serially.  Pass a path for parallel extraction.

# Benchmarks

I benchmarked extraction speed and accuracy of [pymupdf](https://pymupdf.readthedocs.io/en/latest/), [pdfplumber](https://github.com/jsvine/pdfplumber), and pdftext.  I chose pymupdf because it extracts blocks and lines.  Pdfplumber extracts words and bboxes.  I did not benchmark pypdf, even though it is a great library, because it doesn't provide individual character/line/block and bbox information.

Here are the scores, run on an Apple Silicon Macbook, without multiprocessing:

| Library    | Time (s per doc) | Alignment Score (% accuracy vs pymupdf) |
|------------|------------------|-----------------------------------------|
| pymupdf    | 0.34             | --                                      |
| pdftext    | 0.69             | 97.54                                   |
| pdfplumber | 3.40             | 90.16                                   |

pdftext is approximately 1.5-2x slower than using pypdfium2 alone (if you were to extract all the same character information without any grouping into spans/lines/blocks).

There are additional benchmarks for pypdfium2 and other tools [here](https://github.com/py-pdf/benchmarks).

## Methodology

I used a benchmark set of 200 pdfs extracted from [common crawl](https://huggingface.co/datasets/pixparse/pdfa-eng-wds), then processed by a team at HuggingFace.

For each library, I used a detailed extraction method, to pull out font information, as well as just the words.  This ensured we were comparing similar performance numbers.  I formatted the text similarly when extracting - newlines after lines, and double newlines after blocks.  For pdfplumber, I could only do the newlines after lines, since it doesn't recognize blocks.

For the alignment score, I extracted the text, then used the rapidfuzz library to find the alignment percentage.  I used the text extracted by pymupdf as the pseudo-ground truth.

## Running benchmarks

You can run the benchmarks yourself.  To do so, you have to first install pdftext manually.  The install assumes you have poetry and Python 3.9+ installed.

```shell
git clone https://github.com/VikParuchuri/pdftext.git
cd pdftext
poetry install
python benchmark/benchmark.py # Will download the benchmark pdfs automatically
```

The benchmark script has a few options:

- `--max` this controls the maximum number of pdfs to benchmark
- `--result_path` a folder to save the results.  A file called `results.json` will be created in the folder.
- `--pdftext_only` skip running pdfplumber, which can be slow.
- `--pdftext_workers` number of parallel workers for pdftext.

# How it works

PDFText is a very light wrapper around pypdfium2.  It first uses pypdfium2 to extract characters in order, along with font and other information.  Then it uses heuristic rules to group characters into spans, lines, and blocks.  It does some simple postprocessing to clean up the text.

# Credits

This is built on some amazing open source work, including:

- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)
- [pypdf](https://github.com/py-pdf/benchmarks) for very thorough and fair benchmarks

Thank you to the [pymupdf](https://github.com/pymupdf/PyMuPDF) devs for creating such a great library - I just wish it had a simpler license!
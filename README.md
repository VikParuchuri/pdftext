# PDFText

Text extraction like [PyMuPDF](https://github.com/pymupdf/PyMuPDF), but without the AGPL license.  PDFText extracts plain text or structured blocks and lines.  It's built on [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), so it's [fast, accurate](#benchmarks), and Apache licensed.

## Community

[Discord](https://discord.gg//KuZwXNGnfH) is where we discuss future development.

# Installation

You'll need python 3.9+ first.  Then run `pip install pdftext`.

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
- `--pages` will specify pages (comma separated) to extract
- `--workers` specifies the number of parallel workers to use
- `--flatten_pdf` merges form fields into the PDF

## JSON

This command outputs structured blocks and lines with font and other information.

```shell
pdftext PDF_PATH --out_path output.txt --json
```

- `PDF_PATH` must be a single pdf file.
- `--out_path` path to the output txt file.  If not specified, will write to stdout.
- `--json` specifies json output
- `--sort` will attempt to sort in reading order if specified.
- `--pages` will specify pages (comma separated) to extract
- `--keep_chars` will keep individual characters in the json output
- `--workers` specifies the number of parallel workers to use
- `--flatten_pdf` merges form fields into the PDF

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
      - `rotation` - how much the span is rotated, in degrees
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

If you want more customization, check out the `pdftext.extraction._get_pages` function for a starting point to dig deeper.  pdftext is a pretty thin wrapper around [pypdfium2](https://pypdfium2.readthedocs.io/en/stable/), so you might want to look at the documentation for that as well.

# Benchmarks

I benchmarked extraction speed and accuracy of [pymupdf](https://pymupdf.readthedocs.io/en/latest/), [pdfplumber](https://github.com/jsvine/pdfplumber), and pdftext.  I chose pymupdf because it extracts blocks and lines.  Pdfplumber extracts words and bboxes.  I did not benchmark pypdf, even though it is a great library, because it doesn't provide individual character/line/block and bbox information.

Here are the scores, run on an M1 Macbook, without multiprocessing:

| Library    | Time (s per page) | Alignment Score (% accuracy vs pymupdf) |
|------------|-------------------|-----------------------------------------|
| pymupdf    | 0.32              | --                                      |
| pdftext    | 1.4               | 97.76                                   |
| pdfplumber | 3.0               | 90.3                                    |

pdftext is approximately 2x slower than using pypdfium2 alone (if you were to extract all the same character information).

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
python benchmark.py # Will download the benchmark pdfs automatically
```

The benchmark script has a few options:

- `--max` this controls the maximum number of pdfs to benchmark
- `--result_path` a folder to save the results.  A file called `results.json` will be created in the folder.
- `--pdftext_only` skip running pdfplumber, which can be slow.

# How it works

PDFText is a very light wrapper around pypdfium2.  It first uses pypdfium2 to extract characters in order, along with font and other information.  Then it uses a simple decision tree algorithm to group characters into lines and blocks.  It does some simple postprocessing to clean up the text.

# Credits

This is built on some amazing open source work, including:

- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)
- [scikit-learn](https://scikit-learn.org/stable/index.html)
- [pypdf](https://github.com/py-pdf/benchmarks) for very thorough and fair benchmarks

Thank you to the [pymupdf](https://github.com/pymupdf/PyMuPDF) devs for creating such a great library - I just wish it had a simpler license!
# PDFText

Text extraction like [PyMuPDF]((https://github.com/pymupdf/PyMuPDF), but without the AGPL license.  PDFText extracts plain text or structured blocks and lines.  It's built on [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), so it's [fast, accurate](#benchmarks), and Apache licensed.

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

## JSON

```shell
pdftext PDF_PATH --out_path output.txt --output_type json
```

- `PDF_PATH` must be a single pdf file.
- `--out_path` path to the output txt file.  If not specified, will write to stdout.
- `--output_type` specifies whether to write out plain text (default) or json
- `--sort` will attempt to sort in reading order if specified.

The output will be a json list, with each item in the list corresponding to a single page in the input pdf (in order).  Each page will include the following keys:

- `bbox` - the page bbox, in [x1, y1, x2, y2] format
- `rotation` - how much the page is rotated, in degrees (0, 90, 180, or 270)
- `page_idx` - the index of the page
- `blocks` - the blocks that make up the text in the pdf.  Approximately equal to a paragraph.
  - `bbox` - the block bbox, in [x1, y1, x2, y2] format
  - `lines` - the lines inside the block
    - `bbox` - the line bbox, in [x1, y1, x2, y2] format
    - `chars` - the individual characters in the line
      - `char` - the actual character, encoded in utf-8
      - `rotation` - how much the character is rotated, in degrees
      - `bbox` - the character bbox, in [x1, y1, x2, y2] format
      - `char_idx` - the index of the character on the page (from 0 to number of characters, in original pdf order)
      - `font` this is font info straight from the pdf, see [this pdfium code](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/public/fpdf_text.h)
        - `size` - the size of the font used for the character
        - `weight` - font weight
        - `name` - font name, may be None
        - `flags` - font flags, in the format of the `PDF spec 1.7 Section 5.7.1 Font Descriptor Flags`

# Programmatic usage

Extract plain text:

```python
from pdftext.extraction import plain_text_output

text = plain_text_output(PDF_PATH, sort=False)
```

Extract structured blocks and lines:

```python
from pdftext.extraction import dictionary_output

text = dictionary_output(PDF_PATH)
```

If you want more customization, check out the `pdftext.extraction._get_pages` function for a starting point to dig deeper.  pdftext is a pretty thin wrapper around [pypdfium2](https://pypdfium2.readthedocs.io/en/stable/), so you might want to look at the documentation for that as well.

# Benchmarks

I benchmarked extraction speed and accuracy of [pymupdf](https://pymupdf.readthedocs.io/en/latest/), [pdfplumber](https://github.com/jsvine/pdfplumber), and pdftext.

Here are the scores:

+------------+-------------------+-----------------------------------------+
|  Library   | Time (s per page) | Alignment Score (% accuracy vs pymupdf) |
+------------+-------------------+-----------------------------------------+
|  pymupdf   |       0.31        |                   --                    |
|  pdftext   |       1.55        |                  95.73                  |
| pdfplumber |       3.39        |                  89.55                  |
+------------+-------------------+-----------------------------------------+

pdftext is approximately 2x slower than using pypdfium2 alone (if you were to extract all the same information).

There are additional benchmarks for pypdfium2 and other tools [here](https://github.com/py-pdf/benchmarks).

## Methodology

I used a benchmark set of 200 pdfs extracted from [common crawl](https://huggingface.co/datasets/pixparse/pdfa-eng-wds), then processed by a team at HuggingFace.

For each library, I used a detailed extraction method, to pull out font information, as well as just the words.  This ensured we were comparing similar elements.

For the alignment score, I extracted the text, flattened it by removing all non-newline whitespace, then used the rapidfuzz library to find the alignment percentage.  I used the text extracted by pymupdf as the pseudo-ground truth.

# How it works

PDFText is a very light wrapper around pypdfium2.  It first uses pypdfium2 to extract characters in order, along with font and other information.  Then it uses a simple decision tree algorithm to group characters into lines and blocks.  It then done some simple postprocessing to clean up the text.

# Credits

This is built on some amazing open source work, including:

- [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)
- [scikit-learn](https://scikit-learn.org/stable/index.html)
- [pypdf2](https://github.com/py-pdf/benchmarks) for very thorough and fair benchmarks

Thank you to the [pymupdf](https://github.com/pymupdf/PyMuPDF) devs for creating such a great library - I just wish it had a simpler license!
# PDFText

Text extraction like PyMuPDF, but without the AGPL license.  PDFText extracts plain text or structured blocks and lines, similar to [PymuPDF](https://github.com/pymupdf/PyMuPDF).  It's built on [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), so it's [fast, accurate](https://github.com/py-pdf/benchmarks), and Apache licensed.

# Installation

You'll need python 3.9+ first.  Then run:

```shell
pip install pdftext
```

# CLI Usage

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



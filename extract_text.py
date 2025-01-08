import json
from pathlib import Path
from typing import List

import click
import pypdfium2 as pdfium

from pdftext.extraction import plain_text_output, dictionary_output

def parse_range_str(range_str: str) -> List[int]:
    range_lst = range_str.split(",")
    page_lst = []
    for i in range_lst:
        if "-" in i:
            start, end = i.split("-")
            page_lst += list(range(int(start), int(end) + 1))
        else:
            page_lst.append(int(i))
    page_lst = sorted(list(set(page_lst)))  # Deduplicate page numbers and sort in order
    return page_lst

@click.command(help="Extract plain text or JSON from PDF.")
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--out_path", type=click.Path(exists=False), help="Path to the output text file, defaults to stdout")
@click.option("--json", is_flag=True, help="Output json instead of plain text", default=False)
@click.option("--sort", is_flag=True, help="Attempt to sort the text by reading order", default=False)
@click.option("--keep_hyphens", is_flag=True, help="Keep hyphens in words", default=False)
@click.option("--page_range", type=str, help="Page numbers or ranges to extract, comma separated like 1,2-4,10", default=None)
@click.option("--flatten_pdf", is_flag=True, help="Flatten form fields and annotations into page contents", default=False)
@click.option("--keep_chars", is_flag=True, help="Keep character level information", default=False)
@click.option("--workers", type=int, help="Number of workers to use for parallel processing", default=None)
def main(
        pdf_path: Path,
        out_path: Path | None,
        **kwargs
):
    pages = None
    if kwargs["page_range"] is not None:
        pdf_doc = pdfium.PdfDocument(pdf_path)
        pages = parse_range_str(kwargs["page_range"])
        doc_len = len(pdf_doc)
        pdf_doc.close()
        assert all(0 <= p <= doc_len for p in pages), "Invalid page number(s) provided"

    if kwargs["json"]:
        text = dictionary_output(pdf_path, sort=kwargs["sort"], page_range=pages, flatten_pdf=kwargs["flatten_pdf"], keep_chars=kwargs["keep_chars"], workers=kwargs["workers"])
        text = json.dumps(text)
    else:
        text = plain_text_output(pdf_path, sort=kwargs["sort"], hyphens=kwargs["keep_hyphens"], page_range=pages, flatten_pdf=kwargs["flatten_pdf"], workers=kwargs["workers"])

    if out_path is None:
        print(text)
    else:
        with open(out_path, "w+") as f:
            f.write(text)


if __name__ == "__main__":
    main()

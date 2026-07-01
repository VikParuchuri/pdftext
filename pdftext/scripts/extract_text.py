import json
import sys
from pathlib import Path
from typing import List

import click
import pypdfium2 as pdfium

from pdftext.extraction import _load_pdf, plain_text_output, dictionary_output

def parse_range_str(range_str: str) -> List[int]:
    range_lst = range_str.split(",")
    page_lst = []
    for i in range_lst:
        try:
            if "-" in i:
                start, end = i.split("-")
                start, end = int(start), int(end)
                if start < 0 or start > end:
                    raise click.BadParameter(f"Invalid page range '{i}'; expected 'start-end' with 0 <= start <= end")
                page_lst += list(range(start, end + 1))
            else:
                page = int(i)
                if page < 0:
                    raise click.BadParameter(f"Invalid page number '{i}'; pages are 0-indexed")
                page_lst.append(page)
        except ValueError:
            raise click.BadParameter(f"Invalid page range token '{i}'; expected a number or 'start-end'")
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
@click.option("--password", type=str, help="Password for encrypted PDFs", default=None)
def extract_text_cli(
        pdf_path: Path,
        out_path: Path | None,
        **kwargs
):
    pages = None
    if kwargs["page_range"] is not None:
        pages = parse_range_str(kwargs["page_range"])
        pdf_doc = _load_pdf(pdf_path, False, password=kwargs["password"])
        try:
            doc_len = len(pdf_doc)
        finally:
            pdf_doc.close()
        bad_pages = [p for p in pages if not 0 <= p < doc_len]
        if bad_pages:
            raise click.BadParameter(f"Page number(s) {bad_pages} out of range; document has {doc_len} pages (0-indexed)")

    if kwargs["json"]:
        text = dictionary_output(
            pdf_path,
            sort=kwargs["sort"],
            page_range=pages,
            flatten_pdf=kwargs["flatten_pdf"],
            keep_chars=kwargs["keep_chars"],
            workers=kwargs["workers"],
            password=kwargs["password"],
            disable_links=True
        )
        text = json.dumps(text, ensure_ascii=False, indent=2)
    else:
        text = plain_text_output(
            pdf_path,
            sort=kwargs["sort"],
            hyphens=kwargs["keep_hyphens"],
            page_range=pages,
            flatten_pdf=kwargs["flatten_pdf"],
            workers=kwargs["workers"],
            password=kwargs["password"]
        )

    if out_path is None:
        # Write UTF-8 bytes directly so non-ASCII text doesn't crash on
        # consoles with a non-UTF-8 default encoding (e.g. cp1252 on Windows)
        buffer = getattr(sys.stdout, "buffer", None)
        if buffer is not None:
            buffer.write((text + "\n").encode("utf-8"))
            buffer.flush()
        else:
            print(text)
    else:
        with open(out_path, "w+", encoding="utf-8") as f:
            f.write(text)

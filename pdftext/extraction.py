import atexit
import math
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from itertools import repeat
from typing import List

import pypdfium2 as pdfium

from pdftext.pdf.links import add_links_and_refs
from pdftext.pdf.pages import get_pages
from pdftext.postprocessing import handle_hyphens, merge_text, postprocess_text, sort_blocks
from pdftext.schema import Pages, TableInputs, Tables
from pdftext.settings import settings
from pdftext.tables import table_cell_text


def _load_pdf(pdf, flatten_pdf):
    pdf = pdfium.PdfDocument(pdf)

    # Must be called on the parent pdf, before the page was retrieved
    if flatten_pdf:
        pdf.init_forms()

    return pdf


def _get_page_range(page_range, flatten_pdf=False, quote_loosebox=True) -> Pages:
    return get_pages(pdf_doc, page_range, flatten_pdf, quote_loosebox)


def worker_shutdown(pdf_doc):
    pdf_doc.close()


def worker_init(pdf_path, flatten_pdf):
    global pdf_doc

    pdf_doc = _load_pdf(pdf_path, flatten_pdf)

    atexit.register(partial(worker_shutdown, pdf_doc))


def _get_pages(pdf_path, page_range=None, flatten_pdf=False, quote_loosebox=True, workers=None) -> Pages:
    pdf_doc = _load_pdf(pdf_path, flatten_pdf)
    if page_range is None:
        page_range = range(len(pdf_doc))

    if workers is not None:
        workers = min(workers, len(page_range) // settings.WORKER_PAGE_THRESHOLD)  # It's inefficient to have too many workers, since we batch in inference

    if workers is None or workers <= 1:
        pages = get_pages(pdf_doc, page_range, flatten_pdf, quote_loosebox)
        pdf_doc.close()
        return pages

    pdf_doc.close()
    page_range = list(page_range)

    pages_per_worker = math.ceil(len(page_range) / workers)
    page_range_chunks = [page_range[i * pages_per_worker:(i + 1) * pages_per_worker] for i in range(workers)]

    with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(pdf_path, flatten_pdf)) as executor:
        pages = list(executor.map(_get_page_range, page_range_chunks, repeat(flatten_pdf), repeat(quote_loosebox)))

    ordered_pages = [page for sublist in pages for page in sublist]
    return ordered_pages


def plain_text_output(pdf_path, sort=False, hyphens=False, page_range=None, flatten_pdf=False, workers=None) -> str:
    text = paginated_plain_text_output(pdf_path, sort=sort, hyphens=hyphens, page_range=page_range, workers=workers, flatten_pdf=flatten_pdf)
    return "\n".join(text)


def paginated_plain_text_output(pdf_path, sort=False, hyphens=False, page_range=None, flatten_pdf=False, workers=None) -> List[str]:
    pages: Pages = _get_pages(pdf_path, page_range, workers=workers, flatten_pdf=flatten_pdf)
    text = []
    for page in pages:
        text.append(merge_text(page, sort=sort, hyphens=hyphens).strip())
    return text


def _process_span(span, page_width, page_height, keep_chars):
    span["bbox"] = span["bbox"].bbox
    span["text"] = handle_hyphens(postprocess_text(span["text"]), keep_hyphens=True)
    if not keep_chars:
        del span["chars"]
    else:
        for char in span["chars"]:
            char["bbox"] = char["bbox"].bbox


def dictionary_output(
        pdf_path,
        sort=False,
        page_range=None,
        keep_chars=False,
        flatten_pdf=False,
        quote_loosebox=True,
        disable_links=False,
        workers=None
) -> Pages:
    pages: Pages = _get_pages(pdf_path, page_range, workers=workers, flatten_pdf=flatten_pdf, quote_loosebox=quote_loosebox)

    if not disable_links:
        pdf = _load_pdf(pdf_path, False)
        add_links_and_refs(pages, pdf)
        pdf.close()

    for page in pages:
        page_width, page_height = page["width"], page["height"]
        for block in page["blocks"]:
            for k in list(block.keys()):
                if k not in ["lines", "bbox"]:
                    del block[k]
            block["bbox"] = block["bbox"].bbox
            for line in block["lines"]:
                for k in list(line.keys()):
                    if k not in ["spans", "bbox"]:
                        del line[k]
                line["bbox"] = line["bbox"].bbox
                for span in line["spans"]:
                    _process_span(span, page_width, page_height, keep_chars)

        if sort:
            page["blocks"] = sort_blocks(page["blocks"])

        if page["rotation"] == 90 or page["rotation"] == 270:
            page["width"], page["height"] = page["height"], page["width"]
            page["bbox"] = [page["bbox"][2], page["bbox"][3], page["bbox"][0], page["bbox"][1]]
    return pages


def table_output(
    pdf_path: str,
    table_inputs: TableInputs,
    page_range=None,
    flatten_pdf=False,
    quote_loosebox=True,
    workers=None,
    pages: Pages | None = None
) -> List[Tables]:
    # Extract pages if they don't exist
    if not pages:
        pages: Pages = dictionary_output(pdf_path, page_range=page_range, flatten_pdf=flatten_pdf, quote_loosebox=quote_loosebox, workers=workers, keep_chars=True)

    assert len(pages) == len(table_inputs), "Number of pages and table inputs must match"

    # Extract table cells per page
    out_tables = []
    for page, table_input in zip(pages, table_inputs):
        tables = table_cell_text(table_input["tables"], page, table_input["img_size"])
        assert len(tables) == len(table_input["tables"]), "Number of tables and table inputs must match"
        out_tables.append(tables)
    return out_tables

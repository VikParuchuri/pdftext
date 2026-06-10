import atexit
import math
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from functools import partial
from itertools import repeat
from typing import List

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.links import add_links_and_refs
from pdftext.pdf.pages import get_pages
from pdftext.postprocessing import handle_hyphens, merge_text, postprocess_text, sort_blocks
from pdftext.schema import Pages, PdfPasswordError, TableInputs, Tables
from pdftext.settings import settings
from pdftext.tables import table_cell_text


def _load_pdf(pdf, flatten_pdf, password=None):
    try:
        pdf = pdfium.PdfDocument(pdf, password=password)
    except pdfium.PdfiumError as e:
        if getattr(e, "err_code", None) == pdfium_c.FPDF_ERR_PASSWORD:
            raise PdfPasswordError(
                "PDF is encrypted; pass the correct password via the password argument."
            ) from e
        raise

    # Must be called on the parent pdf, before the page was retrieved
    if flatten_pdf:
        pdf.init_forms()

    return pdf


def _get_page_range(page_range, flatten_pdf=False, quote_loosebox=True) -> Pages:
    return get_pages(pdf_doc, page_range, flatten_pdf, quote_loosebox)


def worker_shutdown(pdf_doc):
    try:
        pdf_doc.close()
    except pdfium.PdfiumError:
        pass


def worker_init(pdf_path, flatten_pdf, password=None):
    global pdf_doc

    pdf_doc = _load_pdf(pdf_path, flatten_pdf, password=password)

    atexit.register(partial(worker_shutdown, pdf_doc))


def _validate_page_range(page_range, doc_len):
    invalid = [p for p in page_range if not 0 <= p < doc_len]
    if invalid:
        raise ValueError(
            f"Invalid page number(s) {invalid}; document has {doc_len} pages (0-indexed)."
        )


def _get_pages(pdf_path, page_range=None, flatten_pdf=False, quote_loosebox=True, workers=None, password=None) -> Pages:
    pdf_doc = _load_pdf(pdf_path, flatten_pdf, password=password)
    try:
        doc_len = len(pdf_doc)
        if page_range is None:
            page_range = range(doc_len)
        else:
            _validate_page_range(page_range, doc_len)

        if workers is not None:
            workers = min(workers, len(page_range) // settings.WORKER_PAGE_THRESHOLD)  # It's inefficient to have too many workers, since we batch in inference

        if workers is None or workers <= 1:
            return get_pages(pdf_doc, page_range, flatten_pdf, quote_loosebox)
    finally:
        pdf_doc.close()

    page_range = list(page_range)

    pages_per_worker = math.ceil(len(page_range) / workers)
    page_range_chunks = [page_range[i * pages_per_worker:(i + 1) * pages_per_worker] for i in range(workers)]

    with ProcessPoolExecutor(max_workers=workers, initializer=worker_init, initargs=(pdf_path, flatten_pdf, password)) as executor:
        try:
            pages = list(executor.map(_get_page_range, page_range_chunks, repeat(flatten_pdf), repeat(quote_loosebox)))
        except BrokenProcessPool as e:
            raise RuntimeError(
                f"A worker process died while extracting {pdf_path}; "
                "retry with workers=None to see the underlying error."
            ) from e

    ordered_pages = [page for sublist in pages for page in sublist]
    return ordered_pages


def plain_text_output(pdf_path, sort=False, hyphens=False, page_range=None, flatten_pdf=False, workers=None, password=None) -> str:
    text = paginated_plain_text_output(pdf_path, sort=sort, hyphens=hyphens, page_range=page_range, workers=workers, flatten_pdf=flatten_pdf, password=password)
    return "\n".join(text)


def paginated_plain_text_output(pdf_path, sort=False, hyphens=False, page_range=None, flatten_pdf=False, workers=None, password=None) -> List[str]:
    pages: Pages = _get_pages(pdf_path, page_range, workers=workers, flatten_pdf=flatten_pdf, password=password)
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
        workers=None,
        password=None
) -> Pages:
    pages: Pages = _get_pages(pdf_path, page_range, workers=workers, flatten_pdf=flatten_pdf, quote_loosebox=quote_loosebox, password=password)

    if not disable_links:
        pdf = _load_pdf(pdf_path, False, password=password)
        try:
            add_links_and_refs(pages, pdf)
        finally:
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
    pages: Pages | None = None,
    password=None
) -> List[Tables]:
    # Extract pages if they don't exist
    if not pages:
        pages: Pages = dictionary_output(pdf_path, page_range=page_range, flatten_pdf=flatten_pdf, quote_loosebox=quote_loosebox, workers=workers, keep_chars=True, password=password)

    if len(pages) != len(table_inputs):
        raise ValueError("Number of pages and table inputs must match")

    # Extract table cells per page
    out_tables = []
    for page, table_input in zip(pages, table_inputs):
        tables = table_cell_text(table_input["tables"], page, table_input["img_size"])
        if len(tables) != len(table_input["tables"]):
            raise ValueError("Number of tables and table inputs must match")
        out_tables.append(tables)
    return out_tables

import json
from pathlib import Path
from typing import List, Any

import click
import pypdfium2 as pdfium

from pdftext.extraction import plain_text_output, dictionary_output
from pdftext.schema import Pages, Bbox


# Helper function to serialize Bbox objects for JSON
def json_serializer(obj: Any) -> Any:
    if isinstance(obj, Bbox):
        return obj.bbox
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def parse_range_str(range_str: str) -> List[int]:
    range_lst = range_str.split(",")
    page_lst: List[int] = []
    for i in range_lst:
        if "-" in i:
            start, end = i.split("-")
            page_lst.extend(list(range(int(start), int(end) + 1)))
        else:
            page_lst.append(int(i))
    # Deduplicate page numbers and sort in order
    page_lst = sorted(list(set(page_lst)))
    return page_lst


@click.command(help="Extract plain text or JSON from PDF.")
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option(
    "--out_path",
    type=click.Path(exists=False),
    help="Path to the output text file, defaults to stdout"
)
@click.option(
    "--json",
    is_flag=True,
    help="Output json instead of plain text",
    default=False
)
@click.option(
    "--sort",
    is_flag=True,
    help="Attempt to sort the text by reading order",
    default=False
)
@click.option(
    "--keep_hyphens",
    is_flag=True,
    help="Keep hyphens in words",
    default=False
)
@click.option(
    "--page_range",
    type=str,
    help="Page numbers or ranges to extract, comma separated like 1,2-4,10",
    default=None
)
@click.option(
    "--flatten_pdf",
    is_flag=True,
    help="Flatten form fields and annotations into page contents",
    default=False
)
@click.option(
    "--keep_chars",
    is_flag=True,
    help="Keep character level information",
    default=False
)
@click.option(
    "--workers",
    type=int,
    help="Number of workers to use for parallel processing",
    default=None
)
def extract_text_cli(
        pdf_path: Path,
        out_path: Path | None,
        **kwargs: Any
) -> None:
    pages: List[int] | None = None
    if kwargs["page_range"] is not None:
        pdf_doc = pdfium.PdfDocument(str(pdf_path))
        pages = parse_range_str(kwargs["page_range"])
        doc_len = len(pdf_doc)
        pdf_doc.close()
        # Ensure page numbers are 1-based for user input validation
        invalid_pages = [p for p in pages if not (1 <= p <= doc_len)]
        if invalid_pages:
            raise click.BadParameter(
                f"Invalid page number(s) provided: {invalid_pages}. "
                f"Document has {doc_len} pages."
            )

    output_text: str = ""
    if kwargs["json"]:
        dict_result: Pages = dictionary_output(
            str(pdf_path),
            sort=kwargs["sort"],
            page_range=pages,
            flatten_pdf=kwargs["flatten_pdf"],
            keep_chars=kwargs["keep_chars"],
            workers=kwargs["workers"],
            disable_links=True
        )
        # Convert Pydantic model to dict for JSON serialization
        # output_text = json.dumps(dict_result.model_dump())
        # Use the custom serializer for Bbox objects
        output_text = json.dumps(dict_result, default=json_serializer)
    else:
        output_text = plain_text_output(
            str(pdf_path),
            sort=kwargs["sort"],
            hyphens=kwargs["keep_hyphens"],
            page_range=pages,
            flatten_pdf=kwargs["flatten_pdf"],
            workers=kwargs["workers"]
        )

    if out_path is None:
        print(output_text)
    else:
        with open(str(out_path), "w+", encoding="utf-8") as f:
            f.write(output_text)
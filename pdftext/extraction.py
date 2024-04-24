import copy
from itertools import chain

from pdftext.inference import inference
from pdftext.model import get_model
from pdftext.pdf.chars import get_pdfium_chars
from pdftext.pdf.utils import unnormalize_bbox
from pdftext.postprocessing import merge_text, sort_blocks


def _get_pages(pdf_path):
    model = get_model()
    text_chars = get_pdfium_chars(pdf_path)
    pages = inference(text_chars, model)
    return pages


def plain_text_output(pdf_path, sort=False):
    pages = _get_pages(pdf_path)
    text = ""
    for page in pages:
        text += merge_text(page, sort=sort).strip() + "\n"
    return text


def dictionary_output(pdf_path, sort=False):
    pages = _get_pages(pdf_path)
    merged_pages = []
    for page in pages:
        merged_page = {
            "page_idx": page["page"],
            "rotation": page["rotation"],
            "bbox": page["bbox"],
            "blocks": []
        }
        for block in page["blocks"]:
            merged_lines = []
            for line in block["lines"]:
                chars = [s["chars"] for s in line["spans"]]
                chars = chain.from_iterable(chars)
                line["chars"] = chars
                del line["spans"]
                line["bbox"] = unnormalize_bbox(line["bbox"], page["bbox"])
            block["lines"] = merged_lines
            block["bbox"] = unnormalize_bbox(block["bbox"], page["bbox"])
            merged_page["blocks"].append(block)
        if sort:
            merged_page["blocks"] = sort_blocks(merged_page["blocks"])
        merged_pages.append(merged_page)
    return merged_pages

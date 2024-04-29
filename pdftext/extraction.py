from typing import List

from pdftext.inference import inference
from pdftext.model import get_model
from pdftext.pdf.chars import get_pdfium_chars
from pdftext.pdf.utils import unnormalize_bbox
from pdftext.postprocessing import merge_text, sort_blocks, postprocess_text, handle_hyphens


def _get_pages(pdf_path, model=None):
    if model is None:
        model = get_model()
    text_chars = get_pdfium_chars(pdf_path)
    pages = inference(text_chars, model)
    return pages


def plain_text_output(pdf_path, sort=False, model=None, hyphens=False) -> str:
    text = paginated_plain_text_output(pdf_path, sort=sort, model=model, hyphens=hyphens)
    return "\n".join(text)


def paginated_plain_text_output(pdf_path, sort=False, model=None, hyphens=False) -> List[str]:
    pages = _get_pages(pdf_path, model)
    text = []
    for page in pages:
        text.append(merge_text(page, sort=sort, hyphens=hyphens).strip())
    return text


def dictionary_output(pdf_path, sort=False, model=None):
    pages = _get_pages(pdf_path, model)
    for page in pages:
        for block in page["blocks"]:
            bad_keys = [key for key in block.keys() if key not in ["lines", "bbox"]]
            for key in bad_keys:
                del block[key]
            for line in block["lines"]:
                bad_keys = [key for key in line.keys() if key not in ["bbox", "spans"]]
                for key in bad_keys:
                    del line[key]
                for span in line["spans"]:
                    span["bbox"] = unnormalize_bbox(span["bbox"], page["width"], page["height"])
                    span["text"] = postprocess_text(span["text"])
                    span["text"] = handle_hyphens(span["text"], keep_hyphens=True)

                line["bbox"] = unnormalize_bbox(line["bbox"], page["width"], page["height"])
            block["bbox"] = unnormalize_bbox(block["bbox"], page["width"], page["height"])
        if sort:
            page["blocks"] = sort_blocks(page["blocks"])
    return pages

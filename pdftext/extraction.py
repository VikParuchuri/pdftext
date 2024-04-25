from pdftext.inference import inference
from pdftext.model import get_model
from pdftext.pdf.chars import get_pdfium_chars
from pdftext.pdf.utils import unnormalize_bbox
from pdftext.postprocessing import merge_text, sort_blocks, postprocess_text


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
    for page in pages:
        for block in page["blocks"]:
            bad_keys = [key for key in block.keys() if key not in ["lines", "bbox"]]
            for key in bad_keys:
                del block[key]
            for line in block["lines"]:
                line_box = None
                bad_keys = [key for key in line.keys() if key not in ["chars", "bbox"]]
                for key in bad_keys:
                    del line[key]
                for char in line["chars"]:
                    char["bbox"] = unnormalize_bbox(char["bbox"], page["bbox"])
                    char["char"] = postprocess_text(char["char"])
                    if line_box is None:
                        line_box = char["bbox"]
                    else:
                        line_box = [
                            min(line_box[0], char["bbox"][0]),
                            min(line_box[1], char["bbox"][1]),
                            max(line_box[2], char["bbox"][2]),
                            max(line_box[3], char["bbox"][3]),
                        ]
                line["bbox"] = line_box
            block["bbox"] = unnormalize_bbox(block["bbox"], page["bbox"])
        if sort:
            page["blocks"] = sort_blocks(page["blocks"])
    return pages

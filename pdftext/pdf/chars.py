import math
from collections import defaultdict

from pdftext.pdf.utils import get_fontname, page_to_device, page_bbox_to_device_bbox
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


def get_pdfium_chars(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    blocks = []
    for page_idx in range(len(pdf)):
        page = pdf.get_page(page_idx)
        text_page = page.get_textpage()

        text_chars = defaultdict(list)
        text_chars["page"] = page_idx
        text_chars["rotation"] = page.get_rotation()
        bbox = page.get_bbox()
        text_chars["bbox"] = page_bbox_to_device_bbox(page, bbox, normalize=False)

        for i in range(text_page.count_chars()):
            char = pdfium_c.FPDFText_GetUnicode(text_page, i)
            char = chr(char)
            fontsize = pdfium_c.FPDFText_GetFontSize(text_page, i)
            fontweight = pdfium_c.FPDFText_GetFontWeight(text_page, i)
            fontname, fontflags = get_fontname(text_page, i)
            rotation = pdfium_c.FPDFText_GetCharAngle(text_page, i)
            rotation = rotation * 180 / math.pi # convert from radians to degrees
            coords = text_page.get_charbox(i, loose=True)
            device_coords = page_bbox_to_device_bbox(page, coords)
            char_info = {
                "font": {
                    "size": fontsize,
                    "weight": fontweight,
                    "name": fontname,
                    "flags": fontflags
                },
                "rotation": rotation,
                "char": char,
                "origin": coords,
                "bbox": device_coords,
                "char_idx": i
            }
            text_chars["chars"].append(char_info)
        blocks.append(text_chars)
    return blocks
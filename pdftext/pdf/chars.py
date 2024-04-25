import decimal
import math
from collections import defaultdict

from pdftext.pdf.utils import get_fontname, pdfium_page_bbox_to_device_bbox
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


def get_pdfium_chars(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    blocks = []

    for page_idx in range(len(pdf)):
        page = pdf.get_page(page_idx)
        text_page = page.get_textpage()

        bbox = page.get_bbox()
        page_width = math.ceil(bbox[2] - bbox[0])
        page_height = math.ceil(abs(bbox[1] - bbox[3]))

        text_chars = {
            "chars": [],
            "page": page_idx,
            "rotation": page.get_rotation(),
            "bbox": pdfium_page_bbox_to_device_bbox(page, bbox, page_width, page_height)
        }

        prev_bbox = None
        x_gaps = decimal.Decimal(0)
        y_gaps = decimal.Decimal(0)
        total_chars = text_page.count_chars()
        for i in range(total_chars):
            char = pdfium_c.FPDFText_GetUnicode(text_page, i)
            char = chr(char)
            fontsize = pdfium_c.FPDFText_GetFontSize(text_page, i)
            fontweight = pdfium_c.FPDFText_GetFontWeight(text_page, i)
            fontname, fontflags = get_fontname(text_page, i)
            rotation = pdfium_c.FPDFText_GetCharAngle(text_page, i)
            rotation = rotation * 180 / math.pi # convert from radians to degrees
            coords = text_page.get_charbox(i, loose=True)
            device_coords = pdfium_page_bbox_to_device_bbox(page, coords, page_width, page_height, normalize=True)

            char_info = {
                "font": {
                    "size": fontsize,
                    "weight": fontweight,
                    "name": fontname,
                    "flags": fontflags
                },
                "rotation": rotation,
                "char": char,
                "bbox": device_coords,
                "char_idx": i
            }
            text_chars["chars"].append(char_info)

            if prev_bbox:
                x_gaps += decimal.Decimal(device_coords[0] - prev_bbox[2])
                y_gaps += decimal.Decimal(device_coords[1] - prev_bbox[3])
            prev_bbox = device_coords

        text_chars["avg_x_gap"] = float(x_gaps / total_chars) if total_chars > 0 else 0
        text_chars["avg_y_gap"] = float(y_gaps / total_chars) if total_chars > 0 else 0
        text_chars["total_chars"] = total_chars
        blocks.append(text_chars)
    return blocks
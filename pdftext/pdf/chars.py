import decimal
import math
from typing import Dict

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import get_fontname, pdfium_page_bbox_to_device_bbox, page_bbox_to_device_bbox
from pdftext.settings import settings


def update_previous_fonts(text_chars: Dict, i: int, fontname: str, fontflags: int, prev_fontname: str, text_page, fontname_sample_freq: int):
    min_update = max(0, i - fontname_sample_freq + 1) # Minimum index to update
    regather_font_info = fontname != prev_fontname
    for j in range(min_update, i): # Goes from min_update to i - 1
        if regather_font_info:
            fontname, fontflags = get_fontname(text_page, j)

        # If we hit the region with the previous fontname, we can bail out
        if fontname == prev_fontname:
            break
        text_chars["chars"][j]["font"]["name"] = fontname
        text_chars["chars"][j]["font"]["flags"] = fontflags


def get_pdfium_chars(pdf_path, fontname_sample_freq=settings.FONTNAME_SAMPLE_FREQ):
    pdf = pdfium.PdfDocument(pdf_path)
    blocks = []

    for page_idx in range(len(pdf)):
        page = pdf.get_page(page_idx)
        text_page = page.get_textpage()
        mediabox = page.get_mediabox()
        page_rotation = page.get_rotation()
        bbox = page.get_bbox()
        page_width = math.ceil(abs(bbox[2] - bbox[0]))
        page_height = math.ceil(abs(bbox[1] - bbox[3]))
        bbox = pdfium_page_bbox_to_device_bbox(page, bbox, page_width, page_height, page_rotation)

        # Recalculate page width and height with new bboxes
        page_width = math.ceil(abs(bbox[2] - bbox[0]))
        page_height = math.ceil(abs(bbox[1] - bbox[3]))

        # Flip width and height if rotated
        if page_rotation == 90 or page_rotation == 270:
            page_width, page_height = page_height, page_width

        bl_origin = all([
            mediabox[0] == 0,
            mediabox[1] == 0
        ])

        text_chars = {
            "chars": [],
            "page": page_idx,
            "rotation": page_rotation,
            "bbox": bbox,
            "width": page_width,
            "height": page_height,
        }

        fontname = None
        fontflags = None
        total_chars = text_page.count_chars()
        for i in range(total_chars):
            char = pdfium_c.FPDFText_GetUnicode(text_page, i)
            char = chr(char)
            fontsize = round(pdfium_c.FPDFText_GetFontSize(text_page, i), 1)
            fontweight = round(pdfium_c.FPDFText_GetFontWeight(text_page, i), 1)
            if fontname is None or i % fontname_sample_freq == 0:
                prev_fontname = fontname
                fontname, fontflags = get_fontname(text_page, i)
                update_previous_fonts(text_chars, i, fontname, fontflags, prev_fontname, text_page, fontname_sample_freq)

            rotation = pdfium_c.FPDFText_GetCharAngle(text_page, i)
            rotation = rotation * 180 / math.pi # convert from radians to degrees
            coords = text_page.get_charbox(i, loose=False)
            device_coords = page_bbox_to_device_bbox(page, coords, page_width, page_height, bl_origin, page_rotation, normalize=True)

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

        text_chars["total_chars"] = total_chars
        blocks.append(text_chars)
    return blocks
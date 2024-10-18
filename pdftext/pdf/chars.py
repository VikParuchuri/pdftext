import math
from collections import defaultdict
from typing import Dict, List

import pypdfium2.raw as pdfium_c
from pypdfium2 import PdfiumError

from pdftext.pdf.utils import get_fontname, pdfium_page_bbox_to_device_bbox, page_bbox_to_device_bbox
from pdftext.settings import settings


def update_previous_fonts(char_infos: List, i: int, prev_fontname: str, prev_fontflags: int, text_page, fontname_sample_freq: int):
    min_update = max(0, i - fontname_sample_freq) # Minimum index to update
    for j in range(i-1, min_update, -1): # Goes from i to min_update
        fontname, fontflags = get_fontname(text_page, j)

        # If we hit the region with the previous fontname, we can bail out
        if fontname == prev_fontname and fontflags == prev_fontflags:
            break
        char_infos[j]["font"]["name"] = fontname
        char_infos[j]["font"]["flags"] = fontflags


def flatten(page, flag=pdfium_c.FLAT_NORMALDISPLAY):
    rc = pdfium_c.FPDFPage_Flatten(page, flag)
    if rc == pdfium_c.FLATTEN_FAIL:
        raise PdfiumError("Failed to flatten annotations / form fields.")


def get_pdfium_chars(pdf, page_range, flatten_pdf, fontname_sample_freq=settings.FONTNAME_SAMPLE_FREQ):
    blocks = []

    for page_idx in page_range:
        page = pdf.get_page(page_idx)

        if flatten_pdf:
            # Flatten form fields and annotations into page contents.
            flatten(page)

            # Flattening invalidates existing handles to the page.
            # It is necessary to re-initialize the page handle after flattening.
            page = pdf.get_page(page_idx)
        
        text_page = page.get_textpage()
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

        text_chars = {
            "page": page_idx,
            "rotation": page_rotation,
            "bbox": bbox,
            "width": page_width,
            "height": page_height,
        }

        # For pypdfium bbox function later
        page_width = math.ceil(page_width)
        page_height = math.ceil(page_height)

        fontname = None
        fontflags = None
        total_chars = text_page.count_chars()
        char_infos = []
        rad_to_deg = 180 / math.pi

        for i in range(total_chars):
            char = pdfium_c.FPDFText_GetUnicode(text_page, i)
            char = chr(char)
            fontsize = round(pdfium_c.FPDFText_GetFontSize(text_page, i), 1)
            fontweight = round(pdfium_c.FPDFText_GetFontWeight(text_page, i), 1)
            if fontname is None or i % fontname_sample_freq == 0:
                prev_fontname = fontname
                prev_fontflags = fontflags
                fontname, fontflags = get_fontname(text_page, i)
                if (fontname != prev_fontname or fontflags != prev_fontflags) and i > 0:
                    update_previous_fonts(char_infos, i, prev_fontname, prev_fontflags, text_page, fontname_sample_freq)

            rotation = pdfium_c.FPDFText_GetCharAngle(text_page, i)
            rotation = rotation * rad_to_deg # convert from radians to degrees
            coords = text_page.get_charbox(i, loose=rotation == 0) # Loose doesn't work properly when charbox is rotated
            device_coords = page_bbox_to_device_bbox(page, coords, page_width, page_height, page_rotation, normalize=True)

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
            char_infos.append(char_info)

        text_chars["chars"] = char_infos
        text_chars["total_chars"] = total_chars
        blocks.append(text_chars)
    return blocks
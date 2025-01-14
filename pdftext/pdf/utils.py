from ctypes import byref, c_int, create_string_buffer
from typing import List

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

LINE_BREAKS = ["\n", "\u000D", "\u000A"]
TABS = ["\t", "\u0009", "\x09"]
SPACES = [" ", "\ufffe", "\uFEFF", "\xa0"]
WHITESPACE_CHARS = ["\n", "\r", "\f", "\t", " "]


def flatten(page, flag=pdfium_c.FLAT_NORMALDISPLAY):
    rc = pdfium_c.FPDFPage_Flatten(page, flag)
    if rc == pdfium_c.FLATTEN_FAIL:
        raise pdfium.PdfiumError("Failed to flatten annotations / form fields.")


def get_fontname(textpage, i):
    font_name_str = ""
    flags = 0
    try:
        buffer_size = 256
        font_name = create_string_buffer(buffer_size)
        font_flags = c_int()

        length = pdfium_c.FPDFText_GetFontInfo(textpage, i, font_name, buffer_size, byref(font_flags))
        if length > buffer_size:
            font_name = create_string_buffer(length)
            pdfium_c.FPDFText_GetFontInfo(textpage, i, font_name, length, byref(font_flags))

        if length > 0:
            font_name_str = font_name.value.decode('utf-8')
            flags = font_flags.value
    except:
        pass
    return font_name_str, flags


def matrix_intersection_area(boxes1: List[List[float]], boxes2: List[List[float]]) -> np.ndarray:
    if len(boxes1) == 0 or len(boxes2) == 0:
        return np.zeros((len(boxes1), len(boxes2)))

    boxes1 = np.array(boxes1)
    boxes2 = np.array(boxes2)

    boxes1 = boxes1[:, np.newaxis, :]  # Shape: (N, 1, 4)
    boxes2 = boxes2[np.newaxis, :, :]  # Shape: (1, M, 4)

    min_x = np.maximum(boxes1[..., 0], boxes2[..., 0])  # Shape: (N, M)
    min_y = np.maximum(boxes1[..., 1], boxes2[..., 1])
    max_x = np.minimum(boxes1[..., 2], boxes2[..., 2])
    max_y = np.minimum(boxes1[..., 3], boxes2[..., 3])

    width = np.maximum(0, max_x - min_x)
    height = np.maximum(0, max_y - min_y)

    return width * height  # Shape: (N, M)

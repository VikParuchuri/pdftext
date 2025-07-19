from ctypes import byref, c_int, create_string_buffer
import math
from typing import List, Tuple, Optional

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from pdftext.schema import Bbox

LINE_BREAKS = ["\n", "\u000D", "\u000A"]
TABS = ["\t", "\u0009", "\x09"]
SPACES = [" ", "\ufffe", "\uFEFF", "\xa0"]
WHITESPACE_CHARS = ["\n", "\r", "\f", "\t", " "]


def get_page_properties(
        page_bbox: list[float],
        page: pdfium.PdfPage,
        rotate: bool = False,
) -> Tuple[int, int, int, bool]:
    
    x_start, y_start, x_end, y_end = page_bbox

    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    page_rotation = 0
    try:
        page_rotation = page.get_rotation()
    except:
        pass


    # This is done to deliberately use in the situations where we don't want to make this transformation 
    # Ideally everywhere we compute the page properties, we should use this function 
    if rotate: 
        if page_rotation == 90 or page_rotation == 270:
            page_width, page_height = page_height, page_width
    
    mediabox = page.get_mediabox()

    bl_origin = mediabox[0] == 0 and mediabox[1] == 0

    return page_width, page_height, page_rotation, bl_origin

def remove_wrong_bboxes(
        transformed_bboxes: list[Bbox],
        page_bbox: list[float],
        page: pdfium.PdfPage,
        # page_idx: int,
) -> List[Optional[Bbox]]:
    
    _, _, page_rotation, _ = get_page_properties(page_bbox, page, rotate=True)

    # get_pos -> get_bbox. Hopefully correct.
    transformed_page_bbox = transform_bbox(page_bbox, page_rotation, page.get_bbox())

    correct_bboxes: List[Optional[Bbox]] = []
    for box_objs in transformed_bboxes:
        if box_objs: 
            new_pos = [0.0] * 4
            new_pos[0] = max(box_objs[0], transformed_page_bbox[0])
            new_pos[1] = max(box_objs[1], transformed_page_bbox[1])
            new_pos[2] = min(box_objs[2], transformed_page_bbox[2])
            new_pos[3] = min(box_objs[3], transformed_page_bbox[3])

            correct_bboxes.append(Bbox(new_pos))
        else:
            correct_bboxes.append(None)
            continue 
        
    correct_bboxes = [
        None if (box_objs is None or (box_objs[0] > box_objs[2]) or (box_objs[1] > box_objs[3])) else box_objs
        for box_objs in correct_bboxes
    ]

    correct_bboxes = [
    box_obj if (
            box_obj is not None and 
            box_obj[0] >= transformed_page_bbox[0] and 
            box_obj[1] >= transformed_page_bbox[1] and 
            box_obj[2] <= transformed_page_bbox[2] and 
            box_obj[3] <= transformed_page_bbox[3]
            ) 
            else None 
    for box_obj in correct_bboxes
    ]

    return correct_bboxes
    

def transform_bbox(
    page_bbox: list[float],
    page_rotation: int,
    bbox: tuple[float, float, float, float],
) -> Bbox:
    """
    Transform pdfium bbox to device bbox
    """
    x_start, y_start, x_end, y_end = page_bbox

    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))
    
    cx_start, cy_start, cx_end, cy_end = bbox

    cx_start -= x_start
    cx_end -= x_start
    cy_start -= y_start
    cy_end -= y_start

    ty_start = page_height - cy_start
    ty_end = page_height - cy_end

    bbox_coords = [
        min(cx_start, cx_end),
        min(ty_start, ty_end),
        max(cx_start, cx_end),
        max(ty_start, ty_end),
    ]

    return Bbox(bbox_coords).rotate(page_width, page_height, page_rotation)


def flatten(page: pdfium.PdfPage, flag: int = pdfium_c.FLAT_NORMALDISPLAY) -> None:
    rc = pdfium_c.FPDFPage_Flatten(page, flag)
    if rc == pdfium_c.FLATTEN_FAIL:
        raise pdfium.PdfiumError("Failed to flatten annotations / form fields.")


def get_fontname(textpage: pdfium.PdfTextPage, i: int) -> Tuple[str, int]:
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

    boxes1_np = np.array(boxes1)
    boxes2_np = np.array(boxes2)

    boxes1_np = boxes1_np[:, np.newaxis, :]  # Shape: (N, 1, 4)
    boxes2_np = boxes2_np[np.newaxis, :, :]  # Shape: (1, M, 4)

    min_x = np.maximum(boxes1_np[..., 0], boxes2_np[..., 0])  # Shape: (N, M)
    min_y = np.maximum(boxes1_np[..., 1], boxes2_np[..., 1])
    max_x = np.minimum(boxes1_np[..., 2], boxes2_np[..., 2])
    max_y = np.minimum(boxes1_np[..., 3], boxes2_np[..., 3])

    width = np.maximum(0, max_x - min_x)
    height = np.maximum(0, max_y - min_y)

    return width * height  # Shape: (N, M)

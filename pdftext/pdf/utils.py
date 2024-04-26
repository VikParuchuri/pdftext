import pypdfium2.raw as pdfium_c
import ctypes
import math

from pdftext.settings import settings

LINE_BREAKS = ["\n", "\u000D", "\u000A", "\u000C"]
TABS = ["\t", "\u0009"]
SPACES = [" ", "\ufffe", "\uFEFF", "\xa0"]
HYPHEN = "-"
WHITESPACE_CHARS = ["\n", "\r", "\f", "\t", " "]
LIGATURES = {
    "ﬀ": "ff",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬆ": "st",
    "ﬅ": "st",
}


def char_count(textpage, *rect):
    args = (textpage, *rect)
    n_chars = pdfium_c.FPDFText_GetBoundedText(*args, None, 0)
    if n_chars <= 0:
        return 0
    return n_chars


def normalize_bbox(bbox, page_bound):
    x1, y1, x2, y2 = bbox
    x1 = x1 / page_bound[2]
    y1 = y1 / page_bound[3]
    x2 = x2 / page_bound[2]
    y2 = y2 / page_bound[3]
    return x1, y1, x2, y2


def unnormalize_bbox(bbox, page_width, page_height):
    x1, y1, x2, y2 = bbox
    x1 = round(x1 * page_width, 1)
    y1 = round(y1 * page_height, 1)
    x2 = round(x2 * page_width, 1)
    y2 = round(y2 * page_height, 1)
    return x1, y1, x2, y2


def get_fontname(textpage, char_index):
    n_bytes = settings.FONT_BUFFER_SIZE
    buffer = ctypes.create_string_buffer(n_bytes)
    # Re-interpret the type from char to unsigned short as required by the function
    buffer_ptr = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ushort))
    flag_buffer = ctypes.c_int()
    flag_ptr = ctypes.pointer(flag_buffer)
    font_info = pdfium_c.FPDFText_GetFontInfo(textpage, char_index, buffer_ptr, n_bytes, flag_ptr)
    if font_info == 0:
        return None, None
    try:
        decoded = buffer.value.decode("utf-8")
    except Exception as e:
        return None, None
    return decoded, flag_buffer.value


def page_to_device(page, x, y, page_width, page_height, page_rotation: int):
    if page_rotation == 90:
        page_rotation = 1
    elif page_rotation == 180:
        page_rotation = 2
    elif page_rotation == 270:
        page_rotation = 3
    else:
        page_rotation = 0
    device_x = ctypes.c_int()
    device_y = ctypes.c_int()
    device_x_ptr = ctypes.pointer(device_x)
    device_y_ptr = ctypes.pointer(device_y)
    width = math.ceil(page_width)
    height = math.ceil(page_height)
    pdfium_c.FPDF_PageToDevice(page, 0, 0, width, height, page_rotation, x, y, device_x_ptr, device_y_ptr)
    x = device_x.value
    y = device_y.value
    return x, y


def pdfium_page_bbox_to_device_bbox(page, bbox, page_width, page_height, page_rotation):
    left_bottom = page_to_device(page, *bbox[:2], page_width, page_height, page_rotation)
    top_right = page_to_device(page, *bbox[2:], page_width, page_height, page_rotation)

    dev_bbox = [left_bottom[0], top_right[1], top_right[0], left_bottom[1]]
    return dev_bbox


def fast_page_bbox_to_device_bbox(page, bbox, page_width, page_height):
    left, bottom, right, top = bbox

    dev_bbox = [left, page_height-top, right, page_height-bottom]
    return dev_bbox


def page_bbox_to_device_bbox(page, bbox, page_width: int, page_height: int, bl_origin: bool, page_rotation: int, normalize=False):
    orig_page_height, orig_page_width = page_height, page_width
    if page_rotation in [90, 270]:
        orig_page_height, orig_page_width = page_width, page_height

    if bl_origin:
        bbox = fast_page_bbox_to_device_bbox(page, bbox, page_width, page_height)
        if page_rotation > 0:
            bbox = rotate_page_bbox(bbox, page_rotation, page_width, page_height)
    else:
        bbox = pdfium_page_bbox_to_device_bbox(page, bbox, orig_page_width, orig_page_height, page_rotation)
        if page_rotation > 0:
            bbox = rotate_pdfium_bbox(bbox, page_rotation, page_width, page_height)

    if normalize:
        bbox = [bbox[0] / page_width, bbox[1] / page_height, bbox[2] / page_width, bbox[3] / page_height]
    return bbox


def rotate_pdfium_bbox(bbox, angle_deg, width, height):
    x1, y1, x2, y2 = bbox
    if angle_deg == 90:
        bbox = [y1, x1, y2, x2]
        bbox = [bbox[2], height - bbox[1], bbox[0], height - bbox[3]]
    elif angle_deg == 180:
        bbox = [x2, y2, x1, y1]
        bbox = [width - bbox[0], height - bbox[1], width - bbox[2], height - bbox[3]]
    elif angle_deg == 270:
        bbox = rotate_pdfium_bbox(bbox, 90, width, height)
        bbox = rotate_pdfium_bbox(bbox, 180, width, height)

    return bbox


def rotate_page_bbox(bbox, angle_deg, width, height):
    x1, y1, x2, y2 = bbox
    if angle_deg == 90:
        bbox = [y1, x1, y2, x2]
        bbox = [height - bbox[2], bbox[1], height - bbox[0], bbox[3]]
    elif angle_deg == 180:
        bbox = [x2, y2, x1, y1]
        bbox = [width - bbox[0], height - bbox[1], width - bbox[2], height - bbox[3]]
    elif angle_deg == 270:
        bbox = rotate_page_bbox(bbox, 90, width, height)
        bbox = rotate_page_bbox(bbox, 180, width, height)

    return bbox
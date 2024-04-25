import pypdfium2.raw as pdfium_c
import ctypes
import math

LINE_BREAKS = ["\n", "\u000D", "\u000A", "\u000C"]
TABS = ["\t", "\u0009"]
SPACES = [" ", "\ufffe", "\uFEFF"]
HYPHEN = "-"
WHITESPACE_CHARS = ["\n", "\r", "\f", "\t", " "]


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


def unnormalize_bbox(bbox, page_bound):
    x1, y1, x2, y2 = bbox
    x1 = x1 * page_bound[2]
    y1 = y1 * page_bound[3]
    x2 = x2 * page_bound[2]
    y2 = y2 * page_bound[3]
    return x1, y1, x2, y2


def get_fontname(textpage, char_index):
    n_bytes = 1024
    # Initialise the output buffer - this function can work without null terminator, so skip it
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


def page_to_device(page, x, y, page_width, page_height):
    device_x = ctypes.c_int()
    device_y = ctypes.c_int()
    device_x_ptr = ctypes.pointer(device_x)
    device_y_ptr = ctypes.pointer(device_y)
    rotation = pdfium_c.FPDFPage_GetRotation(page)
    width = math.ceil(page_width)
    height = math.ceil(page_height)
    pdfium_c.FPDF_PageToDevice(page, 0, 0, width, height, rotation, x, y, device_x_ptr, device_y_ptr)
    x = device_x.value
    y = device_y.value
    return x, y


def pdfium_page_bbox_to_device_bbox(page, bbox, page_width, page_height, normalize=False):
    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    left_bottom = page_to_device(page, *bbox[:2], page_width, page_height)

    dev_bbox = [left_bottom[0], left_bottom[1] - bbox_height, left_bottom[0] + bbox_width, left_bottom[1]]   # Convert to ltrb
    if normalize:
        dev_bbox = [dev_bbox[0] / page_width, dev_bbox[1] / page_height, dev_bbox[2] / page_width, dev_bbox[3] / page_height]
    return dev_bbox
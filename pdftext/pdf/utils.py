from ctypes import byref, c_int, create_string_buffer

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

import math
from ctypes import c_double, c_int, create_string_buffer
from typing import Dict, List

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import get_fontname


class PageChars:
    """Char-level data for one page in column-oriented form.

    Coordinate transforms, rotation, and word deduplication operate on the
    arrays; char dicts are only materialized once per surviving span char.
    """
    __slots__ = ("text", "codes", "rotations", "boxes", "font_ids", "fonts", "char_indices")

    def __init__(self, text: str, codes, rotations, boxes, font_ids, fonts: List[Dict], char_indices):
        self.text = text                  # one python char per pdfium char
        self.codes = codes                # uint32[n] unicode code points
        self.rotations = rotations        # float64[n] radians from FPDFText_GetCharAngle
        self.boxes = boxes                # float64[n, 4] display-space x0, y0, x1, y1
        self.font_ids = font_ids          # int32[n] indices into fonts
        self.fonts = fonts                # interned font dicts, one per unique font
        self.char_indices = char_indices  # int64[n] original pdfium char indices

    def __len__(self):
        return len(self.codes)


def _empty_page_chars(fonts) -> PageChars:
    return PageChars(
        "",
        np.empty(0, np.uint32),
        np.empty(0, np.float64),
        np.empty((0, 4), np.float64),
        np.empty(0, np.int32),
        fonts,
        np.empty(0, np.int64),
    )


def get_chars(textpage: pdfium.PdfTextPage, page_bbox: list[float], page_rotation: int, quote_loosebox=True) -> PageChars:
    n = textpage.count_chars()

    x_start, y_start, x_end, y_end = page_bbox
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    # Hoist FFI lookups and reuse ctypes objects across the per-char loop;
    # pass the raw handle to skip pypdfium2's per-call auto-cast
    textpage_raw = textpage.raw
    get_unicode = pdfium_c.FPDFText_GetUnicode
    get_char_angle = pdfium_c.FPDFText_GetCharAngle
    get_loose_charbox = pdfium_c.FPDFText_GetLooseCharBox
    get_tight_charbox = pdfium_c.FPDFText_GetCharBox
    get_fontsize = pdfium_c.FPDFText_GetFontSize
    get_fontweight = pdfium_c.FPDFText_GetFontWeight
    loose_rect = pdfium_c.FS_RECTF()
    tight_l, tight_b, tight_r, tight_t = c_double(), c_double(), c_double(), c_double()
    font_buffer = create_string_buffer(256)
    font_flags = c_int()
    # Font info rarely changes between chars; intern one dict per unique font
    fonts: List[Dict] = []
    font_cache = {}

    codes = []
    rotations = []
    box_l = []
    box_b = []
    box_r = []
    box_t = []
    font_ids = []

    for i in range(n):
        code = get_unicode(textpage_raw, i)
        if 0xD800 <= code <= 0xDFFF:
            # Lone surrogates (from broken ToUnicode CMaps) can't be encoded
            # to UTF-8 and would crash JSON/file output downstream
            code = 0xFFFD

        rotation = get_char_angle(textpage_raw, i)
        loosebox = (rotation == 0) and (code != 39 or quote_loosebox)  # 39 == ord("'")

        if loosebox:
            ok = get_loose_charbox(textpage_raw, i, loose_rect)
            l, b, r, t = loose_rect.left, loose_rect.bottom, loose_rect.right, loose_rect.top
        else:
            ok = get_tight_charbox(textpage_raw, i, tight_l, tight_r, tight_b, tight_t)  # yes, lrbt!
            l, b, r, t = tight_l.value, tight_b.value, tight_r.value, tight_t.value
        if not ok:
            raise pdfium.PdfiumError("Failed to get charbox.")

        fontname, fontflag = get_fontname(textpage_raw, i, font_buffer, font_flags)
        fontsize = get_fontsize(textpage_raw, i)
        fontweight = get_fontweight(textpage_raw, i)

        font_key = (fontname, fontflag, fontsize, fontweight)
        font_id = font_cache.get(font_key)
        if font_id is None:
            font_id = len(fonts)
            font_cache[font_key] = font_id
            fonts.append({
                "name": fontname,
                "flags": fontflag,
                "size": fontsize,
                "weight": fontweight,
            })

        codes.append(code)
        rotations.append(rotation)
        box_l.append(l)
        box_b.append(b)
        box_r.append(r)
        box_t.append(t)
        font_ids.append(font_id)

    if n == 0:
        return _empty_page_chars(fonts)

    # Vectorized coordinate transform: origin shift, y flip, normalization
    l = np.fromiter(box_l, np.float64, n)
    b = np.fromiter(box_b, np.float64, n)
    r = np.fromiter(box_r, np.float64, n)
    t = np.fromiter(box_t, np.float64, n)

    cx_start = l - x_start
    cx_end = r - x_start
    ty_start = page_height - (b - y_start)
    ty_end = page_height - (t - y_start)

    x0 = np.minimum(cx_start, cx_end)
    y0 = np.minimum(ty_start, ty_end)
    x1 = np.maximum(cx_start, cx_end)
    y1 = np.maximum(ty_start, ty_end)

    # Mirrors Bbox.rotate for the whole page at once
    if page_rotation == 90:
        nx0, ny0, nx1, ny1 = page_height - y1, x0, page_height - y0, x1
    elif page_rotation == 180:
        nx0, ny0, nx1, ny1 = page_width - x1, page_height - y1, page_width - x0, page_height - y0
    elif page_rotation == 270:
        nx0, ny0, nx1, ny1 = y0, page_width - x1, y1, page_width - x0
    else:
        nx0, ny0, nx1, ny1 = x0, y0, x1, y1
    if page_rotation:
        x0 = np.minimum(nx0, nx1)
        y0 = np.minimum(ny0, ny1)
        x1 = np.maximum(nx0, nx1)
        y1 = np.maximum(ny0, ny1)
    else:
        x0, y0, x1, y1 = nx0, ny0, nx1, ny1

    codes_arr = np.fromiter(codes, np.uint32, n)
    return PageChars(
        "".join(map(chr, codes)),
        codes_arr,
        np.fromiter(rotations, np.float64, n),
        np.stack([x0, y0, x1, y1], axis=1),
        np.fromiter(font_ids, np.int32, n),
        fonts,
        np.arange(n, dtype=np.int64),
    )


# Word boundaries occur after these chars (linebreak, space, hyphen marker)
_WORD_BREAK_CODES = np.array([2, 10, 32], dtype=np.uint32)


def deduplicate_chars(chars: PageChars) -> PageChars:
    """Drops repeated words (same text/font/rotation at the same rounded
    position), e.g. fake-bold double rendering. Operates on word groups."""
    n = len(chars)
    if n == 0:
        return chars

    codes = chars.codes
    font_ids = chars.font_ids
    rotations = chars.rotations
    boxes = chars.boxes

    # A new word starts at 0 and wherever the previous char was a break
    # char, or the font/rotation changed
    starts = np.empty(n, dtype=bool)
    starts[0] = True
    starts[1:] = (
        np.isin(codes[:-1], _WORD_BREAK_CODES)
        | (font_ids[1:] != font_ids[:-1])
        | (rotations[1:] != rotations[:-1])
    )

    word_starts = np.flatnonzero(starts)
    word_ends = np.append(word_starts[1:], n)

    # Word bboxes: min/max over each word's char boxes
    wx0 = np.minimum.reduceat(boxes[:, 0], word_starts)
    wy0 = np.minimum.reduceat(boxes[:, 1], word_starts)
    wx1 = np.maximum.reduceat(boxes[:, 2], word_starts)
    wy1 = np.maximum.reduceat(boxes[:, 3], word_starts)

    text = chars.text
    seen = set()
    keep = np.zeros(len(word_starts), dtype=bool)
    for w in range(len(word_starts)):
        s = word_starts[w]
        key = (
            (round(float(wx0[w]), 0), round(float(wy0[w]), 0), round(float(wx1[w]), 0), round(float(wy1[w]), 0)),
            text[s:word_ends[w]],
            float(rotations[s]),
            int(font_ids[s]),  # interned per page, so id equality == font equality
        )
        if key not in seen:
            seen.add(key)
            keep[w] = True

    if keep.all():
        return chars

    char_keep = np.repeat(keep, word_ends - word_starts)
    codes_kept = codes[char_keep]
    return PageChars(
        "".join(map(chr, codes_kept.tolist())),
        codes_kept,
        rotations[char_keep],
        boxes[char_keep],
        font_ids[char_keep],
        chars.fonts,
        chars.char_indices[char_keep],
    )

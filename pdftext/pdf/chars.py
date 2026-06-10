import math
from ctypes import c_double, c_int, create_string_buffer

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import get_fontname
from pdftext.schema import Bbox, Char, Chars, Spans, Span


def get_chars(textpage: pdfium.PdfTextPage, page_bbox: list[float], page_rotation: int, quote_loosebox=True) -> Chars:
    chars: Chars = []

    x_start, y_start, x_end, y_end = page_bbox
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))
    rotated = page_rotation != 0

    # Hoist FFI lookups and reuse ctypes objects across the per-char loop
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
    # Font info rarely changes between chars; share one dict per unique font
    font_cache = {}

    for i in range(textpage.count_chars()):
        text = chr(get_unicode(textpage, i))

        rotation = get_char_angle(textpage, i)
        loosebox = (rotation == 0) and (text != "'" or quote_loosebox)

        if loosebox:
            ok = get_loose_charbox(textpage, i, loose_rect)
            cx_start, cy_start, cx_end, cy_end = loose_rect.left, loose_rect.bottom, loose_rect.right, loose_rect.top
        else:
            ok = get_tight_charbox(textpage, i, tight_l, tight_r, tight_b, tight_t)  # yes, lrbt!
            cx_start, cy_start, cx_end, cy_end = tight_l.value, tight_b.value, tight_r.value, tight_t.value
        if not ok:
            raise pdfium.PdfiumError("Failed to get charbox.")

        cx_start -= x_start
        cx_end -= x_start
        cy_start -= y_start
        cy_end -= y_start

        ty_start = page_height - cy_start
        ty_end = page_height - cy_end

        bbox_coords = [min(cx_start, cx_end), min(ty_start, ty_end), max(cx_start, cx_end), max(ty_start, ty_end)]
        bbox = Bbox(bbox_coords)
        if rotated:
            bbox = bbox.rotate(page_width, page_height, page_rotation)

        fontname, fontflag = get_fontname(textpage, i, font_buffer, font_flags)
        fontsize = get_fontsize(textpage, i)
        fontweight = get_fontweight(textpage, i)

        font_key = (fontname, fontflag, fontsize, fontweight)
        font = font_cache.get(font_key)
        if font is None:
            font = {
                "name": fontname,
                "flags": fontflag,
                "size": fontsize,
                "weight": fontweight,
            }
            font_cache[font_key] = font

        char_dict: Char = {
            "bbox": bbox,
            "char": text,
            "rotation": rotation,
            "font": font,
            "char_idx": i
        }
        chars.append(char_dict)

    return chars


def deduplicate_chars(chars: Chars) -> Chars:
    # we first construct words from the chars and then deduplicate them
    words: Spans = []
    word: Span = None

    def word_break():
        words.append({
            "bbox": char["bbox"].copy(),
            "text": char["char"],
            "rotation": char["rotation"],
            "font": char["font"],
            "char_start_idx": char["char_idx"],
            "char_end_idx": char["char_idx"],
            "chars": [char],
            "url": '',
        })

    for char in chars:
        if words:
            word = words[-1]

        if not word:
            word_break()
            continue

        # we also break on hyphenation
        if any(word['text'].endswith(x) for x in ['\n', ' ', '\x02']):
            word_break()
            continue

        # we break on any change in font info; fonts are interned per page,
        # so an identity check is the fast path
        char_font = char['font']
        word_font = word['font']
        if char_font is not word_font and any(char_font[k] != word_font[k] for k in ['name', 'flags', 'size', 'weight']):
            word_break()
            continue

        if char['rotation'] != word['rotation']:
            word_break()
            continue

        word['text'] += char['char']
        word['char_end_idx'] = char['char_idx']
        word['bbox'].merge_inplace(char['bbox'])
        word['chars'].append(char)

    # deduplicate words - use tuple keys instead of strings
    seen = set()
    deduped = []
    for word in words:
        # Round the bbox coordinates
        bbox = word['bbox'].bbox
        bbox_rounded = tuple(round(x, 0) for x in bbox)

        key = (bbox_rounded, word['text'], word['rotation'],
               word['font']['name'], word['font']['flags'],
               word['font']['size'], word['font']['weight'])
        if key not in seen:
            seen.add(key)
            deduped.append(word)

    return [char for word in deduped for char in word['chars']]

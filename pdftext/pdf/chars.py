import math

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import get_fontname
from pdftext.schema import Bbox, Char, Chars, Spans, Span


MAX_UNICODE_INT = 1114111  # 0x10ffff


def get_chars(textpage: pdfium.PdfTextPage, page_bbox: list[float], page_rotation: int, quote_loosebox=True) -> Chars:
    chars: Chars = []

    x_start, y_start, x_end, y_end = page_bbox
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    for i in range(textpage.count_chars()):
        text = utf8_int_to_string(pdfium_c.FPDFText_GetUnicode(textpage, i))

        rotation = pdfium_c.FPDFText_GetCharAngle(textpage, i)
        loosebox = (rotation == 0) and (text != "'" or quote_loosebox)

        char_box = textpage.get_charbox(i, loose=loosebox)
        cx_start, cy_start, cx_end, cy_end = char_box

        cx_start -= x_start
        cx_end -= x_start
        cy_start -= y_start
        cy_end -= y_start

        ty_start = page_height - cy_start
        ty_end = page_height - cy_end

        bbox_coords = [min(cx_start, cx_end), min(ty_start, ty_end), max(cx_start, cx_end), max(ty_start, ty_end)]
        bbox = Bbox(bbox_coords).rotate(page_width, page_height, page_rotation)

        fontname, fontflag = get_fontname(textpage, i)
        fontsize = pdfium_c.FPDFText_GetFontSize(textpage, i)
        fontweight = pdfium_c.FPDFText_GetFontWeight(textpage, i)

        char_dict: Char = {
            "bbox": bbox,
            "char": text,
            "rotation": rotation,
            "font": {
                "name": fontname,
                "flags": fontflag,
                "size": fontsize,
                "weight": fontweight,
            },
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
            "bbox": char["bbox"],
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

        # we break on any change in font info - optimized comparison
        char_font = char['font']
        word_font = word['font']
        if any(char_font[k] != word_font[k] for k in ['name', 'flags', 'size', 'weight']):
            word_break()
            continue

        if char['rotation'] != word['rotation']:
            word_break()
            continue

        word['text'] += char['char']
        word['char_end_idx'] = char['char_idx']
        word['bbox'] = word['bbox'].merge(char['bbox'])
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


def utf8_int_to_string(utf8_int: int) -> str:
    """Decode UTF-8 integer to string.
`
    PDFium's `FPDFText_GetUnicode` returns unsigned 32-bit integer. Integers ≤ 1114111 are valid
    Unicode codepoint and can be converted with python in-built `chr` function.
    Larger integers are UTF-8 bytes packed into integers and must be handled separately.

    Parameters
    ----------
    utf8_int
        Unsgined 32-bit ingeger value from FPDFText_GetUnicode that may be either a valid Unicode
        codepoint, or UTF-8 bytes packed as an integer.

    Returns
    -------
    The decoded character or string.

    Examples
    --------
    >>> utf8_int_to_string(65)  # Valid Unicode
    'A'
    >>> utf8_int_to_string(15112101)  # UTF-8 bytes for '日'
    '日'
    """
    if utf8_int <= MAX_UNICODE_INT:
        return chr(utf8_int)
    # Compute byte length using 8-bit ceiling
    byte_length = (utf8_int.bit_length() + 7) // 8
    bytes_obj = utf8_int.to_bytes(byte_length, "big")
    return bytes_obj.decode("utf-8")

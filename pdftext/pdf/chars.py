import math

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import get_fontname
from pdftext.schema import Bbox, Char, Chars, Spans, Span


def get_chars(textpage: pdfium.PdfTextPage, page_bbox: list[float], page_rotation: int, quote_loosebox=True) -> Chars:
    chars: Chars = []

    x_start, y_start, x_end, y_end = page_bbox
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    for i in range(textpage.count_chars()):
        text = chr(pdfium_c.FPDFText_GetUnicode(textpage, i))

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

        # we break on any change in font info
        if any(char['font'][k] != word['font'][k] for k in ['name', 'flags', 'size', 'weight']):
            word_break()
            continue

        if char['rotation'] != word['rotation']:
            word_break()
            continue

        word['text'] += char['char']
        word['char_end_idx'] = char['char_idx']
        word['bbox'] = word['bbox'].merge(char['bbox'])
        word['chars'].append(char)

    # deduplicate words
    seen = {}
    deduped = []
    for word in words:
        # Round the bbox coordinates
        bbox = word['bbox'].bbox
        bbox = [round(x, 0) for x in bbox]

        key = f"{bbox}-{word['text']}-{word['rotation']}-{word['font']['name']}-{word['font']['flags']}-{word['font']['size']}-{word['font']['weight']}"
        if key not in seen:
            seen[key] = True
            deduped.append(word)

    return [char for word in deduped for char in word['chars']]

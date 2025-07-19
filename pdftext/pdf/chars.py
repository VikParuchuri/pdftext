import ctypes
import math
from typing import Optional

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from pypdfium2.raw import c_uint

from pdftext.pdf.utils import get_fontname, transform_bbox
from pdftext.schema import Bbox, Char, Chars, Spans, Span

def get_chars(
    textpage: pdfium.PdfTextPage,
    page_bbox: list[float],
    page_rotation: int,
    quote_loosebox: bool = True,
) -> Chars:
    chars: Chars = []

    x_start, y_start, x_end, y_end = page_bbox
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    for i in range(textpage.count_chars()):
        text = chr(pdfium_c.FPDFText_GetUnicode(textpage, i))

        rotation = pdfium_c.FPDFText_GetCharAngle(textpage, i)
        loosebox = (rotation == 0) and (text != "'" or quote_loosebox)

        char_box = textpage.get_charbox(i, loose=loosebox)

        bbox = transform_bbox(page_bbox, page_rotation, char_box)

        fontname, fontflag = get_fontname(textpage, i)
        fontsize = pdfium_c.FPDFText_GetFontSize(textpage, i)
        fontweight = pdfium_c.FPDFText_GetFontWeight(textpage, i)
        fontcolor = [c_uint()]*4  # r, g, b, a
        is_fillcolor = round(
            pdfium_c.FPDFText_GetFillColor(
                textpage,
                i,
                ctypes.byref(fontcolor[0]),
                ctypes.byref(fontcolor[1]),
                ctypes.byref(fontcolor[2]),
                ctypes.byref(fontcolor[3]),
            )
        )
        if is_fillcolor:
            fontcolor = [color.value for color in fontcolor]
        else:
            fontcolor = []

        char_dict: Char = {
            "bbox": bbox,
            "char": text,
            "rotation": rotation,
            "font": {
                "name": fontname,
                "flags": fontflag,
                "color": fontcolor,
                "size": fontsize,
                "weight": fontweight,
            },
            "char_idx": i,
        }
        chars.append(char_dict)

    # TODO: If required, add a deduplication step here through intersection of bboxes

    return chars


def deduplicate_chars(chars: Chars) -> Chars:
    # we first construct words from the chars and then deduplicate them
    words: Spans = []
    word: Optional[Span] = None

    def word_break() -> None:
        words.append(
            {
                "bbox": char["bbox"],
                "text": char["char"],
                "rotation": int(char["rotation"]),
                "font": char["font"],
                "char_start_idx": char["char_idx"],
                "char_end_idx": char["char_idx"],
                "chars": [char],
                "url": "",
                "superscript": False,
                "subscript": False,
            }
        )

    for char in chars:
        if words:
            word = words[-1]

        if not word:
            word_break()
            continue

        # we also break on hyphenation
        if any(word["text"].endswith(x) for x in ["\n", " ", "\x02"]):
            word_break()
            continue

        # we break on any change in font info - optimized comparison
        char_font = char['font']
        word_font = word['font']
        if any(char_font[k] != word_font[k] for k in ['name', 'flags', 'size', 'weight']):
            word_break()
            continue

        if char["rotation"] != word["rotation"]:
            word_break()
            continue

        word["text"] += char["char"]
        word["char_end_idx"] = char["char_idx"]
        word["bbox"] = word["bbox"].merge(char["bbox"])
        word["chars"].append(char)

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

    return [char for word in deduped for char in word["chars"]]

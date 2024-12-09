import math

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import get_fontname
from pdftext.schema import Bbox, Chars


def get_chars(textpage: pdfium.PdfTextPage, page_bbox: list[float], page_rotation: int, quote_loosebox=True, normalize=True) -> Chars:
    chars: Chars = []
    start_idx = 0
    end_idx = 1

    x_start, y_start, x_end, y_end = page_bbox
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    for i in range(textpage.count_chars()):
        fontname, fontflag = get_fontname(textpage, i)
        text = chr(pdfium_c.FPDFText_GetUnicode(textpage, i))
        end_idx = start_idx + len(text)

        rotation = pdfium_c.FPDFText_GetCharAngle(textpage, i)
        loosebox = rotation == 0 and (not text == "'" or quote_loosebox)

        char_box = textpage.get_charbox(i, loose=loosebox)
        cx_start, cy_start, cx_end, cy_end = char_box

        cx_start -= x_start
        cx_end -= x_start
        cy_start -= y_start
        cy_end -= y_start

        ty_start = page_height - cy_start
        ty_end = page_height - cy_end

        bbox = [cx_start, min(ty_start, ty_end), cx_end, max(ty_start, ty_end)]
        bbox = Bbox(bbox).rotate(page_width, page_height, page_rotation)
        if normalize:
            bbox = bbox.normalize(page_width, page_height)

        chars.append({
            "bbox": bbox,
            "char": text,
            "rotation": rotation,
            "font": {
                "name": fontname,
                "flags": fontflag,
                "size": pdfium_c.FPDFText_GetFontSize(textpage, i),
                "weight": pdfium_c.FPDFText_GetFontWeight(textpage, i),
            },
            "char_idx": i,
            "char_start_idx": start_idx,
            "char_end_idx": end_idx
        })
        start_idx = end_idx
    return chars

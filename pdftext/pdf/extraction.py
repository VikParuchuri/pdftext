from pdftext.pdf.utils import get_fontname, page_to_device
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


def get_pdfium_chars(pdf_path):
    pdf = pdfium.PdfDocument(pdf_path)
    blocks = []
    for page_idx in range(len(pdf)):
        page = pdf.get_page(page_idx)
        page_rotation = page.get_rotation()
        text_page = page.get_textpage()

        text_chars = []
        for i in range(text_page.count_chars()):
            char = pdfium_c.FPDFText_GetUnicode(text_page, i)
            char = chr(char)
            fontsize = pdfium_c.FPDFText_GetFontSize(text_page, i)
            fontweight = pdfium_c.FPDFText_GetFontWeight(text_page, i)
            fontname, fontflags = get_fontname(text_page, i)
            rotation = pdfium_c.FPDFText_GetCharAngle(text_page, i)
            coords = text_page.get_charbox(i, loose=True)
            device_coords = page_to_device(page, *coords[:2]) + page_to_device(page, *coords[2:])
            device_coords = (device_coords[0], device_coords[3], device_coords[2], device_coords[1])  # Convert to ltrb
            char_info = {
                "font": {
                    "size": fontsize,
                    "weight": fontweight,
                    "name": fontname,
                    "flags": fontflags
                },
                "rotation": rotation,
                "char": char,
                "origin": coords,
                "bbox": device_coords,
                "page_rotation": page_rotation,
                "page": 0,
                "char_idx": i
            }
            text_chars.append(char_info)
        blocks.append(text_chars)
    return blocks
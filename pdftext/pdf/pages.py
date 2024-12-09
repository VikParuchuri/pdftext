from __future__ import annotations

import math
import statistics
from typing import List

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import LINE_BREAKS, SPACES, TABS, flatten, get_fontname
from pdftext.schema import Bbox, Blocks, Chars, Line, Lines, Pages, Span, Spans
from pdftext.settings import settings


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


def get_spans(chars: Chars) -> Spans:
    spans: Spans = []
    span: Span = None

    def span_break():
        return spans.append({
            "bbox": char["bbox"],
            "text": char["char"],
            "rotation": char["rotation"],
            "font": char["font"],
            "char_start_idx": char["char_start_idx"],
            "char_end_idx": char["char_end_idx"],
            "chars": [char]
        })

    for char in chars:
        if spans:
            span = spans[-1]

        if not span:
            span_break()
            continue

        if any(char['font'][k] != span['font'][k] for k in ['name', 'flags', 'size', 'weight']):
            span_break()
            continue

        if char['rotation'] != span['rotation']:
            span_break()
            continue

        if span['text'].endswith("\x02"):
            span_break()
            continue

        span['text'] += char['char']
        span['char_end_idx'] = char['char_end_idx']
        span['bbox'] = span['bbox'].merge(char['bbox'])
        span['chars'].append(char)

    return spans


def get_lines(spans: Spans) -> Lines:
    lines: Lines = []
    line: Line = None

    def line_break(): return lines.append({"spans": [span], "bbox": span["bbox"], "rotation": span["rotation"]})

    for span in spans:
        if lines:
            line = lines[-1]

        if not line:
            line_break()
            continue

        if any(line["spans"][-1]["text"].endswith(suffix) for suffix in ["\r\n", "\x02"]):
            line["spans"][-1]["text"] = line["spans"][-1]["text"].replace("\x02", "-")
            line_break()
            continue

        if span["rotation"] != line["rotation"]:
            line_break()
            continue

        if span["bbox"].y_start > line["bbox"].y_end:
            line_break()
            continue

        line["spans"].append(span)
        line["bbox"] = line["bbox"].merge(span["bbox"])

    return lines


def get_blocks(lines: Lines) -> Blocks:
    if not lines:
        return []

    x_diffs = []
    y_diffs = []
    for i in range(len(lines) - 1):
        prev_center = lines[i]["bbox"].center
        curr_center = lines[i + 1]["bbox"].center
        x_diffs.append(abs(curr_center[0] - prev_center[0]))
        y_diffs.append(abs(curr_center[1] - prev_center[1]))

    median_x_gap = 0.1
    if x_diffs:
        median_x_gap = statistics.median(x_diffs) or median_x_gap
    median_y_gap = 0.1
    if y_diffs:
        median_y_gap = statistics.median(y_diffs) or median_y_gap

    tolerance_factor = 1.5
    allowed_x_gap = median_x_gap * tolerance_factor
    allowed_y_gap = median_y_gap * tolerance_factor

    def block_merge():
        block["lines"].append(line)
        block["bbox"] = block["bbox"].merge(line["bbox"])

    blocks: Blocks = []
    for line in lines:
        if not blocks:
            # First block
            blocks.append({"lines": [line], "bbox": line["bbox"], "rotation": line["rotation"]})
            continue

        block = blocks[-1]
        last_line = block["lines"][-1]

        last_center = last_line["bbox"].center
        current_center = line["bbox"].center

        x_diff = abs(current_center[0] - last_center[0])
        y_diff = abs(current_center[1] - last_center[1])

        if x_diff <= allowed_x_gap and y_diff <= allowed_y_gap:
            block_merge()
            continue

        line_x_indented_start = last_line["bbox"].x_start > line["bbox"].x_start
        if len(block["lines"]) == 1 and line_x_indented_start and y_diff <= allowed_y_gap:
            block_merge()
            continue

        line_x_indented_end = last_line["bbox"].x_end > line["bbox"].x_end
        if line_x_indented_end and y_diff <= allowed_y_gap:
            block_merge()
            continue

        if y_diff < allowed_y_gap * 0.2 and last_line["bbox"].x_end > line["bbox"].x_start:
            block_merge()
            continue

        if block["bbox"].intersection_pct(line["bbox"]) > 0:
            block_merge()
            continue

        blocks.append({"lines": [line], "bbox": line["bbox"]})

    merged_blocks = []
    for i in range(len(blocks)):
        if not merged_blocks:
            merged_blocks.append(blocks[i])
            continue

        prev_block = merged_blocks[-1]
        curr_block = blocks[i]

        if prev_block["bbox"].intersection_pct(curr_block["bbox"]) > 0:
            merged_blocks[-1] = {
                "lines": prev_block["lines"] + curr_block["lines"],
                "bbox": prev_block["bbox"].merge(curr_block["bbox"])
            }
        else:
            merged_blocks.append(curr_block)

    return merged_blocks


def get_pages(
    pdf: pdfium.PdfDocument,
    page_range: range,
    flatten_pdf: bool = True,
    quote_loosebox=True,
    normalize=True
) -> Pages:
    pages: Pages = []

    for page_idx in page_range:
        page = pdf.get_page(page_idx)
        if flatten_pdf:
            flatten(page)
            page = pdf.get_page(page_idx)

        textpage = page.get_textpage()

        page_bbox: List[float] = page.get_bbox()
        page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
        page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

        page_rotation = 0
        try:
            page_rotation = page.get_rotation()
        except:
            pass

        chars = get_chars(textpage, page_bbox, page_rotation, quote_loosebox, normalize)
        spans = get_spans(chars)
        lines = get_lines(spans)
        blocks = get_blocks(lines)

        pages.append({
            "page": page_idx,
            "bbox": page_bbox,
            "width": page_width,
            "height": page_height,
            "rotation": page_rotation,
            "blocks": blocks
        })
    return pages


if __name__ == "__main__":
    # import cProfile

    pdf_path = '/home/ubuntu/surya-test/pdfs/chinese_progit.pdf'
    pdf = pdfium.PdfDocument(pdf_path)

    # cProfile.run('get_pages(pdf, range(len(pdf)))', filename='pdf_parsing_bbox.prof')

    # for page in get_pages(pdf, [481]):
    #     for block in page["blocks"]:
    #         for line_idx, line in enumerate(block["lines"]):
    #             text = ""
    #             for span_idx, span in enumerate(line["spans"]):
    #                 text += span["text"]
    #             print(text, [span["text"] for span in line["spans"]])

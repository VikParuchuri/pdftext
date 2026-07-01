from __future__ import annotations

import math
import statistics
from typing import List
import unicodedata

import pypdfium2 as pdfium

from pdftext.pdf.chars import PageChars, get_chars, deduplicate_chars
from pdftext.pdf.utils import flatten
from pdftext.schema import Bbox, Blocks, Line, Lines, Pages, Spans


def is_math_symbol(char):
    if len(char) != 1:
        return False

    category = unicodedata.category(char)
    return category == 'Sm'

def _top2(values):
    # Returns (max1, max1_idx, max2) so that max-excluding-index can be answered in O(1)
    max1 = max2 = float("-inf")
    max1_idx = -1
    for idx, v in enumerate(values):
        if v > max1:
            max2 = max1
            max1 = v
            max1_idx = idx
        elif v > max2:
            max2 = v
    return max1, max1_idx, max2


def _bottom2(values):
    min1 = min2 = float("inf")
    min1_idx = -1
    for idx, v in enumerate(values):
        if v < min1:
            min2 = min1
            min1 = v
            min1_idx = idx
        elif v < min2:
            min2 = v
    return min1, min1_idx, min2


def assign_scripts(lines: Lines, height_threshold: float = 0.8, line_distance_threshold: float = 0.1):
    for line in lines:
        spans = line["spans"]
        if len(spans) < 2:
            continue

        line_bbox = line["bbox"].bbox
        line_height = line_bbox[3] - line_bbox[1]
        # Skip vertical lines
        if line_height > line_bbox[2] - line_bbox[0]:
            continue

        # Precompute per-span geometry once; the loop below would otherwise
        # recompute these via Bbox properties O(n^2) times per line
        heights = []
        y_starts = []
        y_ends = []
        v_above = []
        v_below = []
        for s in spans:
            bbox = s["bbox"].bbox
            height = bbox[3] - bbox[1]
            heights.append(height)
            y_starts.append(bbox[1])
            y_ends.append(bbox[3])
            v_above.append(bbox[1] - height * line_distance_threshold)
            v_below.append(bbox[3] + height * line_distance_threshold)

        above_max1, above_max1_idx, above_max2 = _top2(v_above)
        below_min1, below_min1_idx, below_min2 = _bottom2(v_below)
        max_line_height = max(1, line_height)
        last_idx = len(spans) - 1

        for i, span in enumerate(spans):
            is_first = i == 0 or not spans[i - 1]["text"].strip()
            is_last = i == last_idx or not spans[i + 1]["text"].strip()
            span_height = heights[i]
            span_top = y_starts[i]
            span_bottom = y_ends[i]

            line_fullheight = span_height / max_line_height <= height_threshold
            next_fullheight = is_last or span_height / max(1, heights[i + 1]) <= height_threshold
            prev_fullheight = is_first or span_height / max(1, heights[i - 1]) <= height_threshold

            # any(span_top < v_above[j] for j != i) == span_top < max(v_above excluding i)
            above = span_top < (above_max2 if i == above_max1_idx else above_max1)
            prev_above = is_first or span_top < y_starts[i - 1]
            next_above = is_last or span_top < y_starts[i + 1]

            below = span_bottom > (below_min2 if i == below_min1_idx else below_min1)
            prev_below = is_first or span_bottom > y_ends[i - 1]
            next_below = is_last or span_bottom > y_ends[i + 1]

            span_text = span["text"].strip()
            span_text_okay = all([
                (len(span_text) == 1 or span_text.isdigit()), # Ensure that the span text is a single char or a number
                span_text.isalnum() or is_math_symbol(span_text) # Ensure that the span text is an alphanumeric or a math symbol
            ])

            if all([
                (prev_fullheight or next_fullheight),
                (prev_above or next_above),
                above,
                line_fullheight,
                span_text_okay
            ]):
                span["superscript"] = True
            elif all([
                (prev_fullheight or next_fullheight),
                (prev_below or next_below),
                below,
                line_fullheight,
                span_text_okay
            ]):
                span["subscript"] = True


def get_spans(chars: PageChars, superscript_height_threshold: float = 0.8, line_distance_threshold: float = 0.1, need_chars: bool = True) -> Spans:
    n = len(chars)
    if n == 0:
        return []

    text = chars.text
    fonts = chars.fonts
    # Plain lists are much faster than per-element numpy access in the loop,
    # and tolist() converts to exact-value python floats/ints
    x0 = chars.boxes[:, 0].tolist()
    y0 = chars.boxes[:, 1].tolist()
    x1 = chars.boxes[:, 2].tolist()
    y1 = chars.boxes[:, 3].tolist()
    rotations = chars.rotations.tolist()
    font_ids = chars.font_ids.tolist()
    char_indices = chars.char_indices.tolist()
    codes = chars.codes.tolist()

    # First pass: find span boundaries, accumulating the span bbox as floats
    span_bounds = []
    start = 0
    bx0, by0, bx1, by1 = x0[0], y0[0], x1[0], y1[0]
    for j in range(1, n):
        prev_code = codes[j - 1]
        height = by1 - by0
        if (
            # we break on any change in font info (interned per page) or rotation
            font_ids[j] != font_ids[start]
            or rotations[j] != rotations[start]
            # we break on hyphenation or newline
            or prev_code == 2 or prev_code == 10
            # character is likely a superscript: top above the span, bottom not
            # full span height, and to the right of the span
            or (
                y0[j] < by0 - height * line_distance_threshold
                and y1[j] < height * superscript_height_threshold + by0
                and x0[j] > bx1
            )
        ):
            span_bounds.append((start, j, [bx0, by0, bx1, by1]))
            start = j
            bx0, by0, bx1, by1 = x0[j], y0[j], x1[j], y1[j]
        else:
            if x0[j] < bx0:
                bx0 = x0[j]
            if y0[j] < by0:
                by0 = y0[j]
            if x1[j] > bx1:
                bx1 = x1[j]
            if y1[j] > by1:
                by1 = y1[j]
    span_bounds.append((start, n, [bx0, by0, bx1, by1]))

    # Second pass: materialize span dicts (char dicts only when the caller
    # actually consumes them - links, tables, keep_chars output)
    spans: Spans = []
    for start, end, bbox in span_bounds:
        span = {
            "bbox": Bbox(bbox),
            "text": text[start:end],
            "font": fonts[font_ids[start]],
            "rotation": rotations[start],
            "char_start_idx": char_indices[start],
            "char_end_idx": char_indices[end - 1],
            "url": '',
            "superscript": False,
            "subscript": False,
        }
        if need_chars:
            span["chars"] = [
                {
                    "bbox": Bbox([x0[j], y0[j], x1[j], y1[j]]),
                    "char": text[j],
                    "rotation": rotations[j],
                    "font": fonts[font_ids[j]],
                    "char_idx": char_indices[j],
                }
                for j in range(start, end)
            ]
        spans.append(span)

    return spans


def get_lines(spans: Spans) -> Lines:
    lines: Lines = []
    line: Line = None

    def line_break():
        lines.append({"spans": [span], "bbox": span["bbox"].copy(), "rotation": span["rotation"]})

    for span in spans:
        if lines:
            line = lines[-1]

        if not line:
            line_break()
            continue

        # we break if the previous span ends with a linebreak
        last_text = line["spans"][-1]["text"]
        if any(last_text.endswith(suffix) for suffix in ["\n", "\x02"]):
            line_break()
            continue

        # rotations are radians from FPDFText_GetCharAngle; compare circularly.
        # Only break on roughly perpendicular text: pdfium reports a 180-degree
        # flip for ordinary text rendered with negative-scale matrices, which
        # still belongs to the same visual line
        if span["rotation"] != line["rotation"]:
            rotation_diff = abs(span["rotation"] - line["rotation"]) % (2 * math.pi)
            rotation_diff = min(rotation_diff, 2 * math.pi - rotation_diff)
            if math.radians(45) <= rotation_diff <= math.radians(135):
                line_break()
                continue

        # sometimes pdfium doesn't inject a linebreak, so we check the span positions
        if span["bbox"].y_start > line["bbox"].y_end:
            line_break()
            continue

        line["spans"].append(span)
        line["bbox"].merge_inplace(span["bbox"])

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
        block["bbox"].merge_inplace(line["bbox"])

    blocks: Blocks = []
    for line in lines:
        if not blocks:
            # First block
            blocks.append({"lines": [line], "bbox": line["bbox"].copy(), "rotation": line["rotation"]})
            continue

        block = blocks[-1]
        last_line = block["lines"][-1]

        last_center = last_line["bbox"].center
        current_center = line["bbox"].center

        x_diff = abs(current_center[0] - last_center[0])
        y_diff = abs(current_center[1] - last_center[1])

        # we merge if the line is close enough to the previous line
        if x_diff <= allowed_x_gap and y_diff <= allowed_y_gap:
            block_merge()
            continue

        # we make an exception for the first line w.r.t the x diff, because the first line is usually indented
        line_x_indented_start = last_line["bbox"].x_start > line["bbox"].x_start
        if len(block["lines"]) == 1 and line_x_indented_start and y_diff <= allowed_y_gap:
            block_merge()
            continue

        # we make an exception for the last line w.r.t the x diff, because the last line is can be incomplete
        line_x_indented_end = last_line["bbox"].x_end > line["bbox"].x_end
        if line_x_indented_end and y_diff <= allowed_y_gap:
            block_merge()
            continue

        # if the y diff is very small, and you see a line continuation, we merge (can happen with inline math between text spans)
        if y_diff < allowed_y_gap * 0.2 and last_line["bbox"].x_end > line["bbox"].x_start:
            block_merge()
            continue

        # we also merge when we see the current line intersecting the previous block
        if block["bbox"].intersection_pct(line["bbox"]) > 0:
            block_merge()
            continue

        blocks.append({"lines": [line], "bbox": line["bbox"].copy(), "rotation": line["rotation"]})

    # we do one last pass of merging overlapping blocks in the PDF reading order
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
                "bbox": prev_block["bbox"].merge_inplace(curr_block["bbox"]),
                "rotation": prev_block["rotation"]
            }
        else:
            merged_blocks.append(curr_block)

    return merged_blocks


def get_pages(
    pdf: pdfium.PdfDocument,
    page_range: range,
    flatten_pdf: bool = True,
    quote_loosebox: bool =True,
    superscript_height_threshold: float = 0.7,
    line_distance_threshold: float = 0.1,
    need_chars: bool = True,
) -> Pages:
    pages: Pages = []

    for page_idx in page_range:
        page = pdf.get_page(page_idx)
        textpage = None
        try:
            if flatten_pdf:
                flatten(page)
                page.close()
                page = pdf.get_page(page_idx)

            textpage = page.get_textpage()

            page_bbox: List[float] = page.get_bbox()
            page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
            page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

            page_rotation = 0
            try:
                page_rotation = page.get_rotation()
            except pdfium.PdfiumError:
                pass

            chars = deduplicate_chars(get_chars(textpage, page_bbox, page_rotation, quote_loosebox))
            spans = get_spans(chars, superscript_height_threshold=superscript_height_threshold, line_distance_threshold=line_distance_threshold, need_chars=need_chars)
            lines = get_lines(spans)
            assign_scripts(lines, height_threshold=superscript_height_threshold, line_distance_threshold=line_distance_threshold)
            blocks = get_blocks(lines)

            pages.append({
                "page": page_idx,
                "bbox": page_bbox,
                "width": page_width,
                "height": page_height,
                "rotation": page_rotation,
                "blocks": blocks
            })
        finally:
            if textpage is not None:
                textpage.close()
            page.close()
    return pages

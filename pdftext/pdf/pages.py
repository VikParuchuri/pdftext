from __future__ import annotations

import math
import statistics
from typing import Optional, cast
import unicodedata
import io

import pypdfium2 as pdfium

from pdftext.pdf.chars import get_chars, deduplicate_chars
from pdftext.pdf.utils import (
    Bbox,
    flatten,
    transform_bbox,
    remove_wrong_bboxes,
)
from pdftext.schema import (
    Blocks,
    Chars,
    Line,
    Lines,
    Pages,
    Span,
    Spans,
    Block,
    Page,
)
import base64


def is_math_symbol(char: str) -> bool:
    if len(char) != 1:
        return False

    category = unicodedata.category(char)
    return category == "Sm"


def assign_scripts(
    lines: Lines, height_threshold: float = 0.8, line_distance_threshold: float = 0.1
) -> None:
    for line in lines:
        prev_span: Optional[Span] = None
        if len(line["spans"]) < 2:
            continue

        # Skip vertical lines
        if line["bbox"].height > line["bbox"].width:
            continue

        for i, span in enumerate(line["spans"]):
            is_first = i == 0 or not (prev_span and prev_span["text"].strip())
            is_last = (
                i == len(line["spans"]) - 1 or not line["spans"][i + 1]["text"].strip()
            )
            span_height = span["bbox"].height
            span_top = span["bbox"].y_start
            span_bottom = span["bbox"].y_end

            line_fullheight = (
                span_height / max(1, line["bbox"].height) <= height_threshold
            )
            next_fullheight = (
                is_last
                or span_height / max(1, line["spans"][i + 1]["bbox"].height)
                <= height_threshold
            )
            prev_fullheight = (
                is_first
                or not prev_span
                or (span_height / max(1, prev_span["bbox"].height) <= height_threshold)
            )

            above = any(
                [
                    span_top
                    < (s["bbox"].y_start - s["bbox"].height * line_distance_threshold)
                    for j, s in enumerate(line["spans"])
                    if j != i
                ]
            )
            prev_above = (
                is_first or not prev_span or span_top < prev_span["bbox"].y_start
            )
            next_above = is_last or span_top < line["spans"][i + 1]["bbox"].y_start

            below = any(
                [
                    span_bottom
                    > (s["bbox"].y_end + s["bbox"].height * line_distance_threshold)
                    for j, s in enumerate(line["spans"])
                    if j != i
                ]
            )
            prev_below = (
                is_first or not prev_span or span_bottom > prev_span["bbox"].y_end
            )
            next_below = is_last or span_bottom > line["spans"][i + 1]["bbox"].y_end

            span_text = span["text"].strip()
            span_text_okay = all(
                [
                    (
                        len(span_text) == 1 or span_text.isdigit()
                    ),  # Ensure that the span text is a single char or a number
                    span_text.isalnum()
                    or is_math_symbol(
                        span_text
                    ),  # Ensure that the span text is an alphanumeric or a math symbol
                ]
            )

            if all(
                [
                    (prev_fullheight or next_fullheight),
                    (prev_above or next_above),
                    above,
                    line_fullheight,
                    span_text_okay,
                ]
            ):
                span["superscript"] = True
            elif all(
                [
                    (prev_fullheight or next_fullheight),
                    (prev_below or next_below),
                    below,
                    line_fullheight,
                    span_text_okay,
                ]
            ):
                span["subscript"] = True

            prev_span = span


def get_spans(
    chars: Chars,
    image_bboxes: list[Bbox],
    superscript_height_threshold: float = 0.8,
    line_distance_threshold: float = 0.1,
) -> Spans:
    spans: Spans = []
    avg_char_width: Optional[float] = None
    sum_char_widths = 0.0

    def span_break() -> None:
        nonlocal spans, sum_char_widths
        new_span_dict = {
            "bbox": char["bbox"],
            "text": char["char"],
            "rotation": char["rotation"],
            "font": char["font"],
            "char_start_idx": char["char_idx"],
            "char_end_idx": char["char_idx"],
            "chars": [char],
            "url": "",
            "superscript": False,
            "subscript": False,
        }
        spans.append(Span(new_span_dict))
        sum_char_widths = char["bbox"].width

    for char in chars:
        current_span = spans[-1] if spans else None

        if not current_span:
            span_break()
            continue

        if any(
            char["font"][k] != current_span["font"][k]
            for k in ["name", "flags", "size", "weight", "color"]
        ):
            span_break()
            continue

        if char["rotation"] != current_span["rotation"]:
            span_break()
            continue

        if current_span["text"].endswith("\x02") or current_span["text"].endswith("\n"):
            span_break()
            continue

        if all(
            [
                char["bbox"].y_start
                < (
                    current_span["bbox"].y_start
                    - current_span["bbox"].height * line_distance_threshold
                ),
                char["bbox"].y_end
                < (current_span["bbox"].height * superscript_height_threshold)
                + current_span["bbox"].y_start,
                char["bbox"].x_start > current_span["bbox"].x_end,
            ]
        ):
            span_break()
            continue

        if len(current_span["chars"]) > 0:
            prev_char_bbox = current_span["chars"][-1]["bbox"]
            for char_in_current_span in current_span["chars"][::-1]:
                if char_in_current_span["char"].strip():
                    prev_char_bbox = char_in_current_span["bbox"]
                    break
            avg_char_width = sum_char_widths / len(current_span["chars"])
            # Used to be 1.5 * avg_char_width reduced it to avg_char_width
            if char["bbox"].horizontal_distance(prev_char_bbox) > avg_char_width:
                span_break()
                continue

            if char["bbox"].overlap_y(prev_char_bbox) == 0:
                span_break()
                continue

            if char["bbox"].overlap_y(current_span["bbox"]) < 0.1 * min(
                char["bbox"].height, current_span["bbox"].height
            ):
                span_break()
                continue

            for image_bbox in image_bboxes:
                if (
                    image_bbox.intersection_area(current_span["bbox"]) == 0
                    and image_bbox.intersection_area(char["bbox"]) == 0
                    and image_bbox.intersection_area(
                        current_span["bbox"].merge(char["bbox"])
                    )
                    > 0
                ):
                    span_break()
                    continue

        current_span["text"] += char["char"]
        current_span["char_end_idx"] = char["char_idx"]
        current_span["bbox"] = current_span["bbox"].merge(char["bbox"])
        current_span["chars"].append(char)
        sum_char_widths += char["bbox"].width

    filtered_spans = [span for span in spans if span["text"].strip() != ""]
    return filtered_spans


def get_lines(spans: Spans) -> Lines:
    lines: Lines = []
    current_line: Optional[Line] = None

    def line_break() -> None:
        nonlocal lines
        lines.append(
            {"spans": [span], "bbox": span["bbox"], "rotation": span["rotation"]}
        )

    for span in spans:
        current_line = lines[-1] if lines else None

        if not current_line:
            line_break()
            continue

        # we break if the previous span ends with a linebreak
        last_text = current_line["spans"][-1]["text"]
        if any(last_text.endswith(suffix) for suffix in ["\n", "\x02"]):
            line_break()
            continue

        if (
            span["rotation"] != current_line["rotation"]
            and abs(span["rotation"] - current_line["rotation"]) >= 45
        ):
            line_break()
            continue

        if span["bbox"].y_start > current_line["bbox"].y_end:
            line_break()
            continue

        current_line["spans"].append(span)
        current_line["bbox"] = current_line["bbox"].merge(span["bbox"])

    return lines


def get_blocks(lines: Lines) -> Blocks:
    if not lines:
        return []

    x_diffs: list[float] = []
    y_diffs: list[float] = []
    for i in range(len(lines) - 1):
        prev_bbox = lines[i]["bbox"]
        curr_bbox = lines[i + 1]["bbox"]
        prev_center = prev_bbox.center
        curr_center = curr_bbox.center
        x_diffs.append(abs(curr_center[0] - prev_center[0]))
        y_diffs.append(abs(curr_center[1] - prev_center[1]))

    median_x_gap = statistics.median(x_diffs) if x_diffs else 0.1
    median_y_gap = statistics.median(y_diffs) if y_diffs else 0.1

    tolerance_factor = 1.5
    allowed_x_gap = median_x_gap * tolerance_factor
    allowed_y_gap = median_y_gap * tolerance_factor

    def block_merge() -> None:
        nonlocal current_block, line
        block: Block = cast(Block, current_block)
        block["lines"].append(line)
        block["bbox"] = block["bbox"].merge(line["bbox"])

    blocks: Blocks = []
    for line in lines:
        current_block = blocks[-1] if blocks else None

        if not current_block:
            blocks.append(
                {"lines": [line], "bbox": line["bbox"], "rotation": line["rotation"]}
            )
            continue

        last_line = cast(Block, current_block)["lines"][-1]
        last_bbox = last_line["bbox"]
        current_bbox = line["bbox"]

        last_center = last_bbox.center
        current_center = current_bbox.center

        x_diff = abs(current_center[0] - last_center[0])
        y_diff = abs(current_center[1] - last_center[1])

        # we merge if the line is close enough to the previous line
        if x_diff <= allowed_x_gap and y_diff <= allowed_y_gap:
            block_merge()
            continue

        # we make an exception for the first line w.r.t the x diff, because the first line is usually indented
        line_x_indented_start = last_line["bbox"].x_start > line["bbox"].x_start
        if (
            len(cast(Block, current_block)["lines"]) == 1
            and line_x_indented_start
            and y_diff <= allowed_y_gap
        ):
            block_merge()
            continue

        # we make an exception for the last line w.r.t the x diff, because the last line is can be incomplete
        line_x_indented_end = last_line["bbox"].x_end > line["bbox"].x_end
        if line_x_indented_end and y_diff <= allowed_y_gap:
            block_merge()
            continue

        # if the y diff is very small, and you see a line continuation, we merge (can happen with inline math between text spans)
        if (
            y_diff < allowed_y_gap * 0.2
            and last_line["bbox"].x_end > line["bbox"].x_start
        ):
            block_merge()
            continue

        if cast(Block, current_block)["bbox"].intersection_pct(line["bbox"]) > 0:
            block_merge()
            continue

        blocks.append(
            {"lines": [line], "bbox": line["bbox"], "rotation": line["rotation"]}
        )

    merged_blocks: Blocks = []
    if not blocks:
        return []

    merged_blocks.append(blocks[0])
    for i in range(1, len(blocks)):
        prev_block = merged_blocks[-1]
        curr_block = blocks[i]

        if prev_block["bbox"].intersection_pct(curr_block["bbox"]) > 0:
            merged_blocks[-1] = {
                "lines": prev_block["lines"] + curr_block["lines"],
                "bbox": prev_block["bbox"].merge(curr_block["bbox"]),
                "rotation": prev_block["rotation"],
            }
        else:
            merged_blocks.append(curr_block)

    return merged_blocks


def get_image_bboxes(
    page: pdfium.PdfPage, page_bbox_list: list[float], page_rotation: int
) -> list[Bbox]:

    objects = list(page.get_objects())

    text_bboxes: list[Bbox] = []
    non_text_objects = []

    for obj in objects:
        if obj.type in (0, 5):
            continue

        if obj.type in (2, 3, 4):
            non_text_objects.append(obj)
            continue

        text_bboxes.append(transform_bbox(page_bbox_list, page_rotation, obj.get_pos()))

    for obj in objects:
        if obj.type not in (0, 5):
            continue

        obj_bbox = transform_bbox(page_bbox_list, page_rotation, obj.get_pos())
        overlaps_with_text = any(
            text_bbox and obj_bbox.intersection_area(text_bbox) > 0
            for text_bbox in text_bboxes
        )

        if not overlaps_with_text:
            non_text_objects.append(obj)
            continue

    non_text_bboxes: list[Bbox] = [
        transform_bbox(page_bbox_list, page_rotation, obj.get_pos())
        for obj in non_text_objects
    ]

    filtered_non_text_bboxes: list[Optional[Bbox]] = remove_wrong_bboxes(
        non_text_bboxes, page_bbox_list, page
    )
    valid_non_text_bboxes: list[Bbox] = [
        bbox for bbox in filtered_non_text_bboxes if bbox is not None
    ]

    return valid_non_text_bboxes


def get_pages(
    pdf: pdfium.PdfDocument,
    page_range: list[int],
    flatten_pdf: bool = True,
    quote_loosebox: bool = True,
    superscript_height_threshold: float = 0.7,
    line_distance_threshold: float = 0.1,
    page_scale: int = 2,
) -> Pages:
    pages: Pages = []

    for page_idx in page_range:
        page_obj = pdf.get_page(page_idx)
        if flatten_pdf:
            flatten(page_obj)
            page_obj = pdf.get_page(page_idx)

        textpage = page_obj.get_textpage()

        page_bbox_list: list[float] = page_obj.get_bbox()
        page_width = math.ceil(abs(page_bbox_list[2] - page_bbox_list[0]))
        page_height = math.ceil(abs(page_bbox_list[1] - page_bbox_list[3]))

        page_bbox: Bbox = Bbox(bbox=page_bbox_list)

        page_rotation = 0
        try:
            page_rotation = page_obj.get_rotation()
        except Exception:
            pass

        image_bboxes = get_image_bboxes(page_obj, page_bbox_list, page_rotation)

        chars = deduplicate_chars(
            get_chars(textpage, page_bbox_list, page_rotation, quote_loosebox)
        )
        spans = get_spans(
            chars,
            image_bboxes,
            superscript_height_threshold=superscript_height_threshold,
            line_distance_threshold=line_distance_threshold,
        )
        lines = get_lines(spans)
        assign_scripts(
            lines,
            height_threshold=superscript_height_threshold,
            line_distance_threshold=line_distance_threshold,
        )
        blocks = get_blocks(lines)
        img_render = page_obj.render(scale=page_scale)
        pil_image = img_render.to_pil()

        bytes_arr = io.BytesIO()
        img_base64 = ""
        try:
            pil_image.save(bytes_arr, format="PNG")
            bytes_arr.seek(0)
            img_base64 = base64.b64encode(bytes_arr.getvalue()).decode("utf-8")
        except Exception as e:
            print(f"Error processing image for page {page_idx}: {e}")
        finally:
            bytes_arr.close()
            if "pil_image" in locals() and pil_image:
                pil_image.close()

        page_data: Page = {
            "page": page_idx,
            "bbox": page_bbox,
            "width": page_width,
            "height": page_height,
            "rotation": page_rotation,
            "blocks": blocks,
            "scale": page_scale,
            "page_image": img_base64,
            "refs": None,
            "images": image_bboxes,
        }
        pages.append(page_data)

    return pages

from typing import List
import numpy as np

from pdftext.postprocessing import sort_blocks
from pdftext.schema import Page, Bbox, Tables


def get_dynamic_gap_thresh(page: Page, img_size: list, default_thresh=.01, min_chars=100):
    space_dists = []
    for block in page["blocks"]:
        for line in block["lines"]:
            for span in line["spans"]:
                for i in range(1, len(span["chars"])):
                    char1 = span["chars"][i - 1]
                    char2 = span["chars"][i]
                    if page["rotation"] == 90:
                        space_dists.append((char2["bbox"][0] - char1["bbox"][2]) / img_size[0])
                    elif page["rotation"] == 180:
                        space_dists.append((char2["bbox"][1] - char1["bbox"][3]) / img_size[1])
                    elif page["rotation"] == 270:
                        space_dists.append((char1["bbox"][0] - char2["bbox"][2]) / img_size[0])
                    else:
                        space_dists.append((char1["bbox"][1] - char2["bbox"][3]) / img_size[1])
    cell_gap_thresh = np.percentile(space_dists, 80) if len(space_dists) > min_chars else default_thresh
    return cell_gap_thresh


def is_same_span(bbox, curr_box, img_size, space_thresh, rotation):
    def normalized_diff(a, b, dimension, mult=1, use_abs=True):
        func = abs if use_abs else lambda x: x
        return func(a - b) / img_size[dimension] < space_thresh * mult

    if rotation == 90:
        return all([
            normalized_diff(bbox[0], curr_box[0], 0, use_abs=False),
            normalized_diff(bbox[1], curr_box[3], 1),
            normalized_diff(bbox[0], curr_box[0], 0, mult=5)
        ])
    elif rotation == 180:
        return all([
            normalized_diff(bbox[2], curr_box[0], 0, use_abs=False),
            normalized_diff(bbox[1], curr_box[1], 1),
            normalized_diff(bbox[2], curr_box[0], 1, mult=5)
        ])
    elif rotation == 270:
        return all([
            normalized_diff(bbox[0], curr_box[0], 0, use_abs=False),
            normalized_diff(bbox[3], curr_box[1], 1),
            normalized_diff(bbox[0], curr_box[0], 1, mult=5)
        ])
    else:  # 0 or default case
        return all([
            normalized_diff(bbox[0], curr_box[2], 0, use_abs=False),
            normalized_diff(bbox[1], curr_box[1], 1),
            normalized_diff(bbox[0], curr_box[2], 1, mult=5)
        ])


def table_cell_text(tables: List[List[int]], page: Page, img_size: list, table_thresh=.8, space_thresh=.01) -> Tables:
    # Note: table is a list of 4 ints representing the bounding box of the table.  This is against the image dims - this can be different from the page dims.
    # We rescale the characters below to account for this.
    assert all(len(table) == 4 for table in tables), "Tables must be a list of 4 ints representing the bounding box of the table"
    assert len(img_size) == 2, "img_size must be a list of 2 ints representing the image dimensions width, height"

    table_texts = []
    space_thresh = max(space_thresh, get_dynamic_gap_thresh(page, img_size, default_thresh=space_thresh))
    for table in tables:
        table_poly = Bbox(bbox=table)
        table_text = []
        rotation = page["rotation"]

        for block in page["blocks"]:
            for line in block["lines"]:
                line_bbox = Bbox(bbox=line["bbox"]).rescale(img_size, page)
                if line_bbox.intersection_pct(table_poly) < table_thresh:
                    continue
                curr_span = None
                curr_box = None
                for span in line["spans"]:
                    for char in span["chars"]:
                        bbox = Bbox(bbox=char["bbox"]).rescale(img_size, page).bbox
                        same_span = False
                        if curr_span:
                            same_span = is_same_span(bbox, curr_box, img_size, space_thresh, rotation)

                        if curr_span is None:
                            curr_span = char["char"]
                            curr_box = bbox
                        elif same_span:
                            curr_span += char["char"]
                            curr_box = [min(curr_box[0], bbox[0]), min(curr_box[1], bbox[1]),
                                        max(curr_box[2], bbox[2]), max(curr_box[3], bbox[3])]
                        else:
                            if curr_span.strip():
                                table_text.append({"text": curr_span, "bbox": curr_box})
                            curr_span = char["char"]
                            curr_box = bbox
                if curr_span is not None and curr_span.strip():
                    table_text.append({"text": curr_span, "bbox": curr_box})
        # Adjust to be relative to input table
        for item in table_text:
            item["bbox"] = [
                item["bbox"][0] - table[0],
                item["bbox"][1] - table[1],
                item["bbox"][2] - table[0],
                item["bbox"][3] - table[1]
            ]
        table_text = sort_blocks(table_text)
        table_texts.append(table_text)
    return table_texts
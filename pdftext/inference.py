from itertools import chain

import sklearn

from pdftext.pdf.utils import LINE_BREAKS, TABS, SPACES


def update_current(current, new_char):
    bbox = new_char["bbox"]
    if "bbox" not in current:
        current_bbox = bbox.copy()
        current["bbox"] = current_bbox
    else:
        current_bbox = current["bbox"]
        current_bbox[0] = min(bbox[0], current_bbox[0])
        current_bbox[1] = min(bbox[1], current_bbox[1])
        current_bbox[2] = max(bbox[2], current_bbox[2])
        current_bbox[3] = max(bbox[3], current_bbox[3])
    current["center_x"] = (current_bbox[0] + current_bbox[2]) / 2
    current["center_y"] = (current_bbox[1] + current_bbox[3]) / 2


def create_training_row(char_info, prev_char, currblock, currline):
    char = char_info["char"]

    # Store variables used multiple times
    char_x1, char_y1, char_x2, char_y2 = char_info["bbox"]
    prev_x1, prev_y1, prev_x2, prev_y2 = prev_char["bbox"]
    char_center_x = (char_x2 + char_x1) / 2
    char_center_y = (char_y2 + char_y1) / 2
    x_gap = char_x1 - prev_x2
    y_gap = char_y1 - prev_y2

    char_font = char_info["font"]
    prev_font = prev_char["font"]
    font_match = all(
        [char_font[key] == prev_font[key] for key in ["name", "size", "weight", "flags"]] +
        [char_info["rotation"] == prev_char["rotation"]]
    )
    is_space = any([
        char in SPACES,
        char in TABS,
    ])

    training_row = {
        "is_newline": char in LINE_BREAKS,
        "is_space": is_space,
        "x_gap": x_gap,
        "y_gap": y_gap,
        "font_match": font_match,
        "x_outer_gap": char_x2 - prev_x1,
        "y_outer_gap": char_y2 - prev_y1,
        "line_x_center_gap": char_center_x - currline["center_x"],
        "line_y_center_gap": char_center_y - currline["center_y"],
        "line_x_gap": char_x1 - currline["bbox"][2],
        "line_y_gap": char_y1 - currline["bbox"][3],
        "line_x_start_gap": char_x1 - currline["bbox"][0],
        "line_y_start_gap": char_y1 - currline["bbox"][1],
        "block_x_center_gap": char_center_x - currblock["center_x"],
        "block_y_center_gap": char_center_y - currblock["center_y"],
        "block_x_gap": char_x1 - currblock["bbox"][2],
        "block_y_gap": char_y1 - currblock["bbox"][3],
        "block_x_start_gap": char_x1 - currblock["bbox"][0],
        "block_y_start_gap": char_y1 - currblock["bbox"][1]
    }

    return training_row


def update_span(line, span):
    line["spans"].append(span)
    span = {"chars": []}
    return span


def update_line(block, line):
    line["chars"] = list(chain.from_iterable(s["chars"] for s in line["spans"]))
    del line["spans"]
    block["lines"].append(line)
    line = {"spans": []}
    return line


def update_block(blocks, block):
    blocks["blocks"].append(block)
    block = {"lines": []}
    return block


def infer_single_page(text_chars):
    prev_char = None

    blocks = {
        "blocks": [],
        "page": text_chars["page"],
        "rotation": text_chars["rotation"],
        "bbox": text_chars["bbox"],
        "width": text_chars["width"],
        "height": text_chars["height"],
    }
    block = {"lines": []}
    line = {"spans": []}
    span = {"chars": []}
    for i, char_info in enumerate(text_chars["chars"]):
        if prev_char:
            training_row = create_training_row(char_info, prev_char, block, line)
            sorted_keys = sorted(training_row.keys())
            training_row = [training_row[key] for key in sorted_keys]

            prediction = yield training_row
            if prediction == 0:
                pass
            elif prediction == 1:
                span = update_span(line, span)
            elif prediction == 2:
                span = update_span(line, span)
                line = update_line(block, line)
            else:
                span = update_span(line, span)
                line = update_line(block, line)
                block = update_block(blocks, block)

        span["chars"].append(char_info)
        update_current(line, char_info)
        update_current(block, char_info)

        prev_char = char_info
    if len(span["chars"]) > 0:
        update_span(line, span)
    if len(line["spans"]) > 0:
        update_line(block, line)
    if len(block["lines"]) > 0:
        update_block(blocks, block)

    return blocks


def inference(text_chars, model):
    # Create generators and get first training row from each
    generators = [infer_single_page(text_page) for text_page in text_chars]
    next_prediction = {}

    page_blocks = {}
    while len(page_blocks) < len(generators):
        training_data = {}
        for page_idx, page_generator in enumerate(generators):
            if page_idx in page_blocks:
                continue

            try:
                if page_idx not in next_prediction:
                    training_row = next(page_generator)
                else:
                    training_row = page_generator.send(next_prediction[page_idx])
                    del next_prediction[page_idx]
                training_data[page_idx] = training_row
            except StopIteration as e:
                blocks = e.value
                page_blocks[page_idx] = blocks

        if len(page_blocks) == len(generators):
            break

        training_idxs = sorted(training_data.keys())
        training_rows = [training_data[idx] for idx in training_idxs]

        # Disable nan, etc, validation for a small speedup
        with sklearn.config_context(assume_finite=True):
            predictions = model.predict(training_rows)
        for pred, page_idx in zip(predictions, training_idxs):
            next_prediction[page_idx] = pred
    sorted_keys = sorted(page_blocks.keys())
    page_blocks = [page_blocks[key] for key in sorted_keys]
    assert len(page_blocks) == len(text_chars)
    return page_blocks

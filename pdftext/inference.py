from itertools import chain

from pdftext.pdf.utils import LINE_BREAKS, TABS, SPACES


def update_current(current, new_char):
    bbox = new_char["bbox"]
    if "bbox" not in current:
        current_bbox = bbox
        current["bbox"] = current_bbox
    else:
        current_bbox = current["bbox"]
        current_bbox[0] = min(bbox[0], current_bbox[0])
        current_bbox[1] = min(bbox[1], current_bbox[1])
        current_bbox[2] = max(bbox[2], current_bbox[2])
        current_bbox[3] = max(bbox[3], current_bbox[3])
    current["center_x"] = (current_bbox[0] + current_bbox[2]) / 2
    current["center_y"] = (current_bbox[1] + current_bbox[3]) / 2
    return current


def create_training_row(char_info, prev_char, currblock):
    char = char_info["char"]
    char_center_x = (char_info["bbox"][2] + char_info["bbox"][0]) / 2
    char_center_y = (char_info["bbox"][3] + char_info["bbox"][1]) / 2
    x_gap = char_info["bbox"][0] - prev_char["bbox"][2]
    y_gap = char_info["bbox"][1] - prev_char["bbox"][3]
    font_match = all(
        [char_info["font"][key] == prev_char["font"][key] for key in ["name", "size", "weight", "flags"]] +
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
        "x_outer_gap": char_info["bbox"][2] - prev_char["bbox"][0],
        "y_outer_gap": char_info["bbox"][3] - prev_char["bbox"][1],
        "block_x_center_gap": char_center_x - currblock["center_x"],
        "block_y_center_gap": char_center_y - currblock["center_y"],
        "block_x_gap": char_info["bbox"][0] - currblock["bbox"][2],
        "block_y_gap": char_info["bbox"][1] - currblock["bbox"][3]
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

    blocks = {"blocks": []}
    block = {"lines": []}
    line = {"spans": []}
    span = {"chars": []}
    for i, char_info in enumerate(text_chars["chars"]):
        if prev_char:
            training_row = create_training_row(char_info, prev_char, block)
            training_row = [v for _, v in sorted(training_row.items())]

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
        block = update_current(block, char_info)

        prev_char = char_info
    if len(span["chars"]) > 0:
        update_span(line, span)
    if len(line["spans"]) > 0:
        update_line(block, line)
    if len(block["lines"]) > 0:
        update_block(blocks, block)

    blocks["page"] = text_chars["page"]
    blocks["rotation"] = text_chars["rotation"]
    blocks["bbox"] = text_chars["bbox"]
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

        training_list = sorted(training_data.items())
        training_rows = [tl[1] for tl in training_list]
        training_idxs = [tl[0] for tl in training_list]

        predictions = model.predict(training_rows)
        for pred, page_idx in zip(predictions, training_idxs):
            next_prediction[page_idx] = pred
    page_blocks = sorted(page_blocks.items())
    page_blocks = [p[1] for p in page_blocks]
    assert len(page_blocks) == len(text_chars)
    return page_blocks

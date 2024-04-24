import operator
from collections import defaultdict
from itertools import chain

from pdftext.pdf.utils import SPACES, TABS, LINE_BREAKS, HYPHEN
from pdftext.utils import replace_zero


def update_current(current, new_char):
    bbox = new_char["bbox"]
    if "bbox" not in current:
        current["bbox"] = list(bbox)
    else:
        current["bbox"][0] = min(bbox[0], current["bbox"][0])
        current["bbox"][1] = min(bbox[1], current["bbox"][1])
        current["bbox"][2] = max(bbox[2], current["bbox"][2])
        current["bbox"][3] = max(bbox[3], current["bbox"][3])
    current["height"] = current["bbox"][2] - current["bbox"][0]
    current["center_x"] = (current["bbox"][0] + current["bbox"][2]) / 2
    current["center_y"] = (current["bbox"][1] + current["bbox"][3]) / 2
    if "length" not in current:
        current["length"] = 0
    current["length"] += 1
    return current


def create_training_row(char_info, prev_char, currspan, currline, currblock):
    char = char_info["char"]
    char_center_x = (char_info["bbox"][2] + char_info["bbox"][0]) / 2
    char_center_y = (char_info["bbox"][3] + char_info["bbox"][1]) / 2
    prev_char_center_x = (prev_char["bbox"][2] + prev_char["bbox"][0]) / 2
    prev_char_center_y = (prev_char["bbox"][3] + prev_char["bbox"][1]) / 2
    char_height = char_info["bbox"][3] - char_info["bbox"][1]
    char_width = char_info["bbox"][2] - char_info["bbox"][0]
    training_row = {"is_space": char.isspace() or char in SPACES,
                    "is_newline": char in LINE_BREAKS, "is_printable": char.isprintable(), "is_hyphen": char == HYPHEN,
                    "char_x1": char_info["bbox"][0], "char_y1": char_info["bbox"][1],
                    "char_x2": char_info["bbox"][2], "char_y2": char_info["bbox"][3],
                    "prev_char_x1": prev_char["bbox"][0], "prev_char_y1": prev_char["bbox"][1],
                    "prev_char_x2": prev_char["bbox"][2], "prev_char_y2": prev_char["bbox"][3],
                    "x_gap": char_info["bbox"][0] - prev_char["bbox"][2],
                    "y_gap": char_info["bbox"][1] - prev_char["bbox"][3],
                    "x_center_gap": char_center_x - prev_char_center_x,
                    "y_center_gap": char_center_y - prev_char_center_y,
                    "span_len": len(currspan),
                    "line_len": len(currline), "block_len": len(currblock), "height": char_height,
                    "width": char_width,
                    "width_ratio": char_width / replace_zero(prev_char["bbox"][2] - prev_char["bbox"][0]),
                    "height_ratio": char_width / replace_zero(prev_char["bbox"][3] - prev_char["bbox"][1]),
                    "block_x_center_gap": char_center_x - currblock["center_x"],
                    "block_y_center_gap": char_center_y - currblock["center_y"],
                    "line_x_center_gap": char_center_x - currline["center_x"],
                    "line_y_center_gap": char_center_y - currblock["center_y"],
                    "span_x_center_gap": char_center_x - currspan["center_x"],
                    "span_y_center_gap": char_center_y - currspan["center_y"],
                    "block_x_gap": char_info["bbox"][0] - currblock["bbox"][2],
                    "block_y_gap": char_info["bbox"][1] - currblock["bbox"][3]}
    return training_row


def infer_single_page(text_chars):
    prev_char = None

    blocks = defaultdict(list)
    block = defaultdict(list)
    line = defaultdict(list)
    span = defaultdict(list)
    for i, char_info in enumerate(text_chars["chars"]):
        if prev_char:
            training_row = create_training_row(char_info, prev_char, span, line, block)
            training_row = [v for k, v in sorted(training_row.items(), key=operator.itemgetter(0))]

            prediction = yield training_row
            if prediction == 0:
                pass
            elif prediction == 1:
                line["spans"].append(span)
                span = defaultdict(list)
            elif prediction == 2:
                line["spans"].append(span)
                line["chars"] = list(chain.from_iterable([s["chars"] for s in line["spans"]]))
                del line["spans"]
                block["lines"].append(line)
                line = defaultdict(list)
                span = defaultdict(list)
            else:
                line["spans"].append(span)
                line["chars"] = list(chain.from_iterable([s["chars"] for s in line["spans"]]))
                del line["spans"]
                block["lines"].append(line)
                blocks["blocks"].append(block)
                block = defaultdict(list)
                line = defaultdict(list)
                span = defaultdict(list)

        span["chars"].append(char_info)
        span = update_current(span, char_info)
        line = update_current(line, char_info)
        block = update_current(block, char_info)

        prev_char = char_info
    if len(span["chars"]) > 0:
        line["chars"] = list(chain.from_iterable([s["chars"] for s in line["spans"]]))
        del line["spans"]
    if len(line["chars"]) > 0:
        block["lines"].append(line)
    if len(block["lines"]) > 0:
        blocks["blocks"].append(block)

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

        training_list = sorted(training_data.items(), key=operator.itemgetter(0))
        training_rows = [tl[1] for tl in training_list]
        training_idxs = [tl[0] for tl in training_list]

        predictions = model.predict(training_rows)
        for pred, page_idx in zip(predictions, training_idxs):
            next_prediction[page_idx] = pred
    page_blocks = sorted(page_blocks.items(), key=operator.itemgetter(0))
    page_blocks = [p[1] for p in page_blocks]
    assert len(page_blocks) == len(text_chars)
    return page_blocks

from typing import List, Dict
import unicodedata

from pdftext.pdf.utils import SPACES, LINE_BREAKS, TABS, WHITESPACE_CHARS


def postprocess(text: str) -> str:
    text = replace_special_chars(text)
    text = replace_control_chars(text)
    return text


def replace_special_chars(text: str) -> str:
    for item in SPACES:
        text = text.replace(item, " ")
    for item in LINE_BREAKS:
        text = text.replace(item, "\n")
    for item in TABS:
        text = text.replace(item, "\t")
    return text


def replace_control_chars(text: str) -> str:
    return "".join(char for char in text if unicodedata.category(char)[0] != "C" or char in WHITESPACE_CHARS)


def sort_blocks(blocks: List, tolerance=1.25) -> List:
    # Sort blocks into best guess reading order
    vertical_groups = {}
    for block in blocks:
        bbox = block["bbox"]
        group_key = round(bbox[1] / tolerance) * tolerance
        if group_key not in vertical_groups:
            vertical_groups[group_key] = []
        vertical_groups[group_key].append(block)

    # Sort each group horizontally and flatten the groups into a single list
    sorted_page_blocks = []
    for _, group in sorted(vertical_groups.items()):
        sorted_group = sorted(group, key=lambda x: x["bbox"][0])
        sorted_page_blocks.extend(sorted_group)

    return sorted_page_blocks


def merge_text(page: Dict, sort=False) -> str:
    text = ""
    if sort:
        page["blocks"] = sort_blocks(page["blocks"])

    for block in page["blocks"]:
        block_text = ""
        for line in block["lines"]:
            line_text = ""
            for char in line["chars"]:
                line_text += char["char"]
            line_text = postprocess(line_text)
            if line_text.endswith("\n"):
                line_text = line_text[:-1].strip() + " "

            block_text += line_text
        if not block_text.endswith("\n"):
            block_text += "\n\n"
        text += block_text
    return text

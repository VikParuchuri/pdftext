from typing import List, Dict
import unicodedata

from pdftext.pdf.utils import SPACES, LINE_BREAKS, TABS, WHITESPACE_CHARS

LIGATURES = {
    "ﬀ": "ff",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬆ": "st",
    "ﬅ": "st",
}
HYPHEN_CHAR = "\x02"
REPLACEMENTS = {
    "\r\n": "\n",
}


def postprocess_text(text: str) -> str:
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    text = replace_special_chars(text)
    text = replace_control_chars(text)
    text = replace_ligatures(text)
    return text


def handle_hyphens(text: str, keep_hyphens=False) -> str:
    if keep_hyphens:
        text = text.replace(HYPHEN_CHAR, "-\n")
    elif len(text) == 0:
        pass
    else:
        new_text = ""
        found_hyphen = False
        for i in range(len(text) - 1):
            if text[i] == HYPHEN_CHAR:
                found_hyphen = True
            elif found_hyphen:
                if text[i] in LINE_BREAKS:
                    pass
                elif text[i] in SPACES:
                    new_text = new_text.rstrip() + "\n"
                    found_hyphen = False
                else:
                    new_text += text[i]
            else:
                new_text += text[i]
        text = new_text
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
    return "".join(char for char in text if (unicodedata.category(char)[0] != "C" or char == HYPHEN_CHAR or char in WHITESPACE_CHARS))


def replace_ligatures(text: str) -> str:
    for ligature, replacement in LIGATURES.items():
        text = text.replace(ligature, replacement)
    return text


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


def merge_text(page: Dict, sort=False, hyphens=False) -> str:
    text = ""
    if sort:
        page["blocks"] = sort_blocks(page["blocks"])

    for block in page["blocks"]:
        block_text = ""
        for line in block["lines"]:
            line_text = ""
            for span in line["spans"]:
                line_text += span["text"]
            line_text = postprocess_text(line_text)
            line_text = line_text.rstrip() + "\n"

            block_text += line_text
        block_text = block_text.rstrip() + "\n\n"
        text += block_text
    text = handle_hyphens(text, keep_hyphens=hyphens)
    return text

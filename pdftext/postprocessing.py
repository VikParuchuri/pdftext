import unicodedata
from typing import List, Dict

from pdftext.pdf.utils import LINE_BREAKS, SPACES, TABS, WHITESPACE_CHARS
from pdftext.schema import Page, Block

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
    text = fix_unicode_surrogate_pairs(text)
    text = replace_control_chars(text)
    text = replace_ligatures(text)
    return text


def handle_hyphens(text: str, keep_hyphens: bool = False) -> str:
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
    return "".join(
        char
        for char in text
        if (
            unicodedata.category(char)[0] != "C"
            or char == HYPHEN_CHAR
            or char in WHITESPACE_CHARS
        )
    )


def replace_ligatures(text: str) -> str:
    for ligature, replacement in LIGATURES.items():
        text = text.replace(ligature, replacement)
    return text


def sort_blocks(blocks: List[Block], tolerance: float = 1.25) -> List[Block]:
    # Sort blocks into best guess reading order
    vertical_groups: Dict[float, List[Block]] = {}
    for block in blocks:
        group_key = round(block["bbox"][1] / tolerance) * tolerance
        if group_key not in vertical_groups:
            vertical_groups[group_key] = []
        vertical_groups[group_key].append(block)

    # Sort each group horizontally and flatten the groups into a single list
    sorted_page_blocks = []
    for _, group in sorted(vertical_groups.items()):
        # Handle both Bbox object and raw list cases for x coordinate
        sorted_group = sorted(group, key=lambda x: x["bbox"][0])
        sorted_page_blocks.extend(sorted_group)

    return sorted_page_blocks


def merge_text(page: Page, sort: bool = False, hyphens: bool = False) -> str:
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


def fix_unicode_surrogate_pairs(text: str) -> str:
    """
    Fix Unicode surrogate pairs while preserving mathematical symbols.

    Surrogate pairs are UTF-16 artifacts that shouldn't appear in UTF-8.
    This function converts them to proper Unicode characters.
    """
    if not text:
        return ""

    try:
        # Test if the text is already valid UTF-8
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        # Handle surrogate pairs by converting them to proper Unicode
        result = []
        i = 0
        while i < len(text):
            char = text[i]
            code = ord(char)

            # High surrogate followed by low surrogate = valid pair
            if (
                0xD800 <= code <= 0xDBFF
                and i + 1 < len(text)
                and 0xDC00 <= ord(text[i + 1]) <= 0xDFFF
            ):

                high = code - 0xD800
                low = ord(text[i + 1]) - 0xDC00
                unicode_point = 0x10000 + (high << 10) + low

                try:
                    result.append(chr(unicode_point))
                    i += 2
                    continue
                except ValueError:
                    pass

            # Replace lone surrogates with replacement character
            if 0xD800 <= code <= 0xDFFF:
                result.append("\ufffd")
            else:
                result.append(char)
            i += 1

        return "".join(result)

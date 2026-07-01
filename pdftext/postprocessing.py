import unicodedata
from typing import List

from pdftext.pdf.utils import LINE_BREAKS, SPACES, TABS, WHITESPACE_CHARS
from pdftext.schema import Page

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

# Single translation table folding special chars and ligatures into one pass.
# \r\n must be replaced before applying this (a pure table would yield \n\n).
_TRANSLATION_TABLE = str.maketrans({
    **{c: " " for c in SPACES},
    **{c: "\n" for c in LINE_BREAKS},
    **{c: "\t" for c in TABS},
    **LIGATURES,
})


def _keep_char(char: str) -> bool:
    return unicodedata.category(char)[0] != "C" or char == HYPHEN_CHAR or char in WHITESPACE_CHARS

# Control chars are deleted; precompute the ASCII deletions for the fast path
_ASCII_CONTROL_DELETE = {ord(c): None for c in map(chr, range(128)) if not _keep_char(c)}
_KEEP_CHAR_CACHE = {}


def postprocess_text(text: str) -> str:
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    text = text.translate(_TRANSLATION_TABLE)
    text = replace_control_chars(text)
    return text


def handle_hyphens(text: str, keep_hyphens=False) -> str:
    if keep_hyphens:
        text = text.replace(HYPHEN_CHAR, "-\n")
    elif len(text) == 0:
        pass
    else:
        new_text = ""
        found_hyphen = False
        for i in range(len(text)):
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
    if text.isascii():
        return text.translate(_ASCII_CONTROL_DELETE)
    cache = _KEEP_CHAR_CACHE
    out = []
    for char in text:
        keep = cache.get(char)
        if keep is None:
            keep = _keep_char(char)
            cache[char] = keep
        if keep:
            out.append(char)
    return "".join(out)


def replace_ligatures(text: str) -> str:
    for ligature, replacement in LIGATURES.items():
        text = text.replace(ligature, replacement)
    return text


def sort_blocks(blocks: List, tolerance=1.25) -> List:
    # Sort blocks into best guess reading order
    vertical_groups = {}
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


def merge_text(page: Page, sort=False, hyphens=False) -> str:
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

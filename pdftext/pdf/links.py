import ctypes
import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from pdftext.pdf.utils import matrix_intersection_area
from pdftext.schema import Bbox, Link, Page, Pages


def _get_dest_position(dest) -> Optional[Tuple[float, float]]:
    has_x = ctypes.c_int()
    has_y = ctypes.c_int()
    has_zoom = ctypes.c_int()
    x_coord = ctypes.c_float()
    y_coord = ctypes.c_float()
    zoom_level = ctypes.c_float()
    success = pdfium_c.FPDFDest_GetLocationInPage(
        dest,
        ctypes.byref(has_x),
        ctypes.byref(has_y),
        ctypes.byref(has_zoom),
        ctypes.byref(x_coord),
        ctypes.byref(y_coord),
        ctypes.byref(zoom_level)
    )
    if success:
        if has_x.value and has_y.value:
            return x_coord.value, y_coord.value
    return None


def _rect_to_scaled_bbox(rect, page_bbox, page_rotation) -> List[float]:
    page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
    page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

    cx_start, cy_start, cx_end, cy_end = rect
    cx_start -= page_bbox[0]
    cx_end -= page_bbox[0]
    cy_start -= page_bbox[1]
    cy_end -= page_bbox[1]

    ty_start = page_height - cy_start
    ty_end = page_height - cy_end

    bbox = [min(cx_start, cx_end), min(ty_start, ty_end), max(cx_start, cx_end), max(ty_start, ty_end)]
    return Bbox(bbox).rotate(page_width, page_height, page_rotation).bbox


def _xy_to_scaled_pos(x, y, page_bbox, page_rotation, expand_by=1) -> List[float]:
    return _rect_to_scaled_bbox([x - expand_by, y - expand_by, x + expand_by, y + expand_by], page_bbox, page_rotation)[:2]


def get_links(page_idx: int, pdf: pdfium.PdfDocument) -> List[Link]:
    urls = []

    page = pdf.get_page(page_idx)
    page_bbox: List[float] = page.get_bbox()
    page_rotation = 0
    try:
        page_rotation = page.get_rotation()
    except:
        pass

    annot_count = pdfium_c.FPDFPage_GetAnnotCount(page)
    for i in range(annot_count):
        link: Link = {
            'page': page_idx,
            'bbox': None,
            'dest_page': None,
            'dest_pos': None,
            'url': None,
        }
        annot = pdfium_c.FPDFPage_GetAnnot(page, i)
        if pdfium_c.FPDFAnnot_GetSubtype(annot) != pdfium_c.FPDF_ANNOT_LINK:
            continue

        fs_rect = pdfium_c.FS_RECTF()
        success = pdfium_c.FPDFAnnot_GetRect(annot, ctypes.byref(fs_rect))
        if not success:
            continue

        link['bbox'] = _rect_to_scaled_bbox(
            [fs_rect.left, fs_rect.top, fs_rect.right, fs_rect.bottom],
            page_bbox, page_rotation
        )

        link_obj = pdfium_c.FPDFAnnot_GetLink(annot)

        dest = pdfium_c.FPDFLink_GetDest(pdf, link_obj)
        if dest:
            tgt_page = pdfium_c.FPDFDest_GetDestPageIndex(pdf, dest)
            link['dest_page'] = tgt_page
            dest_position = _get_dest_position(dest)
            if dest_position:
                link['dest_pos'] = _xy_to_scaled_pos(*dest_position, page_bbox, page_rotation)

        else:
            action = pdfium_c.FPDFLink_GetAction(link_obj)
            a_type = pdfium_c.FPDFAction_GetType(action)

            if a_type == pdfium_c.PDFACTION_UNSUPPORTED:
                continue

            elif a_type == pdfium_c.PDFACTION_GOTO:
                # Goto a page
                dest = pdfium_c.FPDFAction_GetDest(pdf, action)
                if dest:
                    tgt_page = pdfium_c.FPDFDest_GetDestPageIndex(pdf, dest)
                    link['dest_page'] = tgt_page
                    dest_position = _get_dest_position(dest)
                    if dest_position:
                        link['dest_pos'] = _xy_to_scaled_pos(*dest_position, page_bbox, page_rotation)

            elif a_type == pdfium_c.PDFACTION_URI:
                # External link
                needed_len = pdfium_c.FPDFAction_GetURIPath(pdf, action, None, 0)
                if needed_len > 0:
                    buf = ctypes.create_string_buffer(needed_len)
                    pdfium_c.FPDFAction_GetURIPath(pdf, action, buf, needed_len)
                    uri = buf.raw[:needed_len].decode('utf-8', errors='replace').rstrip('\x00')
                    link["url"] = uri

        urls.append(link)
    return urls


def merge_links(page: Page, pdf: pdfium.PdfDocument, refs: dict):
    """
    Merges links with spans. Some spans can also have multiple links associated with them.
    We break up the spans and reconstruct them taking the links into account.
    """
    page_id = page["page"]

    links = get_links(page_id, pdf)

    spans = [span for block in page['blocks'] for line in block['lines'] for span in line['spans']]
    span_bboxes = [span['bbox'].bbox for span in spans]
    link_bboxes = [link['bbox'] for link in links]

    intersection_matrix = matrix_intersection_area(link_bboxes, span_bboxes)

    span_link_map: Dict[int, List[Link]] = {}
    for link_idx, link in enumerate(links):
        intersection_link = intersection_matrix[link_idx]
        if intersection_link.sum() == 0:
            continue

        max_intersection = intersection_link.argmax()
        span = spans[max_intersection]

        if link['dest_page'] is None:
            continue

        dest_page = link['dest_page']
        refs.setdefault(dest_page, [])

        if link['dest_pos']:
            dest_pos = link['dest_pos']
        else:
            # Don't link to self if there is no dest_pos
            if dest_page == page_id:
                continue
            # if we don't have a dest pos, we just link to the top of the page
            dest_pos = [0.0, 0.0]

        if dest_pos not in refs[dest_page]:
            refs[dest_page].append(dest_pos)

        link['url'] = f"#page-{dest_page}-{refs[dest_page].index(dest_pos)}"

        span_link_map.setdefault(max_intersection, [])
        span_link_map[max_intersection].append(link)

    span_idx = 0
    for block in page["blocks"]:
        for line in block["lines"]:
            spans = []
            for span in line["spans"]:
                if span_idx in span_link_map:
                    spans.extend(_reconstruct_spans(span, span_link_map[span_idx]))
                else:
                    spans.append(span)
                span_idx += 1
            line['spans'] = spans


def merge_refs(page, refs):
    """
    We associate each reference to the nearest span.
    """

    page_id = page["page"]

    page_refs = refs.get(page_id, [])
    if not page_refs:
        return

    spans = [span for block in page['blocks'] for line in block['lines'] for span in line['spans']]
    if not spans:
        return

    span_starts = np.array([span['bbox'][:2] for span in spans])
    ref_starts = np.array(page_refs)

    distances = np.linalg.norm(span_starts[:, np.newaxis, :] - ref_starts[np.newaxis, :, :], axis=2)

    for ref_idx in range(len(ref_starts)):
        span_idx = np.argmin(distances[:, ref_idx])
        spans[span_idx].setdefault('anchors', [])
        spans[span_idx]['anchors'].append(f"page-{page_id}-{ref_idx}")


def _reconstruct_spans(orig_span: dict, links: List[Link]):
    """
    Reconstructs the spans by breaking them up into smaller spans based on the links.
    """
    spans = []
    span = None
    link_bboxes = [Bbox(link['bbox']) for link in links]

    for char in orig_span['chars']:
        char_bbox = Bbox(char['bbox'])
        intersections: List[Tuple[float, Link]] = []
        for i, link_bbox in enumerate(link_bboxes):
            area = link_bbox.intersection_area(char_bbox)
            if area > 0:
                intersections.append((area, links[i]))

        current_url = ''
        if intersections:
            intersections.sort(key=lambda x: x[0], reverse=True)
            current_url = intersections[0][1]['url']

        if not span or current_url != span['url']:
            span = {
                "bbox": char_bbox,
                "text": char["char"],
                "rotation": char["rotation"],
                "font": char["font"],
                "char_start_idx": char["char_idx"],
                "char_end_idx": char["char_idx"],
                "chars": [char],
                "url": current_url
            }
            spans.append(span)
        else:
            span['text'] += char['char']
            span['char_end_idx'] = char['char_idx']
            span['bbox'] = span['bbox'].merge(char_bbox)
            span['chars'].append(char)

    return spans


def add_links_and_refs(pages: Pages, pdf_doc: pdfium.PdfDocument):
    refs: Dict[int, List[List[float]]] = {}

    for page in pages:
        merge_links(page, pdf_doc, refs)
    for page in pages:
        merge_refs(page, refs)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict, Union


class Bbox:
    def __init__(self, bbox: List[float], ensure_nonzero_area: bool = False) -> None:
        if ensure_nonzero_area:
            bbox = list(bbox)
            bbox[2] = max(bbox[0], bbox[2] + 1)
            bbox[3] = max(bbox[1], bbox[3] + 1)
        self.bbox = bbox
        self.ensure_nonzero_area = ensure_nonzero_area

    def __getitem__(self, item: int) -> float:
        return self.bbox[item]

    def __repr__(self) -> str:
        return f"Bbox({self.bbox})"

    @property
    def height(self) -> float:
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self) -> float:
        return self.bbox[2] - self.bbox[0]

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> List[float]:
        return [(self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2]

    @property
    def size(self) -> List[float]:
        return [self.width, self.height]

    @property
    def x_start(self) -> float:
        return self.bbox[0]

    @property
    def y_start(self) -> float:
        return self.bbox[1]

    @property
    def x_end(self) -> float:
        return self.bbox[2]

    @property
    def y_end(self) -> float:
        return self.bbox[3]

    def inside(self, other: Bbox) -> bool:
        # Check if the self bounding box is entirely contained within the other bounding box.
        return (
            self.x_start >= other.x_start
            and self.x_end <= other.x_end
            and self.y_start >= other.y_start
            and self.y_end <= other.y_end
        )

    def merge(self, other: Bbox) -> Bbox:
        self_bbox = self.bbox
        other_bbox = other.bbox
        return Bbox([
            min(self_bbox[0], other_bbox[0]),
            min(self_bbox[1], other_bbox[1]),
            max(self_bbox[2], other_bbox[2]),
            max(self_bbox[3], other_bbox[3])
        ])

    def overlap_x(self, other: Bbox) -> float:
        return max(
            0, min(self.bbox[2], other.bbox[2]) - max(self.bbox[0], other.bbox[0])
        )

    def overlap_y(self, other: Bbox) -> float:
        return max(
            0, min(self.bbox[3], other.bbox[3]) - max(self.bbox[1], other.bbox[1])
        )

    def horizontal_distance(self, other: Bbox) -> float:
        x1, y1, x2, y2 = self.bbox
        i1, j1, i2, j2 = other.bbox

        if x1 < i1:
            return i1 - x1
        elif i2 < x1:
            return x1 - i2

        return 0

    def intersection_score(self, other: Bbox) -> float:
        intersection_area = self.intersection_area(other)
        if self.area == 0 or other.area == 0:
            if self.inside(other) or other.inside(self):
                return 1.0
            else:
                return 0.0
        else:
            return intersection_area / min(self.area, other.area)

    def intersection_area(self, other: Bbox) -> float:
        return self.overlap_x(other) * self.overlap_y(other)

    def intersection_pct(self, other: Bbox) -> float:
        if self.area == 0:
            return 0.0

        intersection = self.intersection_area(other)
        return intersection / self.area

    def rotate(self, page_width: float, page_height: float, rotation: int) -> Bbox:
        if rotation not in [0, 90, 180, 270]:
            raise ValueError("Rotation must be one of [0, 90, 180, 270] degrees.")

        x_min, y_min, x_max, y_max = self.bbox

        if rotation == 0:
            return Bbox(self.bbox)
        elif rotation == 90:
            new_x_min = page_height - y_max
            new_y_min = x_min
            new_x_max = page_height - y_min
            new_y_max = x_max
        elif rotation == 180:
            new_x_min = page_width - x_max
            new_y_min = page_height - y_max
            new_x_max = page_width - x_min
            new_y_max = page_height - y_min
        elif rotation == 270:
            new_x_min = y_min
            new_y_min = page_width - x_max
            new_x_max = y_max
            new_y_max = page_width - x_min

        # Ensure that x_min < x_max and y_min < y_max
        rotated_bbox = [
            min(new_x_min, new_x_max),
            min(new_y_min, new_y_max),
            max(new_x_min, new_x_max),
            max(new_y_min, new_y_max),
        ]

        return Bbox(rotated_bbox)

    def rescale(self, img_size: List[int], page: Page) -> Bbox:
        w_scale = img_size[0] / page["width"]
        h_scale = img_size[1] / page["height"]
        new_bbox = [
            self.bbox[0] * w_scale,
            self.bbox[1] * h_scale,
            self.bbox[2] * w_scale,
            self.bbox[3] * h_scale,
        ]

        return Bbox(new_bbox)


class Char(TypedDict):
    bbox: Bbox
    char: str
    rotation: float
    font: Dict[str, Union[Any, str]]
    char_idx: int


class Span(TypedDict):
    bbox: Bbox
    text: str
    font: Dict[str, Union[Any, str]]
    chars: List[Char]
    char_start_idx: int
    char_end_idx: int
    rotation: int
    url: str
    superscript: bool
    subscript: bool


class Line(TypedDict):
    spans: List[Span]
    bbox: Bbox
    rotation: int


class Block(TypedDict):
    lines: List[Line]
    bbox: Bbox
    rotation: int


class Page(TypedDict):
    page: int
    bbox: Bbox
    width: int
    height: int
    blocks: List[Block]
    rotation: int
    refs: Optional[List[Reference]]
    scale: int
    page_image: str
    images: List[Bbox]


class TableCell(TypedDict):
    text: str
    bbox: Bbox


class TableInput(TypedDict):
    tables: List[List[int]]
    img_size: List[int]


class Link(TypedDict):
    page: int
    bbox: List[float]
    dest_page: Optional[int]
    dest_pos: Optional[List[float]]
    url: Optional[str]


@dataclass
class Reference:
    idx: int
    page: int
    coord: List[float]

    @property
    def ref(self) -> str:
        return f"page-{self.page}-{self.idx}"

    @property
    def url(self) -> str:
        return f"#{self.ref}"


class PageReference:
    def __init__(self) -> None:
        self.page_ref_map: Dict[int, List[Reference]] = {}

    def get_refs(self, page: int) -> List[Reference]:
        return self.page_ref_map.get(page, [])

    def add_ref(self, page: int, coord: List[float]) -> Reference:
        self.page_ref_map.setdefault(page, [])
        ref = self.check_ref(page, coord)
        if ref is None:
            ref = Reference(idx=len(self.page_ref_map[page]), page=page, coord=coord)
            self.page_ref_map[page].append(ref)
        return ref

    def check_ref(self, page: int, coord: List[float]) -> Optional[Reference]:
        refs = self.page_ref_map.get(page, [])
        for ref in refs:
            if ref.coord == coord:
                return ref
        return None


Chars = List[Char]
Spans = List[Span]
Lines = List[Line]
Blocks = List[Block]
Pages = List[Page]
Tables = List[List[TableCell]]
TableInputs = List[TableInput]

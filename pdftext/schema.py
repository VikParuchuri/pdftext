from __future__ import annotations

from typing import Any, Dict, List, TypedDict, Union


class Bbox:
    def __init__(self, bbox: List[float]):
        self.bbox = bbox

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def area(self):
        return self.width * self.height

    @property
    def center(self):
        return [(self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2]

    @property
    def size(self):
        return [self.width, self.height]

    @property
    def x_start(self):
        return self.bbox[0]

    @property
    def y_start(self):
        return self.bbox[1]

    @property
    def x_end(self):
        return self.bbox[2]

    @property
    def y_end(self):
        return self.bbox[3]

    def merge(self, other: Bbox) -> Bbox:
        x_start = self.x_start if self.x_start < other.x_start else other.x_start
        y_start = self.y_start if self.y_start < other.y_start else other.y_start
        x_end = self.x_end if self.x_end > other.x_end else other.x_end
        y_end = self.y_end if self.y_end > other.y_end else other.y_end

        return Bbox([x_start, y_start, x_end, y_end])

    def overlap_x(self, other: Bbox):
        return max(0, min(self.bbox[2], other.bbox[2]) - max(self.bbox[0], other.bbox[0]))

    def overlap_y(self, other: Bbox):
        return max(0, min(self.bbox[3], other.bbox[3]) - max(self.bbox[1], other.bbox[1]))

    def intersection_area(self, other: Bbox):
        return self.overlap_x(other) * self.overlap_y(other)

    def intersection_pct(self, other: Bbox):
        if self.area == 0:
            return 0

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
        rotated_bbox = (
            min(new_x_min, new_x_max),
            min(new_y_min, new_y_max),
            max(new_x_min, new_x_max),
            max(new_y_min, new_y_max)
        )

        return Bbox(rotated_bbox)


class Char(TypedDict):
    bbox: Bbox
    text: str
    rotation: float
    font: Dict[str, Union[Any, str]]
    char_idx: int


class Span(TypedDict):
    bbox: Bbox
    text: str
    font: Dict[str, Union[Any, str]]
    font_weight: float
    font_size: float
    chars: List[Char]
    char_start_idx: int
    char_end_idx: int


class Line(TypedDict):
    spans: List[Span]
    bbox: Bbox


class Block(TypedDict):
    lines: List[Line]
    bbox: Bbox


class Page(TypedDict):
    page: int
    bbox: Bbox
    width: int
    height: int
    blocks: List[Block]


Chars = List[Char]
Spans = List[Span]
Lines = List[Line]
Blocks = List[Block]
Pages = List[Page]

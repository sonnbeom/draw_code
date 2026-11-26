"""4-1 ④: 상위(모부품 박스·상위 표)의 칸별 선 모으기 (Claude 작성).

상위 박스는 연결선이 출발하는 세로변(box_side)으로 찾는다.
  - 행 경계: select_bom.box_row_ys (3단계와 같은 행 번호 → ParentLink.box_row와 바로 짝지어짐)
  - 왼쪽 끝: 세로변에 닿는 박스 가로선의 왼쪽 끝 중 가장 왼쪽
  - 열 경계: 박스 안 세로선 (상위 표 88500은 I/NO | PART NO | PART NAME | NOTE, 박스는 보통 1열)
"""

from bisect import bisect_right
from dataclasses import dataclass

from bom.pdf_lines.extract_lines import Line
from bom.pdf_lines.geometry import TOUCH_TOL, is_horizontal, is_vertical
from bom.find_table.select_bom import BomMatch, box_row_ys


@dataclass(frozen=True)
class ParentArea:
    """상위 박스(또는 상위 표) 하나의 영역"""
    box_side: Line         # 연결선이 출발하는 세로변 (ParentLink.connector.box_side와 같은 선)
    row_ys: list[float]    # 행 경계 (위 → 아래), 행 번호 = ParentLink.box_row
    col_xs: list[float]    # 열 경계 (왼쪽 → 오른쪽)


def _merge_close(values: list[float]) -> list[float]:
    merged = []
    for value in sorted(values):
        if not merged or value - merged[-1] > TOUCH_TOL:
            merged.append(value)
    return merged


def find_parent_areas(match: BomMatch) -> list[ParentArea]:
    """연결선의 세로변마다 상위 영역(행·열 경계)을 만든다"""
    areas = []
    for side in {c.box_side for c in match.connectors}:
        row_ys = box_row_ys(match.lines, side)
        side_x = (side.x1 + side.x2) / 2
        lefts = [min(ln.x1, ln.x2) for ln in match.lines
                 if is_horizontal(ln) and abs(max(ln.x1, ln.x2) - side_x) <= TOUCH_TOL]
        left_x = min(lefts)
        inner = [(ln.x1 + ln.x2) / 2 for ln in match.lines
                 if is_vertical(ln)
                 and left_x - TOUCH_TOL <= (ln.x1 + ln.x2) / 2 <= side_x + TOUCH_TOL
                 and min(ln.y1, ln.y2) >= row_ys[0] - TOUCH_TOL
                 and max(ln.y1, ln.y2) <= row_ys[-1] + TOUCH_TOL]
        col_xs = _merge_close([left_x, side_x] + inner)
        areas.append(ParentArea(side, row_ys, col_xs))
    return areas


def strokes_by_parent_cell(area: ParentArea, lines: list[Line]) -> dict[tuple[int, int], list[Line]]:
    """상위 영역 안에서 행·열 경계선이 아닌 선(글자 획 + 취소선)을 칸별로. 키 = (행, 열)"""
    x_min, x_max = area.col_xs[0], area.col_xs[-1]
    y_min, y_max = area.row_ys[0], area.row_ys[-1]
    result: dict[tuple[int, int], list[Line]] = {}
    for ln in lines:
        if not (x_min <= min(ln.x1, ln.x2) and max(ln.x1, ln.x2) <= x_max
                and y_min <= min(ln.y1, ln.y2) and max(ln.y1, ln.y2) <= y_max):
            continue
        if abs(ln.y1 - ln.y2) <= TOUCH_TOL and any(abs((ln.y1 + ln.y2) / 2 - y) <= TOUCH_TOL for y in area.row_ys):
            continue                               # 행 경계선
        if abs(ln.x1 - ln.x2) <= TOUCH_TOL and any(abs((ln.x1 + ln.x2) / 2 - x) <= TOUCH_TOL for x in area.col_xs):
            continue                               # 열 경계선
        row = bisect_right(area.row_ys, (ln.y1 + ln.y2) / 2) - 1
        col = bisect_right(area.col_xs, (ln.x1 + ln.x2) / 2) - 1
        result.setdefault((row, col), []).append(ln)
    return result

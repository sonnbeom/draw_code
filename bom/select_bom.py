"""2단계 ④: 표 후보 묶음 중 BOM 고르기 (docs/03 3-1절).

규칙: '연결선 수 = 모부품 박스 행 수'인 묶음이 BOM이다.
  - 표 윗변   : 꽉 찬 가로선(가장 긴 가로선과 같은 길이) 3개 이상 중 맨 위 선
  - 연결선    : 박스 세로변의 칸 중간에서 출발 → 가로로 가다 꺾임 → 아래로 내려와 윗변에 닿음
  - 박스 행 수: 박스 세로변에 닿는 박스 가로선 개수 - 1
  - 닿는지는 선의 x1·y1이 아니라 그 역할의 끝점 좌표로 판정 (선이 기울 수 있음, 트러블슈팅 05)
"""

import math
from dataclasses import dataclass

from bom.extract_lines import Line
from bom.geometry import (TOUCH_TOL, bottom_end, is_horizontal, is_vertical,
                          length, point_on_line, top_end)

FULL_LEN_TOL = 1.0   # 꽉 찬 가로선: 가장 긴 가로선과 길이 차이가 이 이내
MIN_FULL_ROWS = 3    # 꽉 찬 가로선이 이만큼 있어야 표로 본다 (위·아래 테두리 + 행 경계 1개)

Point = tuple[float, float]

@dataclass(frozen=True)
class Connector:
    """연결선: 상위 BOM에서 하위 BOM으로 연결하는 선을 나타냄"""
    leg: Line        # 가로 부분
    drop: Line       # 세로 부분
    box_side: Line   # 출발한 모부품 박스의 세로변

@dataclass(frozen=True)
class BomMatch:
    """ """
    lines: list[Line] #하위 BOM을 이루는 선분들
    bom_top: Line # 하위 BOM의 윗변 Connector와 만나는 선분
    connectors: list[Connector] # 상위 품번들

def _y_range(line: Line) -> tuple[float, float]:
    """ y 범위 구하기 (위쪽 y, 아래쪽 y) """
    return min(line.y1, line.y2), max(line.y1, line.y2)

def _ends(line: Line) -> list[tuple[Point, Point]]:
    """선의 두 끝점을 (닿는지 볼 끝, 반대쪽 끝) 쌍으로 둘 다 돌려줌 어느 끝이 닿는지 모를 때 둘 다 보려고"""
    p1, p2 = (line.x1, line.y1), (line.x2, line.y2)
    return [(p1, p2), (p2, p1)]

def full_width_lines(group: list[Line]) -> list[Line]:
    """꽉 찬 가로선: 가장 긴 가로선과 길이가 거의 같은 가로선들 (표 윗변·행 경계·아랫변, 샘플은 취소선도)"""
    horizontals = [ln for ln in group if is_horizontal(ln)]
    if not horizontals:
        return []
    longest = max(length(ln) for ln in horizontals)
    return [ln for ln in horizontals if length(ln) >= longest - FULL_LEN_TOL]

# ① 하위 bom 윗변 -----------------------------------------------------------------
def find_top(group: list[Line]) -> Line | None:
    """ 꽉 찬 가로선이 3개 이상이면 그 중 맨 위 선을, 아니면 None을 리턴 """
    full = full_width_lines(group)
    if len(full) < MIN_FULL_ROWS:
        return None
    return min(full, key=lambda ln: _y_range(ln)[0])  # 두 끝 중 위쪽 y가 가장 작은 선 = 맨 위

# ② 연결선 찾기 -------------------------------------------------------------
def _find_leg(group: list[Line], drop_top: Point) -> tuple[Line, Point] | None:
    """drop의 위 끝(꺾이는 점)에 한쪽 끝이 닿는 가로선 leg와, leg의 반대쪽 끝(= 박스 쪽 출발점)."""
    for ln in group:
        if not is_horizontal(ln):
            continue
        for touch_end, far_end in _ends(ln):
            if math.dist(touch_end, drop_top) <= TOUCH_TOL:  # 두 점 사이 거리 0.5 이내면 같은 점
                return ln, far_end
    return None

def _find_box_side(group: list[Line], drop: Line, leg_start: Point) -> Line | None:
    """ 상위 bom의 세로 변
    leg 출발점이 세로선 위에 있고 그 중간에 있어야 합니다. 凸 모양 부품은 접점이 세로선의 중간이 아니어서 거를 수 있음."""
    for side in group:
        if side is drop or not is_vertical(side):
            continue
        side_top_y, side_bottom_y = _y_range(side)
        if (point_on_line(*leg_start, side)                                       # 출발점이 세로변 위에 있나
                and side_top_y + TOUCH_TOL < leg_start[1] < side_bottom_y - TOUCH_TOL):  # 끝이 아니라 중간
            return side
    return None


def find_connectors(group: list[Line], bom_top: Line) -> list[Connector]:
    """하위 bom에 닿는 세로선마다, 위로 거슬러 올라가 박스까지 이어지는지 본다."""
    bom_top_y = _y_range(bom_top)[0]  # 하위 bom 윗변 높이
    connectors = []
    for drop in group: # drop 후보 찾기
        if not is_vertical(drop):
            continue
        drop_top = top_end(drop)        # drop의 위 끝 (leg와 꺾이는 점)
        drop_bottom = bottom_end(drop)  # drop의 아래 끝 (하위 bom 윗변에 닿는 점)
        drop_lands_on_bom = point_on_line(*drop_bottom, bom_top)  # 아래 끝 점이 윗변 위에 있나 세로선의 아래 끝점이 하위 박스 윗변(top) 위에 있는지 확인합니다.
        drop_starts_above_bom = drop_top[1] < bom_top_y - TOUCH_TOL  # 위 끝은 윗변보다 위 (윗변에 그냥 붙은 짧은 세로선 제외) 세로선의 위 끝점이 윗변보다 충분히 위에 있는지 확인합니다.
        if not (drop_lands_on_bom and drop_starts_above_bom):
            continue

        leg_found = _find_leg(group, drop_top)
        if leg_found is None:
            continue
        leg, leg_start = leg_found  # leg와 그 출발점(박스 쪽 끝)

        box_side = _find_box_side(group, drop, leg_start) # leg 출발점이 닿는 상위 bom의 세로변
        if box_side is None:
            continue
        connectors.append(Connector(leg, drop, box_side))
    return connectors

# ③ 박스 행 수 -------------------------------------------------------------
def count_box_rows(group: list[Line], box_side: Line) -> int:
    """상위 BOM이 몇 행(칸)으로 나눠져 있는지 세는 함수 box_side를 기준으로 계산
    박스 가로선은 세로변에 닿는 끝에서 왼쪽으로 뻗음. 오른쪽으로 뻗는 연결선 leg는 배제합니다.
    """
    ys = set()  
    for ln in group:
        if not is_horizontal(ln):
            continue
        for end, other in _ends(ln):                        # 변경: 두 끝점을 각각 본다
            if (point_on_line(*end, box_side)               # 이 끝이 세로변 위에 있고
                    and other[0] < end[0] - TOUCH_TOL):     # 반대쪽 끝이 왼쪽이면 박스 가로선
                ys.add(round(end[1], 1))  # 변경: 그 끝점의 y. 같은 높이 선이 여러 개여도 한 번만
    return max(len(ys) - 1, 0)

# 전체 ---------------------------------------------------------------------
def select_bom(groups: list[list[Line]]) -> BomMatch | None:
    """연결선 수 = 박스 행 수인 첫 묶음을 BOM으로 돌려준다. 없으면 None."""
    for group in groups:
        bom_top = find_top(group)
        if bom_top is None:
            continue
        connectors = find_connectors(group, bom_top)
        if not connectors:
            continue
        sides = {c.box_side for c in connectors}  # 박스가 여러 개일 수 있어 세로변별로 센다
        rows = sum(count_box_rows(group, side) for side in sides)
        if len(connectors) == rows:
            return BomMatch(group, bom_top, connectors)
    return None


"""2단계 ④: 표 후보 묶음 중 BOM 고르기 (docs/03 3-1절).

규칙: '연결선 수 = 모부품 박스 행 수'인 묶음이 BOM이다.
  - 표 윗변   : 꽉 찬 가로선(가장 긴 가로선과 같은 길이) 3개 이상 중 맨 위 선
  - 연결선    : 박스 세로변의 칸 중간에서 출발 → 가로로 가다 꺾임 → 아래로 내려와 윗변에 닿음
  - 박스 행 수: 박스 세로변에 닿는 박스 가로선 개수 - 1
"""

from dataclasses import dataclass

from bom.extract_lines import Line
from bom.geometry import TOUCH_TOL, is_horizontal, is_vertical, length, point_on_line

FULL_LEN_TOL = 1.0   # 꽉 찬 가로선: 가장 긴 가로선과 길이 차이가 이 이내
MIN_FULL_ROWS = 3    # 꽉 찬 가로선이 이만큼 있어야 표로 본다 (위·아래 테두리 + 행 경계 1개)

@dataclass(frozen=True)
class Connector:
    """연결선: 상위 BOM에서 하위 BOM으로 연결하는 선을 나타냄"""
    leg: Line        # 가로 부분
    drop: Line       # 세로 부분: 
    box_side: Line   # 출발한 모부품 박스의 세로변

@dataclass(frozen=True)
class BomMatch:
    """ """
    lines: list[Line] #하위 BOM을 이루는 선분들
    top: Line # 하위 BOM의 윗변 Connector와 만나는 선분
    connectors: list[Connector] # 상위 품번들

def _y_range(line: Line) -> tuple[float, float]:
    """ y 범위 구하기 """
    return min(line.y1, line.y2), max(line.y1, line.y2)

# ① 하위 bom 윗변 -----------------------------------------------------------------
def find_top(group: list[Line]) -> Line | None:
    """ 가로선(길이가 유사한 약간의 오차는 허용한다)이 3개 이상이면 그 중 맨 위 선을, 아니면 None을 리턴 """
    horizontals = [ln for ln in group if is_horizontal(ln)]
    if not horizontals:
        return None
    longest = max(length(ln) for ln in horizontals)
    full = [ln for ln in horizontals if length(ln) >= longest - FULL_LEN_TOL]
    
    if len(full) < MIN_FULL_ROWS:
        return None
    
    return min(full, key = lambda ln: ln.y1)

# ② 연결선 찾기 -------------------------------------------------------------
def _find_leg(group: list[Line], drop: Line, y_up: float) -> Line | None:
    """세로 부분의 위 끝(drop.x1, y_up)에서 꺾여 나가는 가로선."""
    for ln in group:
        if (is_horizontal(ln)
                and abs(ln.y1 - y_up) <= TOUCH_TOL
                and (abs(ln.x1 - drop.x1) <= TOUCH_TOL or abs(ln.x2 - drop.x1) <= TOUCH_TOL)):
            return ln
    return None

def _find_box_side(group: list[Line], drop: Line, x: float, y: float) -> Line | None:
    """ 상위 bom의 세로 변
    접점이 세로선의 중간에 있어야 합니다. 凸 모양 부품은 접점이 세로선의 중간이 아니어서 거를 수 있음."""
    for ln in group:
        if ln is drop or not is_vertical(ln): 
            continue
        side_up, side_down = _y_range(ln)
        if abs(ln.x1 - x) <= TOUCH_TOL and side_up + TOUCH_TOL < y < side_down - TOUCH_TOL:
            return ln
    return None


def find_connectors(group: list[Line], top: Line) -> list[Connector]:
    """하위 bom에 닿는 세로선마다, 위로 거슬러 올라가 박스까지 이어지는지 본다."""
    connectors = []
    for drop in group: # drop 후보 찾기
        if not is_vertical(drop):
            continue
        y_up, y_down = _y_range(drop)
        lands_on_top = (abs(y_down - top.y1) <= TOUCH_TOL        # 세로선(drop)의 아래 끝이 윗변과 같은 높이인가?
                        and point_on_line(drop.x1, y_down, top))  # 그 아래 끝 점(drop과 하위 bom 만나는 지점)이 윗변의 x 범위 안에 있나?
        above_top = y_up < top.y1 - TOUCH_TOL                     # drop 아래 끝 점이 윗 변 위에 정확히 맞닿아 있는가?
        if not (lands_on_top and above_top): 
            continue

        leg = _find_leg(group, drop, y_up) 
        if leg is None:
            continue
        start_x = leg.x1 if abs(leg.x2 - drop.x1) <= TOUCH_TOL else leg.x2  # bom과 닿는 leg인지 leg.x2가 꺾이는 점(drop의 x)에 붙어 있으면 → 반대쪽인 leg.x1이 출발점

        box_side = _find_box_side(group, drop, start_x, leg.y1) # leg과 맞닿는 상위 bom의 세로변
        if box_side is None:
            continue
        connectors.append(Connector(leg, drop, box_side))
    return connectors

# ③ 박스 행 수 -------------------------------------------------------------
def count_box_rows(group: list[Line], box_side: Line) -> int:
    """상위 BOM이 몇 행(칸)으로 나눠져 있는지 세는 함수 box_side를 기준으로 계산
    연결선 즉 leg와 닿는 점은 배제합니다.
    """
    side_up, side_down = _y_range(box_side)
    ys = set()  # Java의 HashSet<Double>
    for ln in group:
        if (is_horizontal(ln) # 가로선인지 체크
                and side_up - TOUCH_TOL <= ln.y1 <= side_down + TOUCH_TOL #가로 선의 높이가 box_side 범위 안에 있을 것
                and point_on_line(box_side.x1, ln.y1, ln) # box_side의 좌표가 이 가로선에 닿을 것
                and min(ln.x1, ln.x2) < box_side.x1 - TOUCH_TOL):  # 행수를 셀 때 연결선을 빼기 위함
            ys.add(round(ln.y1, 1))  # 같은 높이 선이 여러 개여도 한 번만
    return max(len(ys) - 1, 0)

# 전체 ---------------------------------------------------------------------
def select_bom(groups: list[list[Line]]) -> BomMatch | None:
    """연결선 수 = 박스 행 수인 첫 묶음을 BOM으로 돌려준다. 없으면 None."""
    for group in groups:
        top = find_top(group)
        if top is None:
            continue
        connectors = find_connectors(group, top)
        if not connectors:
            continue
        sides = {c.box_side for c in connectors}  # 박스가 여러 개일 수 있어 세로변별로 센다
        rows = sum(count_box_rows(group, side) for side in sides)
        if len(connectors) == rows:
            return BomMatch(group, top, connectors)
    return None
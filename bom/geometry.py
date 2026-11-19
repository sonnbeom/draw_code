import math

from bom.extract_lines import Line

MAX_TILT_DEG = 3.0  # 가로/세로로 볼 최대 기울기 (도). 엔지니어 도면은 선이 살짝 기운다 (트러블슈팅 05)
TOUCH_TOL = 0.5     # 맞닿음 판정 허용 오차 (pt). 샘플에선 닿는 끝점 거리가 정확히 0


def _tilt_deg(along: float, across: float) -> float:
    """ y 변화량, x 변화량을 기반으로 각도를 측정 두번째 인자 기분으로 측정 
    예: 세로선이면 along = y 변화량, across = x 변화량."""
    return math.degrees(math.atan2(across, along))  # atan2(옆, 진행) = 진행 방향에서 벌어진 각

def is_horizontal(line: Line) -> bool:
    """가로선인가: 가로 방향에서 3° 이하로 기울었다."""
    dx = abs(line.x2 - line.x1)
    dy = abs(line.y2 - line.y1)
    return dx > 0 and _tilt_deg(dx, dy) <= MAX_TILT_DEG  # dx > 0: 가로 변화가 있어야 하며 y 변화량은 각도로 측정해서 3도 까지 허용

def is_vertical(line: Line) -> bool:
    """세로선인가: 세로 방향에서 3° 이하로 기울었다."""
    dx = abs(line.x2 - line.x1)
    dy = abs(line.y2 - line.y1)
    return dy > 0 and _tilt_deg(dy, dx) <= MAX_TILT_DEG # dy > 0: 세로 변화가 있어야 하며 x 변화량은 각도로 측정해서 3도 까지 허용

def length(line: Line) -> float:
    """선분 길이 = x 변화량 + y 변화량 (가로·세로선이면 실제 길이와 거의 같다)"""
    return abs(line.x2 - line.x1) + abs(line.y2 - line.y1)

def top_end(line: Line) -> tuple[float, float]:
    """선분의 두 끝점 중 위쪽에 있는 점의 좌표를 돌려주는 함수
    선의 위쪽 끝 (x, y). pymupdf는 y가 아래로 커지므로 y가 작은 쪽."""
    return (line.x1, line.y1) if line.y1 <= line.y2 else (line.x2, line.y2)

def bottom_end(line: Line) -> tuple[float, float]:
    """ 선분의 두 끝점 중 아래쪽에 있는 점의 좌표를 돌려주는 함수
    선의 아래쪽 끝 (x, y). y가 큰 쪽."""
    return (line.x2, line.y2) if line.y1 <= line.y2 else (line.x1, line.y1)

def point_on_line(x: float, y: float, line: Line) -> bool:
    """점 (x, y)가 선 ln 위에 있는가 (허용 오차 포함).
    가로·세로선이라 선의 x범위·y범위 안에 들어오면 선 위에 있는 것이다."""
    return (min(line.x1, line.x2) - TOUCH_TOL <= x <= max(line.x1, line.x2) + TOUCH_TOL
            and min(line.y1, line.y2) - TOUCH_TOL <= y <= max(line.y1, line.y2) + TOUCH_TOL)

def touches(a: Line, b: Line) -> bool:
    """두 선이 닿는가: 한 선의 끝점이 다른 선 위에 있다 (모서리·T자 모두)."""
    return (point_on_line(a.x1, a.y1, b) or point_on_line(a.x2, a.y2, b)
            or point_on_line(b.x1, b.y1, a) or point_on_line(b.x2, b.y2, a))

def bbox(lines: list[Line]) -> tuple[float, float, float, float]:
    """선 묶음을 감싸는 네모. 반환 순서: (x_min, x_max, y_min, y_max) (트러블슈팅 01)"""
    xs = [v for ln in lines for v in (ln.x1, ln.x2)]
    ys = [v for ln in lines for v in (ln.y1, ln.y2)]
    return min(xs), max(xs), min(ys), max(ys)



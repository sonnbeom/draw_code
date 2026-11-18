from bom.extract_lines import Line

AXIS_TOL = 0.5   # 수평/수직 판정 허용 오차 (pt)
TOUCH_TOL = 0.5  # 맞닿음 판정 허용 오차 (pt). 샘플에선 닿는 끝점 거리가 정확히 0

def is_horizontal(line: Line) -> bool:
    """선분이 수평인지 확인"""
    return abs(line.y1 - line.y2) <= AXIS_TOL

def is_vertical(line: Line) -> bool:
    """선분이 수직인지 확인"""
    return abs(line.x1 - line.x2) <= AXIS_TOL

def length(line: Line) -> float:
    """선분 길이 x 변화량 + y 변화량"""
    return abs(line.x2 - line.x1) + abs(line.y2 - line.y1) 

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
    """선 묶음을 감싸는 네모"""
    xs = [v for ln in lines for v in(ln.x1, ln.x2)]
    ys = [v for ln in lines for v in(ln.y1, ln.y2)]
    return min(xs), max(xs), min(ys), max(ys)


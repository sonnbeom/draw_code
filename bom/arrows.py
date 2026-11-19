# 모듈이 하는 일: 화살촉을 찾아서 연결선 끝을 bom 윗변까지 연결시켜 하나로 인지하게 만드는 모듈
import math
from collections import defaultdict
from dataclasses import replace

from bom.extract_lines import Line
from bom.geometry import TOUCH_TOL

SIDE_FROM = 0.3   # 밑변의 30% 지점부터
SIDE_TO = 0.7     # 70% 지점까지 닿아야 화살촉 (꼭짓점 근처는 제외)
MIN_COS = 0.99    # 선 방향과 꼭짓점 방향이 이만큼 같아야 함 (cos 0.99 ≈ 8° 이내)
CELL = 10.0       # 끝점 찾기용 칸 크기 (pt). 근처 선만 보려고 좌표를 칸으로 나눔

Point = tuple[float, float]  # 타입에 이름 붙이기 (읽기 쉽게)

# ① 삼각형 후보 찾기 ---------------------------------------------------------------
def _triangle_points(path_lines: list[Line]) -> list[Point] | None:
    """한 path의 선이 정확히 3개이고 서로 다른 꼭짓점이 3개면 그 꼭짓점들, 아니면 None."""
    if len(path_lines) != 3: 
        return None
    points: list[Point] = []
    for ln in path_lines:
        for p in ((ln.x1, ln.y1), (ln.x2, ln.y2)):
            if all(math.dist(p, q) > TOUCH_TOL for q in points):  # 이미 있는 점과 거리가 다르면 추가
                points.append(p) #(10, 0)
    return points if len(points) == 3 else None

def find_triangle_candidates(lines: list[Line]) -> list[tuple[int, list[Point]]]:
    """(path_id, 꼭짓점 3개) 목록. 같은 삼각형을 칠하기+선으로 두 번 그린 것은 하나만."""
    by_path = defaultdict(list)  # Java의 Map<Integer, List<Line>> + computeIfAbsent
    for ln in lines:
        by_path[ln.path_id].append(ln)

    triangles = []
    seen = set()
    for path_id, path_lines in by_path.items():
        points = _triangle_points(path_lines)
        if points is None:
            continue
        key = tuple(sorted((round(x, 1), round(y, 1)) for x, y in points))  # 순서 상관없는 꼭짓점 묶음
        if key in seen:
            continue
        seen.add(key)
        triangles.append((path_id, points))
    return triangles

# ② 근처 끝점 빨리 찾기 --------------------------------------------------------
def _cell(x: float, y: float) -> tuple[int, int]:
    """좌표가 속한 칸 근처로 연결하기 위함"""
    return int(x // CELL), int(y // CELL)


def _index_endpoints(lines: list[Line]) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """칸을 나누고각 칸에 선분을 분류함 cell 함수를 통해 나누고 해당 cell에 포함되는 선분을 1,2번째로 넣어줌"""
    index = defaultdict(list)
    for i, ln in enumerate(lines):
        index[_cell(ln.x1, ln.y1)].append((i, 1))
        index[_cell(ln.x2, ln.y2)].append((i, 2))
    return index


def _end_and_other(ln: Line, which: int) -> tuple[Point, Point]:
    """선분과 몇번째 끝인지 인풋을 받음 지정한 끝점과 반대쪽 끝점을 줌 """
    if which == 1:
        return (ln.x1, ln.y1), (ln.x2, ln.y2)
    return (ln.x2, ln.y2), (ln.x1, ln.y1)

# ③ 조건 2·3 검사 -------------------------------------------------------------
def _position_on_side(p: Point, a: Point, b: Point) -> float | None:
    """점 p가 점,a,b위에 있는가 + 어디에 있는가 점 p가 변 a→b 위에 있으면 위치 비율(a=0, b=1), 아니면 None."""
    side_len2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 # 변 길이의 제곱
    t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / side_len2 # 0 a----b 1  / t = 0 a위치 t = 1 b 위치
    foot = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))  # p에서 변에 내린 수선의 발 t를 기반으로 한 위치 
    if math.dist(p, foot) > TOUCH_TOL:  # 변에서 떨어져 있음
        return None
    return t


def _same_side(p: Point, q: Point, a: Point, b: Point) -> bool:
    """ 두 점 p와 q가 직선 a-b를 기준으로 같은 편에 있는지 확인하는 함수 
    cross_p는 p가 직선의 어느 쪽에 있는지 알려 주는 숫자
    점 p와 q가 직선 a-b의 같은 쪽에 있는가 (외적 부호 비교)."""
    cross_p = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    cross_q = (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0])
    return cross_p * cross_q > 0


def _points_at(start: Point, end: Point, target: Point) -> bool:
    """선분이 어떤 목표 지점(target)을 똑바로 가리키고 있는지 확인하는 함수
    선을 start에서 end 쪽으로 쭉 연장했을 때 target 방향과 거의 같으면 True입니다.
    """
    v1 = (end[0] - start[0], end[1] - start[1])
    v2 = (target[0] - end[0], target[1] - end[1])
    norm = math.hypot(*v1) * math.hypot(*v2)
    return norm > 0 and (v1[0] * v2[0] + v1[1] * v2[1]) / norm >= MIN_COS  # 두 방향의 cos

# 전체 -------------------------------------------------------------------------
def merge_arrows(lines: list[Line]) -> list[Line]:
    """화살촉으로 들어오는 선의 끝을 꼭짓점까지 늘린 새 목록을 돌려준다 (원래 목록은 안 바꿈)."""
    index = _index_endpoints(lines)
    new_ends = {}  # (선 번호, 몇 번째 끝) → 옮길 꼭짓점

    for path_id, points in find_triangle_candidates(lines):
        for k in range(3):  # 세 변을 차례로 밑변 후보로
            a, b = points[k], points[(k + 1) % 3]
            tip = points[(k + 2) % 3]  # 밑변 반대쪽 꼭짓점

            cx0, cy0 = _cell(min(a[0], b[0]), min(a[1], b[1]))
            cx1, cy1 = _cell(max(a[0], b[0]), max(a[1], b[1]))
            for cx in range(cx0 - 1, cx1 + 2):        # 밑변이 걸친 칸 + 이웃 칸
                for cy in range(cy0 - 1, cy1 + 2):
                    for i, which in index.get((cx, cy), []):
                        ln = lines[i]
                        if ln.path_id == path_id:      # 삼각형 자기 선은 제외
                            continue
                        end, other = _end_and_other(ln, which)
                        t = _position_on_side(end, a, b)
                        if t is None or not (SIDE_FROM <= t <= SIDE_TO):   # 조건 2
                            continue
                        if _same_side(other, tip, a, b):                  # 바깥에서 와야 함
                            continue
                        if not _points_at(other, end, tip):               # 조건 3
                            continue
                        new_ends[(i, which)] = tip

    merged = list(lines)  # 복사본 (Java의 new ArrayList<>(lines))
    for (i, which), (x, y) in new_ends.items():
        if which == 1:
            merged[i] = replace(merged[i], x1=x, y1=y)  # frozen이라 고친 복사본을 새로 만듦
        else:
            merged[i] = replace(merged[i], x2=x, y2=y)
    return merged
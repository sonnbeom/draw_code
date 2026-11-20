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
Cell = tuple[int, int]       # 칸 번호 (가로 칸, 세로 칸)
EndRef = tuple[int, int]     # (선 번호, 몇 번째 끝 1 또는 2)

# ① 삼각형 후보 찾기 ---------------------------------------------------------------
def _triangle_corners(path_lines: list[Line]) -> list[Point] | None:
    """한 path의 선이 정확히 3개이고 서로 다른 꼭짓점이 3개면 그 꼭짓점들, 아니면 None."""
    if len(path_lines) != 3:
        return None
    corners: list[Point] = []
    for ln in path_lines:
        for line_end in ((ln.x1, ln.y1), (ln.x2, ln.y2)):
            if all(math.dist(line_end, corner) > TOUCH_TOL for corner in corners):  # 이미 있는 꼭짓점과 다른 점이면 추가
                corners.append(line_end)
    return corners if len(corners) == 3 else None

def find_triangle_candidates(lines: list[Line]) -> list[tuple[int, list[Point]]]:
    """(path_id, 꼭짓점 3개) 목록. 같은 삼각형을 칠하기+선으로 두 번 그린 것은 하나만."""
    lines_by_path = defaultdict(list)  # Java의 Map<Integer, List<Line>> + computeIfAbsent
    for ln in lines:
        lines_by_path[ln.path_id].append(ln)

    triangles = []
    seen_keys = set()
    for path_id, path_lines in lines_by_path.items():
        corners = _triangle_corners(path_lines)
        if corners is None:
            continue
        corner_key = tuple(sorted((round(x, 1), round(y, 1)) for x, y in corners))  # 순서 상관없는 꼭짓점 묶음
        if corner_key in seen_keys:
            continue
        seen_keys.add(corner_key)
        triangles.append((path_id, corners))
    return triangles

# ② 근처 끝점 빨리 찾기 --------------------------------------------------------
def _cell(x: float, y: float) -> Cell:
    """좌표가 속한 칸 번호. 가까운 점은 같은 칸이 됨 (트러블슈팅 06)"""
    return int(x // CELL), int(y // CELL)


def _index_endpoints(lines: list[Line]) -> dict[Cell, list[EndRef]]:
    """칸을 나누고 각 칸에 선분 끝점을 분류함 cell 함수를 통해 나누고 해당 cell에 (선 번호, 1번째 또는 2번째 끝)을 넣어줌"""
    endpoint_index = defaultdict(list)
    for line_idx, ln in enumerate(lines):
        endpoint_index[_cell(ln.x1, ln.y1)].append((line_idx, 1))
        endpoint_index[_cell(ln.x2, ln.y2)].append((line_idx, 2))
    return endpoint_index


def _touch_and_far_end(ln: Line, end_no: int) -> tuple[Point, Point]:
    """선분과 몇번째 끝인지 인풋을 받음 지정한 끝점(touch_end)과 반대쪽 끝점(far_end)을 줌 """
    if end_no == 1:
        return (ln.x1, ln.y1), (ln.x2, ln.y2)
    return (ln.x2, ln.y2), (ln.x1, ln.y1)

# ③ 조건 2·3 검사 -------------------------------------------------------------
def _position_on_side(point: Point, side_a: Point, side_b: Point) -> float | None:
    """점 point가 변 side_a→side_b 위에 있는가 + 어디에 있는가. 위에 있으면 위치 비율(side_a=0, side_b=1), 아니면 None."""
    side_len_sq = (side_b[0] - side_a[0]) ** 2 + (side_b[1] - side_a[1]) ** 2 # 변 길이의 제곱
    ratio = ((point[0] - side_a[0]) * (side_b[0] - side_a[0])
             + (point[1] - side_a[1]) * (side_b[1] - side_a[1])) / side_len_sq # 0 a----b 1  / 0 = a 위치, 1 = b 위치
    foot = (side_a[0] + ratio * (side_b[0] - side_a[0]),
            side_a[1] + ratio * (side_b[1] - side_a[1]))  # point에서 변에 내린 수선의 발 ratio를 기반으로 한 위치
    if math.dist(point, foot) > TOUCH_TOL:  # 변에서 떨어져 있음
        return None
    return ratio


def _same_side(point_1: Point, point_2: Point, line_a: Point, line_b: Point) -> bool:
    """ 두 점 point_1과 point_2가 직선 line_a-line_b를 기준으로 같은 편에 있는지 확인하는 함수
    cross는 점이 직선의 어느 쪽에 있는지 알려 주는 숫자 (외적 부호 비교)."""
    cross_1 = (line_b[0] - line_a[0]) * (point_1[1] - line_a[1]) - (line_b[1] - line_a[1]) * (point_1[0] - line_a[0])
    cross_2 = (line_b[0] - line_a[0]) * (point_2[1] - line_a[1]) - (line_b[1] - line_a[1]) * (point_2[0] - line_a[0])
    return cross_1 * cross_2 > 0


def _points_at(far_end: Point, touch_end: Point, target: Point) -> bool:
    """선분이 어떤 목표 지점(target)을 똑바로 가리키고 있는지 확인하는 함수
    선을 far_end에서 touch_end 쪽으로 쭉 연장했을 때 target 방향과 거의 같으면 True입니다.
    """
    line_dir = (touch_end[0] - far_end[0], touch_end[1] - far_end[1])    # 선 방향
    target_dir = (target[0] - touch_end[0], target[1] - touch_end[1])    # 선 끝에서 목표 방향
    norm = math.hypot(*line_dir) * math.hypot(*target_dir)
    return norm > 0 and (line_dir[0] * target_dir[0] + line_dir[1] * target_dir[1]) / norm >= MIN_COS  # 두 방향의 cos

# 전체 -------------------------------------------------------------------------
def merge_arrows(lines: list[Line]) -> list[Line]:
    """화살촉으로 들어오는 선의 끝을 꼭짓점까지 늘린 새 목록을 돌려준다 (원래 목록은 안 바꿈)."""
    endpoint_index = _index_endpoints(lines)
    new_ends = {}  # (선 번호, 몇 번째 끝) → 옮길 꼭짓점

    for path_id, corners in find_triangle_candidates(lines):
        for k in range(3):  # 세 변을 차례로 밑변 후보로
            base_a, base_b = corners[k], corners[(k + 1) % 3]
            tip = corners[(k + 2) % 3]  # 밑변 반대쪽 꼭짓점

            cell_x_from, cell_y_from = _cell(min(base_a[0], base_b[0]), min(base_a[1], base_b[1]))
            cell_x_to, cell_y_to = _cell(max(base_a[0], base_b[0]), max(base_a[1], base_b[1]))
            for cell_x in range(cell_x_from - 1, cell_x_to + 2):        # 밑변이 걸친 칸 + 이웃 칸
                for cell_y in range(cell_y_from - 1, cell_y_to + 2):
                    for line_idx, end_no in endpoint_index.get((cell_x, cell_y), []):
                        ln = lines[line_idx]
                        if ln.path_id == path_id:      # 삼각형 자기 선은 제외
                            continue
                        touch_end, far_end = _touch_and_far_end(ln, end_no)
                        ratio = _position_on_side(touch_end, base_a, base_b)
                        if ratio is None or not (SIDE_FROM <= ratio <= SIDE_TO):   # 조건 2
                            continue
                        if _same_side(far_end, tip, base_a, base_b):              # 바깥에서 와야 함
                            continue
                        if not _points_at(far_end, touch_end, tip):               # 조건 3
                            continue
                        new_ends[(line_idx, end_no)] = tip

    merged = list(lines)  # 복사본 (Java의 new ArrayList<>(lines))
    for (line_idx, end_no), (tip_x, tip_y) in new_ends.items():
        if end_no == 1:
            merged[line_idx] = replace(merged[line_idx], x1=tip_x, y1=tip_y)  # frozen이라 고친 복사본을 새로 만듦
        else:
            merged[line_idx] = replace(merged[line_idx], x2=tip_x, y2=tip_y)
    return merged

from collections import deque

from bom.extract_lines import Line
from bom.geometry import bbox, is_horizontal, is_vertical, length, touches

MIN_TABLE_LINE = 14.0    # 표 선 최소 길이 (pt). 글자 획은 이보다 짧고, 행 높이는 약 19.8
FRAME_LEN_RATIO = 0.5    # 테두리: 도면 폭(높이)의 50% 이상 길이
FRAME_EDGE_RATIO = 0.06  # 테두리: 도면 가장자리에서 6% 이내

# ① 후보 거르기 ------------------------------------------------------------
def filter_candidates(lines: list[Line]) -> list[Line]:
    """  가로 또는 세로이면서(대각선 아님) 길이 19 이상인 선만 남긴다 글자 제거"""
    return [
        ln for ln in lines
        if (is_horizontal(ln) or is_vertical(ln)) and length(ln) >= MIN_TABLE_LINE
        ]

# ② 테두리 선 지우기 -------------------------------------------------------
def remove_frame(lines: list[Line]) -> list[Line]:
    x_min, x_max, y_min, y_max = bbox(lines) # 도면 전체 범위 = 후보 선 전체를 감싸는 네모
    w = x_max - x_min  # 도면 폭
    h = y_max - y_min  # 도면 높이

    kept = []
    for ln in lines:
        if is_horizontal(ln):
            long_enough = length(ln) >= FRAME_LEN_RATIO * w # 길이가 도면 폭의 50% 이상인지
            near_edge = (ln.y1 - y_min <= FRAME_EDGE_RATIO * h  #선의 y가 위쪽 끝이나 아래쪽 끝에서 도면 높이의 6% 이내인지 안에 있는지
                         or y_max - ln.y1 <= FRAME_EDGE_RATIO * h)
        else:  # 세로선 (①을 거쳤으니 가로 아니면 세로)
            long_enough = length(ln) >= FRAME_LEN_RATIO * h
            near_edge = (ln.x1 - x_min <= FRAME_EDGE_RATIO * w      # 왼쪽 가장자리
                         or x_max - ln.x1 <= FRAME_EDGE_RATIO * w)  # 오른쪽 가장자리

        if not (long_enough and near_edge):  # 둘 다 맞아야 테두리 → 아니면 남긴다
            kept.append(ln)
    return kept

# ③ 닿는 것끼리 묶기 -------------------------------------------------------
def group_lines(lines: list[Line]) -> list[list[Line]]:
    """닿는 선끼리 묶는다. 이웃의 이웃도 같은 묶음 (연결 요소, BFS)."""
    n = len(lines)
    visited = [False] * n  # Java의 boolean[] visited = new boolean[n]
    groups = []

    for start in range(n):
        if visited[start]:
            continue
        # 새 묶음 시작
        visited[start] = True
        queue = deque([start])  # Java의 ArrayDeque
        group = []
        while queue:
            i = queue.popleft()
            group.append(lines[i])
            for j in range(n):  # 아직 안 본 선 중 i와 닿는 것을 대기줄에
                if not visited[j] and touches(lines[i], lines[j]):
                    visited[j] = True
                    queue.append(j)
        groups.append(group)
    return groups

# 전체 ---------------------------------------------------------------------
def find_table_candidates(lines: list[Line]) -> list[list[Line]]:
    """① → ② → ③을 차례로 실행해 표 후보 묶음을 큰 순서로 돌려준다."""
    candidates = filter_candidates(lines)
    no_frame = remove_frame(candidates)
    groups = group_lines(no_frame)
    groups.sort(key=len, reverse=True)  # 선이 많은 묶음부터
    return groups
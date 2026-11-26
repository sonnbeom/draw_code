from collections import deque

from bom.find_table.arrows import merge_arrows 
from bom.pdf_lines.extract_lines import Line
from bom.pdf_lines.geometry import bbox, is_horizontal, is_vertical, length, touches

MIN_TABLE_LINE = 14.0    # 표 선 최소 길이 (pt). 글자 획은 최대 14.2, 상위 박스 1칸 세로변은 18.4라 그 사이로 잡음
FRAME_LEN_RATIO = 0.5    # 테두리: 도면 폭(높이)의 50% 이상 길이
FRAME_EDGE_RATIO = 0.06  # 테두리: 도면 가장자리에서 6% 이내

# ① 후보 거르기 ------------------------------------------------------------
def filter_candidates(lines: list[Line]) -> list[Line]:
    """  가로 또는 세로이면서(대각선 아님) 길이 14 이상인 선만 남긴다 글자 제거"""
    return [
        ln for ln in lines
        if (is_horizontal(ln) or is_vertical(ln)) and length(ln) >= MIN_TABLE_LINE
        ]

# ② 테두리 선 지우기 -------------------------------------------------------
def remove_frame(lines: list[Line]) -> list[Line]:
    x_min, x_max, y_min, y_max = bbox(lines) # 도면 전체 범위 = 후보 선 전체를 감싸는 네모
    drawing_width = x_max - x_min   # 도면 폭
    drawing_height = y_max - y_min  # 도면 높이

    kept = []
    for ln in lines:
        if is_horizontal(ln):
            long_enough = length(ln) >= FRAME_LEN_RATIO * drawing_width # 길이가 도면 폭의 50% 이상인지
            near_edge = (ln.y1 - y_min <= FRAME_EDGE_RATIO * drawing_height  #선의 y가 위쪽 끝이나 아래쪽 끝에서 도면 높이의 6% 이내인지 안에 있는지
                         or y_max - ln.y1 <= FRAME_EDGE_RATIO * drawing_height)
        else:  # 세로선 (①을 거쳤으니 가로 아니면 세로)
            long_enough = length(ln) >= FRAME_LEN_RATIO * drawing_height
            near_edge = (ln.x1 - x_min <= FRAME_EDGE_RATIO * drawing_width      # 왼쪽 가장자리
                         or x_max - ln.x1 <= FRAME_EDGE_RATIO * drawing_width)  # 오른쪽 가장자리

        if not (long_enough and near_edge):  # 둘 다 맞아야 테두리 → 아니면 남긴다
            kept.append(ln)
    return kept

# ③ 닿는 것끼리 묶기 -------------------------------------------------------
def group_lines(lines: list[Line]) -> list[list[Line]]:
    """닿는 선끼리 묶는다. 이웃의 이웃도 같은 묶음 (연결 요소, BFS)."""
    line_count = len(lines)
    visited = [False] * line_count  # Java의 boolean[] visited = new boolean[n]
    groups = []

    for seed_idx in range(line_count):
        if visited[seed_idx]:
            continue
        # 새 묶음 시작 (seed = 이 묶음의 첫 선)
        visited[seed_idx] = True
        queue = deque([seed_idx])  # Java의 ArrayDeque
        group = []
        while queue:
            current_idx = queue.popleft()
            group.append(lines[current_idx])
            for other_idx in range(line_count):  # 아직 안 본 선 중 current와 닿는 것을 대기줄에
                if not visited[other_idx] and touches(lines[current_idx], lines[other_idx]):
                    visited[other_idx] = True
                    queue.append(other_idx)
        groups.append(group)
    return groups

# 전체 ---------------------------------------------------------------------
def find_table_candidates(lines: list[Line]) -> list[list[Line]]:
    """⓪ → ① → ② → ③을 차례로 실행해 표 후보 묶음을 큰 순서로 돌려준다."""
    merged = merge_arrows(lines)            # ⓪ 화살촉: 선 끝을 꼭짓점까지 늘림 (트러블슈팅 04)
    candidates = filter_candidates(merged)  # ① 글자 획 제거 (길이 14 미만, 대각선)
    no_frame = remove_frame(candidates)     # ② 도면 테두리 제거
    groups = group_lines(no_frame)          # ③ 닿는 선끼리 묶기
    groups.sort(key=len, reverse=True)      # 선이 많은 묶음부터
    return groups
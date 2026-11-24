"""4단계 4-2: 리비전 삼각형 찾기 → 붙이기 → 안 숫자 읽기 (docs/설계/12_리비전_삼각형.md, Claude 작성).

  ① 찾기: 닫힌 세 선 + 정삼각형 + 밑변 수평 + 크기(변 ÷ 글자 높이)
  ② 붙이기: 오른쪽으로 가장 가까운 것 = 표 / 상위 박스 / 이미 붙은 삼각형 (여러 개면 왼쪽으로 줄지어 붙음)
  ③ 읽기: 삼각형 안 선을 글자 사전으로 끼워 맞춤 (안 맞으면 검수 → 5단계 OCR)
"""

import math
from collections import defaultdict
from dataclasses import dataclass

from bom.extract_lines import Line
from bom.geometry import TOUCH_TOL, find_slot, is_horizontal
from bom.glyphs import Glyph, match_glyphs
from bom.parent_cells import ParentArea
from bom.split_cells import BomGrid

SIDE_RATIO = (1.8, 4.0)  # 변 ÷ 글자 높이 범위 (샘플 2.4, 테스트 2.16~3.58). 글자 '4'·'A'의 삼각형 부분은 이보다 작음
SIDE_TOL = 0.3           # 정삼각형: 세 변 길이 차이 허용 (실제 ≤ 0.1)
ATTACH_GAP = 1.0         # 붙이기: 오른쪽 대상과 간격 ≤ 글자 높이 × 이 값 (붙은 것 -0.5~5.8, 떨어진 것 31.6 이상)
ATTACH_OVERLAP = 0.1     # 붙이기: 겹침 허용 = 글자 높이 × 이 값 (22000 NO 23 삼각형끼리 0.6 겹침)

OK, REVIEW = "정상", "검수"


@dataclass(frozen=True)
class Triangle:
    lines: tuple[Line, Line, Line]
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    side: float

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2


@dataclass(frozen=True)
class RevMark:
    """행(또는 상위 행)에 붙은 리비전 삼각형 하나"""
    box_side: Line | None   # None = BOM 표 행, 아니면 상위 박스 (ParentLink.connector.box_side)
    row: int                # 표 행 번호 (BomGrid) 또는 상위 행 번호 (ParentLink.box_row)
    triangle: Triangle
    text: str               # 안 숫자 (사전으로 읽음, 검수면 읽은 데까지)
    status: str             # 정상 / 검수


# ── ① 찾기 ─────────────────────────────────────────────────────────────
def _true_length(ln: Line) -> float:
    """실제 길이 (피타고라스). geometry.length는 가로+세로 변화량이라 비스듬한 변에 못 씀"""
    return math.hypot(ln.x2 - ln.x1, ln.y2 - ln.y1)


def _key(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y)


def _other_end(ln: Line, p: tuple[float, float]) -> tuple[float, float] | None:
    """p에 닿은 끝의 반대쪽 끝 (p에 안 닿으면 None)"""
    if abs(ln.x1 - p[0]) <= TOUCH_TOL and abs(ln.y1 - p[1]) <= TOUCH_TOL:
        return ln.x2, ln.y2
    if abs(ln.x2 - p[0]) <= TOUCH_TOL and abs(ln.y2 - p[1]) <= TOUCH_TOL:
        return ln.x1, ln.y1
    return None


def find_triangles(lines: list[Line], height: float) -> list[Triangle]:
    """밑변(가로선) 양 끝에 닿은 두 선이 한 꼭짓점에서 만나고, 세 변 길이가 같은 것"""
    lo, hi = height * SIDE_RATIO[0], height * SIDE_RATIO[1]
    cands = [ln for ln in lines if lo <= _true_length(ln) <= hi]
    by_end: dict[tuple[int, int], list[Line]] = defaultdict(list)   # 끝점 격자 → 선 (화살촉 찾기와 같은 방식)
    for ln in cands:
        by_end[_key(ln.x1, ln.y1)].append(ln)
        by_end[_key(ln.x2, ln.y2)].append(ln)

    def touching(p):
        kx, ky = _key(*p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for ln in by_end.get((kx + dx, ky + dy), []):
                    apex = _other_end(ln, p)
                    if apex is not None:
                        yield ln, apex

    found: dict[frozenset, Triangle] = {}
    for base in cands:
        if not is_horizontal(base):
            continue
        a, b = (base.x1, base.y1), (base.x2, base.y2)
        for left, apex in touching(a):
            if left is base:
                continue
            for right, apex2 in touching(b):
                if right is base or right is left:
                    continue
                if abs(apex[0] - apex2[0]) > TOUCH_TOL or abs(apex[1] - apex2[1]) > TOUCH_TOL:
                    continue
                sides = [_true_length(base), _true_length(left), _true_length(right)]
                if max(sides) - min(sides) > SIDE_TOL:
                    continue
                key = frozenset(map(id, (base, left, right)))
                xs = [base.x1, base.x2, apex[0]]
                ys = [base.y1, base.y2, apex[1]]
                found[key] = Triangle((base, left, right), min(xs), max(xs), min(ys), max(ys), sum(sides) / 3)
    return list(found.values())


# ── ② 붙이기 ───────────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Target:
    box_side: Line | None
    left_x: float
    row_ys: list[float]


def attach_triangles(triangles: list[Triangle], grid: BomGrid, areas: list[ParentArea],
                     height: float) -> list[tuple[Line | None, int, Triangle]]:
    """오른쪽 삼각형부터: 오른쪽으로 가장 가까운 표·상위 박스·이미 붙은 삼각형에 붙인다"""
    if len(grid.col_xs) < 2 or len(grid.row_ys) < 2:
        return []   # 칸 나누기 실패 (case_0475)
    targets = [_Target(None, grid.col_xs[0], grid.row_ys)] + [_Target(a.box_side, a.col_xs[0], a.row_ys) for a in areas]
    max_gap, min_gap = height * ATTACH_GAP, -height * ATTACH_OVERLAP
    attached: list[tuple[Line | None, int, Triangle]] = []
    for tri in sorted(triangles, key=lambda t: -t.x_max):
        best = None   # (간격, box_side, 행)
        for t in targets:
            gap = t.left_x - tri.x_max
            row = find_slot(tri.y_center, t.row_ys)
            # 행은 가운데 y로 (28440 상위 박스 삼각형은 행보다 커서 위로 2.5 삐져나옴)
            if min_gap <= gap <= max_gap and row is not None:
                if best is None or gap < best[0]:
                    best = (gap, t.box_side, row)
        for box_side, row, done in attached:
            gap = done.x_min - tri.x_max
            if min_gap <= gap <= max_gap and abs(done.y_center - tri.y_center) <= done.side * 0.5:
                if best is None or gap < best[0]:
                    best = (gap, box_side, row)
        if best is not None:
            attached.append((best[1], best[2], tri))
    return attached


# ── ③ 읽기 ─────────────────────────────────────────────────────────────
def read_triangle(tri: Triangle, lines: list[Line], glyphs: list[Glyph]) -> tuple[str, str]:
    """삼각형 안쪽 선(삼각형 세 변 제외)을 사전으로 읽는다. 크기는 안 숫자의 높이로 맞춤. (글자, 상태)"""
    own = set(map(id, tri.lines))
    inner = [ln for ln in lines
             if id(ln) not in own
             and tri.x_min < min(ln.x1, ln.x2) and max(ln.x1, ln.x2) < tri.x_max
             and tri.y_min < min(ln.y1, ln.y2) and max(ln.y1, ln.y2) < tri.y_max]
    if not inner:
        return "", REVIEW
    top = min(min(ln.y1, ln.y2) for ln in inner)
    bottom = max(max(ln.y1, ln.y2) for ln in inner)
    result = match_glyphs(inner, glyphs, (top + bottom) / 2, bottom - top)
    status = OK if result.chars and not result.leftover else REVIEW
    return result.text, status


# ── 전체 ───────────────────────────────────────────────────────────────
def find_revisions(grid: BomGrid, areas: list[ParentArea], lines: list[Line],
                   glyphs: list[Glyph], height: float) -> list[RevMark]:
    marks = []
    for box_side, row, tri in attach_triangles(find_triangles(lines, height), grid, areas, height):
        text, status = read_triangle(tri, lines, glyphs)
        marks.append(RevMark(box_side, row, tri, text, status))
    return marks


def rev_text(marks: list[RevMark]) -> str:
    """한 행의 삼각형들 → json 형식 "03,02" (숫자 내림차순, docs/12)"""
    return ",".join(sorted((m.text for m in marks), reverse=True))

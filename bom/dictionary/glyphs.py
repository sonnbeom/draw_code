"""4-1: 글자 사전과 끼워 맞추기 (docs/설계/06_취소선.md "짧은 취소선 판정").

같은 폰트라 같은 글자는 선 모양이 같다 (크기만 다름).
  - 사전 만들기 (샘플): 칸의 선을 틈으로 글자별로 자르고 json 글자를 붙여 모양을 모은다
  - 끼워 맞추기 (도면): 칸에 사전 글자를 왼쪽부터 대 보고, 맞으면 그 선들을 뺀다.
    끝까지 남는 선이 취소선 후보 (판정은 bom/strikes/rules.py)

좌표는 "글자 왼쪽 x, 글자 줄 가운데 y"를 0으로 놓고 글자 높이로 나눠 크기를 맞춘다.
"""

import json
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from bom.pdf_lines.extract_lines import Line
from bom.pdf_lines.geometry import TOUCH_TOL
from bom.cells.split_cells import BomGrid

GAP_TOL = 0.5           # 사전 만들 때: 글자 사이 x 틈이 이보다 작으면 같은 글자 (샘플 틈 약 1.5)
LINE_GAP_RATIO = 0.15   # 두 줄 칸: 위아래 선 사이 y 틈이 글자 높이 x 이 값보다 크면 다른 줄 (22000 수량 두 줄 틈 0.23)
DASH_LEN = (0.5, 1.5)   # '-' 길이 범위 (글자 높이 대비). 도면마다 길이가 달라 사전 대신 규칙 (샘플 1.06, 88400 0.97)
CENTER_SHIFT = -0.076   # 한 줄 칸의 글자 줄 가운데 = 행 가운데 + 글자 높이 x 이 값 (테스트 -0.7/9.2, 샘플 -0.5/6.6)
MATCH_TOL = 0.08        # 끼워 맞추기: 끝점 거리 허용 = 글자 높이 x 이 값 (9.2 → 0.74)
MIN_DICT_COUNT = 2      # 사전에 넣는 최소 등장 횟수 (한 번만 나온 모양은 잡음일 수 있어 뺌)
ROUND = 2               # 정규화 좌표 반올림 자릿수 (모양 묶기용)

DICT_PATH = Path(__file__).with_name("glyph_dict.json")

Point = tuple[float, float]
Segment = tuple[Point, Point]   # 정규화된 선분 (작은 점이 앞)
Shape = tuple[Segment, ...]     # 글자 하나의 모양 = 선분 목록 (정렬됨)


@dataclass(frozen=True)
class Glyph:
    """사전 글자 하나 (같은 글자라도 모양 변형이 여러 개일 수 있음)"""
    char: str
    shape: Shape
    width: float   # 글자 폭 / 글자 높이
    count: int     # 샘플에서 나온 횟수


@dataclass
class MatchResult:
    """끼워 맞추기 결과"""
    chars: list[tuple[str, float, float]] = field(default_factory=list)  # (글자, 왼쪽 x, 오른쪽 x)
    used: list[list[Line]] = field(default_factory=list)                  # 글자마다 쓰인 선
    leftover: list[Line] = field(default_factory=list)                    # 어떤 글자에도 안 쓰인 선

    @property
    def text(self) -> str:
        return "".join(ch for ch, _, _ in self.chars)


# ── 칸 → 선 ────────────────────────────────────────────────────────────
def _on_grid(ln: Line, grid: BomGrid) -> bool:
    """행·열 경계선인가 (가로선이 행 경계 높이, 세로선이 열 경계 x)"""
    if abs(ln.y1 - ln.y2) <= TOUCH_TOL:
        return any(abs((ln.y1 + ln.y2) / 2 - y) <= TOUCH_TOL for y in grid.row_ys)
    if abs(ln.x1 - ln.x2) <= TOUCH_TOL:
        return any(abs((ln.x1 + ln.x2) / 2 - x) <= TOUCH_TOL for x in grid.col_xs)
    return False


def strokes_by_cell(grid: BomGrid, lines: list[Line]) -> dict[tuple[int, int], list[Line]]:
    """표 안에서 행·열 경계선이 아닌 선(글자 획 + 취소선)을 칸별로 나눈다. 키 = (행, 칸의 시작 열 Cell.col)
    BOM 묶음(match.lines)으로 거르지 않는 이유: 칸 경계에 닿은 긴 취소선은 묶음에 들어가 버림 (88300 품명)"""
    if len(grid.col_xs) < 2 or len(grid.row_ys) < 2:
        return {}                                  # 칸을 못 나눈 표 (샘플 결함 case_0475: 열 경계 없음)
    cell_of = {}                                   # (행, 열) → 그 열을 덮는 칸의 시작 열 (병합 칸 처리)
    for cell in grid.cells:
        for col in range(cell.col, cell.col + cell.col_span):
            cell_of[(cell.row, col)] = cell.col
    x_min, x_max = grid.col_xs[0], grid.col_xs[-1]
    y_min, y_max = grid.row_ys[0], grid.row_ys[-1]
    result: dict[tuple[int, int], list[Line]] = {}
    for ln in lines:
        if not (x_min <= min(ln.x1, ln.x2) and max(ln.x1, ln.x2) <= x_max
                and y_min <= min(ln.y1, ln.y2) and max(ln.y1, ln.y2) <= y_max):
            continue                               # 두 끝이 다 표 안인 선만 (표를 지나가는 도면 테두리선 등 제외)
        if _on_grid(ln, grid):
            continue
        mx, my = (ln.x1 + ln.x2) / 2, (ln.y1 + ln.y2) / 2
        row = bisect_right(grid.row_ys, my) - 1    # find_slot과 같지만 경계 위도 허용 (글자 획은 경계에 안 걸림)
        col = bisect_right(grid.col_xs, mx) - 1
        key = (row, cell_of.get((row, col), col))
        result.setdefault(key, []).append(ln)
    return result


def _y_range(strokes: list[Line]) -> tuple[float, float]:
    return min(min(s.y1, s.y2) for s in strokes), max(max(s.y1, s.y2) for s in strokes)


def split_text_lines(strokes: list[Line], height: float) -> list[list[Line]]:
    """두 줄 칸을 위 → 아래 줄로 나눈다. 선의 y 범위가 이어지거나 틈이 작으면 같은 줄"""
    ordered = sorted(strokes, key=lambda s: min(s.y1, s.y2))
    text_lines: list[list[Line]] = []
    bottom = None
    for s in ordered:
        top_y = min(s.y1, s.y2)
        if text_lines and top_y - bottom <= height * LINE_GAP_RATIO:
            text_lines[-1].append(s)
            bottom = max(bottom, max(s.y1, s.y2))
        else:
            text_lines.append([s])
            bottom = max(s.y1, s.y2)
    # 납작한 줄('-'나 가로선만)은 혼자 한 줄이 아님 → 이웃 줄에 붙인다 (88361 지워진 '-': '-'와 취소선 틈 2.85)
    merged: list[list[Line]] = []
    for text_line in text_lines:
        top, bottom = _y_range(text_line)
        if merged and (bottom - top < height * 0.5 or _flat(merged[-1], height)):
            merged[-1].extend(text_line)
        else:
            merged.append(text_line)
    return merged


def _flat(text_line: list[Line], height: float) -> bool:
    top, bottom = _y_range(text_line)
    return bottom - top < height * 0.5


def split_by_gap(strokes: list[Line]) -> list[list[Line]]:
    """사전 만들 때만: x 틈(GAP_TOL)으로 글자 자르기. 샘플은 글자 사이 틈이 있어 이걸로 충분"""
    ordered = sorted(strokes, key=lambda s: min(s.x1, s.x2))
    glyphs: list[list[Line]] = []
    right = None
    for s in ordered:
        left = min(s.x1, s.x2)
        if glyphs and left - right < GAP_TOL:
            glyphs[-1].append(s)
            right = max(right, max(s.x1, s.x2))
        else:
            glyphs.append([s])
            right = max(s.x1, s.x2)
    return glyphs


def text_height(cell_strokes: dict[tuple[int, int], list[Line]]) -> float:
    """도면의 글자 높이 = 틈으로 자른 글자 높이의 최빈값 (숫자·대문자 높이. 테스트 9.2, 샘플 6.6)"""
    heights = Counter()
    for strokes in cell_strokes.values():
        for glyph in split_by_gap(strokes):
            top, bottom = _y_range(glyph)
            if bottom - top > 1.0:                 # '-' 같은 납작한 글자는 빼고
                heights[round(bottom - top, 1)] += 1
    return heights.most_common(1)[0][0] if heights else 0.0


def line_center(text_line: list[Line], height: float, row_center: float, single: bool) -> float:
    """글자 줄 가운데 y. 한 줄 칸은 행 가운데 기준 ('-'만 있어도 됨), 두 줄 칸은 그 줄 글자들로"""
    if single:
        return row_center + height * CENTER_SHIFT
    centers = []
    for glyph in split_by_gap(text_line):
        top, bottom = _y_range(glyph)
        if abs((bottom - top) - height) <= height * 0.1:   # 글자 높이와 같은 글자만 (쉼표·괄호 제외)
            centers.append((top + bottom) / 2)
    if centers:
        centers.sort()
        return centers[len(centers) // 2]
    top, bottom = _y_range(text_line)
    return (top + bottom) / 2


# ── 모양 ──────────────────────────────────────────────────────────────
def shape_of(strokes: list[Line], x_left: float, y_center: float, height: float) -> Shape:
    """선 목록 → 정규화 모양 (기준점 빼고 글자 높이로 나눔, 반올림, 정렬)"""
    segments = []
    for s in strokes:
        p1 = (round((s.x1 - x_left) / height, ROUND), round((s.y1 - y_center) / height, ROUND))
        p2 = (round((s.x2 - x_left) / height, ROUND), round((s.y2 - y_center) / height, ROUND))
        segments.append((min(p1, p2), max(p1, p2)))
    return tuple(sorted(segments))


# ── 사전 저장·불러오기 ───────────────────────────────────────────────────
def save_glyph_dict(glyphs: list[Glyph], path: Path = DICT_PATH) -> None:
    data = [{"char": g.char, "shape": g.shape, "width": g.width, "count": g.count} for g in glyphs]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_glyph_dict(path: Path = DICT_PATH) -> list[Glyph]:
    """선분이 많은 글자부터 (끼워 맞출 때 'E'가 'F'보다 먼저 시도되도록)"""
    data = json.loads(path.read_text(encoding="utf-8"))
    glyphs = [Glyph(d["char"], tuple(tuple(tuple(p) for p in seg) for seg in d["shape"]), d["width"], d["count"])
              for d in data]
    return sorted(glyphs, key=lambda g: (-len(g.shape), -g.count))


# ── 끼워 맞추기 ─────────────────────────────────────────────────────────
def _near(a: Point, b: Point, tol: float) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _place(glyph: Glyph, x0: float, y_center: float, height: float, remaining: list[Line]) -> list[Line] | None:
    """글자를 (x0, y_center)에 놓았을 때 사전 선분마다 같은 위치의 선이 있으면 그 선들, 하나라도 없으면 None"""
    tol = height * MATCH_TOL
    used: list[Line] = []
    for (ax, ay), (bx, by) in glyph.shape:
        a = (x0 + ax * height, y_center + ay * height)
        b = (x0 + bx * height, y_center + by * height)
        hit = None
        for s in remaining:
            if any(s is u for u in used):
                continue
            p, q = (s.x1, s.y1), (s.x2, s.y2)
            if (_near(p, a, tol) and _near(q, b, tol)) or (_near(p, b, tol) and _near(q, a, tol)):
                hit = s
                break
        if hit is None:
            return None
        used.append(hit)
    return used


def _place_dash(window: list[Line], x0: float, y_center: float, height: float) -> tuple[Glyph, float, list[Line]] | None:
    """사전 글자가 하나도 안 맞을 때: x0에서 시작하는 줄 가운데 높이의 가로선 하나 = '-'"""
    tol = height * MATCH_TOL
    for s in window:
        if (abs(min(s.x1, s.x2) - x0) <= tol and abs(s.y1 - s.y2) <= tol
                and abs((s.y1 + s.y2) / 2 - y_center) <= tol
                and DASH_LEN[0] * height <= abs(s.x2 - s.x1) <= DASH_LEN[1] * height):
            width = abs(s.x2 - s.x1) / height
            return Glyph("-", (), width, 0), x0, [s]
    return None


def match_glyphs(strokes: list[Line], glyphs: list[Glyph], y_center: float, height: float) -> MatchResult:
    """한 줄의 선에 사전 글자를 왼쪽부터 끼워 맞춘다.
    시작 x 후보(남은 선의 왼쪽 끝들)를 왼쪽부터 대 보고, 처음 맞는 곳에서 선분 많은 글자부터 시도.
    글자끼리는 겹치지 않으므로 다음 글자는 앞 글자 오른쪽 끝 이후에서만 시작 (취소선은 앞 글자 왼쪽에서 시작해 남음)"""
    result = MatchResult()
    remaining = list(strokes)
    tol = height * MATCH_TOL
    max_width = max(g.width for g in glyphs) * height
    last_right = float("-inf")
    while remaining:
        starts = sorted({min(s.x1, s.x2) for s in remaining if min(s.x1, s.x2) >= last_right - tol})
        placed = None
        for x0 in starts:
            # 속도: 이 시작점에서 가장 넓은 글자 폭 안에 들어가는 선만 후보로 (칸 전체 선을 매번 뒤지지 않게)
            window = [s for s in remaining
                      if min(s.x1, s.x2) >= x0 - tol and max(s.x1, s.x2) <= x0 + max_width + tol]
            for glyph in glyphs:
                right_limit = x0 + glyph.width * height + tol
                local = [s for s in window if max(s.x1, s.x2) <= right_limit]
                if len(local) < len(glyph.shape):      # 선 개수가 모자라면 볼 필요 없음
                    continue
                used = _place(glyph, x0, y_center, height, local)
                if used:
                    placed = (glyph, x0, used)
                    break
            if placed is None:
                placed = _place_dash(window, x0, y_center, height)
            if placed:
                break
        if placed is None:
            break
        glyph, x0, used = placed
        right = x0 + glyph.width * height
        result.chars.append((glyph.char, x0, right))
        result.used.append(used)
        used_ids = {id(u) for u in used}
        remaining = [s for s in remaining if id(s) not in used_ids]
        last_right = right
    result.leftover = remaining
    return result

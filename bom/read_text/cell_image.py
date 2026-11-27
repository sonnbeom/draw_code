"""5단계 OCR 입력: 칸(또는 칸 안 한 줄)의 획만 다시 그린다 (docs/설계/19_OCR_전략.md, Claude 작성).

  - 칸 모드(먼저 시도): 칸 전체를 한 그림으로 → OCR 검출이 줄을 찾음
  - 줄 모드(칸 모드가 부족하면): 칸 안 한 줄씩 (줄 번호 = 4-1 CellMark.line)
  - 취소선은 빼고 그림: 4-1이 찾은 짧은 취소선(CellMark.strikes) + 표 폭 취소선(grid.struck_lines)
    → 4-3 "선 지우기"를 따로 두지 않고 여기에 합침
  - 크기: 글자 높이 → TEXT_PX (도면마다 글자 크기가 달라도 같은 크기로 = 정규화), 흰 바탕에 검은 선
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np

from bom.pdf_lines.extract_lines import Line
from bom.pdf_lines.geometry import TOUCH_TOL, is_horizontal
from bom.dictionary.glyphs import split_text_lines, strokes_by_cell
from bom.cells.split_cells import BomGrid

TEXT_PX = 32     # 글자 높이를 그림에서 몇 px로
PAD_Y = 8        # 위아래 여백 → 한 줄 그림 높이 32 + 8×2 = 48 (RapidOCR 인식 모델 입력 높이)
PAD_X = 8        # 좌우 여백
THICKNESS = 2    # 선 굵기 px. 3 → 2 (2026-11-27): 0001~0600 품명 99.6% → 100.0% (D→O 14·5→S 12 사라짐), docs/OCR/24


@dataclass(frozen=True)
class LineImage:
    """줄 모드: OCR에 넣을 한 줄 그림"""
    row: int               # 표 행 (0 = 머리글)
    col: int               # 칸의 시작 열 (Cell.col)
    line: int              # 칸 안 몇 번째 줄 (0 = 위) = CellMark.line
    strokes: list[Line]    # 그린 획 (취소선 뺀 것)
    image: np.ndarray      # BGR uint8


@dataclass(frozen=True)
class CellImage:
    """칸 모드: OCR에 넣을 칸 하나 그림"""
    row: int
    col: int
    line_ys: dict[int, float]   # 우리 줄 번호(CellMark.line) → 그림 속 그 줄의 가운데 y px (OCR 줄과 짝지을 때)
    strokes: list[Line]
    image: np.ndarray


def _draw(strokes: list[Line], height: float):
    """획 목록 → (그림, 좌표 변환 함수). 왼쪽 끝이 PAD_X, 세로 가운데가 그림 가운데에 오게"""
    scale = TEXT_PX / height
    xs = [x for s in strokes for x in (s.x1, s.x2)]
    ys = [y for s in strokes for y in (s.y1, s.y2)]
    x0, y_mid = min(xs), (min(ys) + max(ys)) / 2
    width = math.ceil((max(xs) - x0) * scale) + 2 * PAD_X
    img_h = max(TEXT_PX, math.ceil((max(ys) - min(ys)) * scale)) + 2 * PAD_Y   # 여러 줄·큰 획도 안 잘리게

    def px(x: float, y: float) -> tuple[int, int]:
        # PDF 좌표는 y가 아래로 커짐 = 그림 좌표와 같은 방향 → 뒤집을 필요 없음
        return round((x - x0) * scale) + PAD_X, round((y - y_mid) * scale + img_h / 2)

    img = np.full((img_h, width, 3), 255, dtype=np.uint8)
    for s in strokes:
        cv2.line(img, px(s.x1, s.y1), px(s.x2, s.y2), (0, 0, 0), THICKNESS, cv2.LINE_AA)
    return img, px


def render_strokes(strokes: list[Line], height: float) -> np.ndarray:
    return _draw(strokes, height)[0]


def _cells(grid: BomGrid, lines: list[Line], height: float, remove: list[Line]):
    """칸마다 (행, 열, [(줄 번호, 남은 획)]). 줄 나누기는 취소선을 빼기 '전'에 → 줄 번호가 4-1과 같음"""
    removed = set(map(id, remove)) | set(map(id, grid.struck_lines))
    for (row, col), strokes in sorted(strokes_by_cell(grid, lines).items()):
        text_lines = []
        for line_no, text_line in enumerate(split_text_lines(strokes, height)):
            kept = [s for s in text_line if id(s) not in removed]
            if kept:   # 취소선만 있던 줄은 그릴 게 없음
                text_lines.append((line_no, kept))
        if text_lines:
            yield row, col, text_lines


MULTI_LINE = 1.6   # 획 덩어리 높이가 글자 높이 × 이 값보다 크면 여러 줄일 수 있음 → 자를 곳을 찾음
EDGE = 0.8         # 자를 곳은 덩어리 위·아래 끝에서 글자 높이 × 이 값 안쪽에서만 찾음 (한 줄 안에서 자르지 않게)
BIN = 0.1          # 높이별 획 수를 셀 칸 크기 (글자 높이 × 이 값)


def _touch(a: Line, b: Line) -> bool:
    """두 획이 끝점을 공유하는가"""
    return any(abs(p[0] - q[0]) <= TOUCH_TOL and abs(p[1] - q[1]) <= TOUCH_TOL
               for p in ((a.x1, a.y1), (a.x2, a.y2)) for q in ((b.x1, b.y1), (b.x2, b.y2)))


def _boxes_meet(a: Line, b: Line) -> bool:
    """두 획을 감싸는 네모가 겹치거나 닿는가 (TOUCH_TOL 여유)"""
    return (min(a.x1, a.x2) - TOUCH_TOL <= max(b.x1, b.x2) and min(b.x1, b.x2) - TOUCH_TOL <= max(a.x1, a.x2)
            and min(a.y1, a.y2) - TOUCH_TOL <= max(b.y1, b.y2) and min(b.y1, b.y2) - TOUCH_TOL <= max(a.y1, a.y2))


UNDERSCORE_TOP = 0.25   # 아랫줄 글자 꼭대기 + 글자 높이 × 이 값보다 위에 있는 홀로 가로 획은 윗줄의 '_'
TAIL_MAX = 0.3         # 윗줄 획에 닿아 윗줄로 따라 올라가는 획은 자른 높이 + 글자 높이 × 이 값 안에서 끝나야 함
                       # (쉼표 꼬리 0.21까지 내려옴. 아랫줄 글자 획은 0.4 넘게 내려감: 'M' 1.0, '2' 첫 조각 0.44)


def _lift_underscores(upper: list[Line], lower: list[Line], height: float) -> tuple[list[Line], list[Line]]:
    """아랫줄에 간 홀로 가로 획 중 아랫줄 글자 꼭대기 근처(위)에 있는 것 → 윗줄 바닥의 '_'로 보고 윗줄로
    홀로 = 다른 어떤 획과도 네모가 안 겹침 ('+'의 가로 획은 세로 획과 겹쳐 홀로가 아님)
    아랫줄의 '-'(가운데, +0.5)와 '_'(바닥, +1.0)는 꼭대기에서 멀어 안 움직임"""
    strokes = upper + lower
    alone = {id(s) for s in lower
             if is_horizontal(s) and not any(o is not s and _boxes_meet(s, o) for o in strokes)}
    body = [s for s in lower if id(s) not in alone]
    if not body:
        return upper, lower
    limit = min(min(s.y1, s.y2) for s in body) + height * UNDERSCORE_TOP
    lift = [s for s in lower if id(s) in alone and (s.y1 + s.y2) / 2 < limit]
    return upper + lift, [s for s in lower if s not in lift]


def split_by_valley(strokes: list[Line], height: float) -> list[list[Line]]:
    """줄 모드 줄 나누기: 높이마다 걸친 획 수를 세서 가장 적은 높이(골짜기)에서 자른다. 세 줄이면 두 번
    split_text_lines(틈이 있어야 자름)와 달리 윗줄 , ( ) 가 아랫줄까지 내려와 틈이 없어도 자름 (case_0601 품명)
    획은 위 끝이 자른 높이보다 위면 윗줄, 아니면 아랫줄
    (가운데 y로 나누면 윗줄 쉼표의 꼬리가 아랫줄로 가서 쉼표 → '.', 아랫줄에 ':' 부스러기. case_0603 행4)"""
    top = min(min(s.y1, s.y2) for s in strokes)
    bottom = max(max(s.y1, s.y2) for s in strokes)
    if bottom - top < height * MULTI_LINE:
        return [strokes]
    step = height * BIN
    best_y, best_count = None, None
    y = top + height * EDGE
    while y <= bottom - height * EDGE:
        count = sum(min(s.y1, s.y2) <= y <= max(s.y1, s.y2) for s in strokes)
        if best_count is None or count < best_count:
            best_y, best_count = y, count
        y += step
    if best_y is None:
        return [strokes]
    upper = [s for s in strokes if min(s.y1, s.y2) < best_y]
    lower = [s for s in strokes if min(s.y1, s.y2) >= best_y]
    # 윗줄 획과 끝점이 닿은 아랫줄 획은 같은 글자 → 윗줄로 (쉼표 = 세로 획 + 꼬리 1.07, 꼬리 위 끝이 자른 높이와 같음. case_0612 행11)
    # 자른 높이 바로 밑에서 끝나는 획만: 줄 간격이 좁으면 아랫줄 'M'·'2' 꼭대기가 쉼표 꼬리에 닿아 글자째 끌려옴. 88500 행8~10
    moved = True
    while moved:
        moved = False
        for s in list(lower):
            if max(s.y1, s.y2) < best_y + height * TAIL_MAX and any(_touch(s, u) for u in upper):
                lower.remove(s)
                upper.append(s)
                moved = True
    # 윗줄 바닥의 '_'는 줄 간격이 좁으면 자른 높이 아래에 있어 아랫줄로 감 (88500 행14 '2_L') → 되돌림
    if upper and lower:
        upper, lower = _lift_underscores(upper, lower, height)
    if not upper or not lower:
        return [strokes]
    return split_by_valley(upper, height) + split_by_valley(lower, height)


def line_images(grid: BomGrid, lines: list[Line], height: float, remove: list[Line]) -> list[LineImage]:
    """줄 모드: 표의 모든 칸(머리글 포함)을 줄 단위 그림으로. remove = 뺄 선 (4-1 CellMark.strikes를 모은 것)
    줄 나누기는 취소선을 뺀 획을 골짜기로 (split_by_valley). 줄 번호는 위 → 아래 순서
    (4-1 CellMark.line과 맞추는 건 줄 모드로 정한 뒤 — 지금 비교는 취소 칸을 빼고 함)"""
    result = []
    for row, col, text_lines in _cells(grid, lines, height, remove):
        kept = [s for _, part in text_lines for s in part]
        for line_no, part in enumerate(split_by_valley(kept, height)):
            result.append(LineImage(row, col, line_no, part, render_strokes(part, height)))
    return result


def cell_images(grid: BomGrid, lines: list[Line], height: float, remove: list[Line]) -> list[CellImage]:
    """칸 모드: 칸 하나 = 그림 하나 (여러 줄이면 여러 줄 그대로)"""
    result = []
    for row, col, text_lines in _cells(grid, lines, height, remove):
        strokes = [s for _, kept in text_lines for s in kept]
        img, px = _draw(strokes, height)
        line_ys = {}
        for line_no, kept in text_lines:
            top = min(min(s.y1, s.y2) for s in kept)
            bottom = max(max(s.y1, s.y2) for s in kept)
            line_ys[line_no] = px(0, (top + bottom) / 2)[1]
        result.append(CellImage(row, col, line_ys, strokes, img))
    return result

"""4단계 4-1: 칸별 취소 판정 (docs/설계/06_취소선.md).

칸 안의 줄마다 정상 / 취소 / 검수 를 정한다.
  - 짧은 칸(I/NO, 수량): 사전 글자를 끼워 맞추고 남는 가로선으로 판정
  - 나머지 칸(품번, 품명 등): 긴 취소선만 본다 (기존 is_struck)
"""

from dataclasses import dataclass

from bom.extract_lines import Line
from bom.geometry import TOUCH_TOL, find_slot, is_horizontal, length
from bom.glyphs import Glyph, MatchResult, line_center, match_glyphs, split_text_lines, strokes_by_cell, text_height
from bom.split_cells import BomGrid, is_struck
from bom.table_candidates import MIN_TABLE_LINE

OK, STRUCK, REVIEW = "정상", "취소", "검수"

@dataclass(frozen=True)
class CellMark:
    """칸 안 한 줄의 판정 결과"""
    row: int             # 행 (1부터, 0 = 머리글)
    col: int             # 칸의 시작 열 (Cell.col)
    line: int            # 칸 안 몇 번째 줄 (0 = 위)
    status: str          # 정상 / 취소 / 검수
    text: str            # 사전으로 읽은 글자 (짧은 칸만, 나머지는 "")
    strikes: list[Line]  # 찾은 취소선 (4-3에서 지울 선)

def _is_long_strike(s: Line, strokes: list[Line]) -> bool:
    """긴 취소선: 글자 획보다 긴(14 이상) 가로선을 글자 획이 위아래로 관통 (품번·품명, 기존 is_struck)"""
    return is_horizontal(s) and length(s) >= MIN_TABLE_LINE and is_struck(s, strokes)

def _crosses_glyph(s: Line, result: MatchResult, y_center: float, height: float) -> bool:
    """짧은 취소선: 남는 가로선이 줄 가운데 근처 높이에서, 읽은 글자의 x 범위와 겹친다"""
    if not is_horizontal(s):
        return False
    near_middle = abs((s.y1 + s.y2) / 2 - y_center) <= height * 0.5
    x_min, x_max = min(s.x1, s.x2), max(s.x1, s.x2)
    over_glyph = any(x_min < right - TOUCH_TOL and x_max > left + TOUCH_TOL
                     for _, left, right in result.chars)
    return near_middle and over_glyph

def judge_short_line(strokes: list[Line], glyphs: list[Glyph],
                     y_center: float, height: float) -> tuple[str, str, list[Line]]:
    """짧은 칸 한 줄: 사전 끼워 맞추기 → 남는 선으로 판정. (상태, 읽은 글자, 취소선)"""
    result = match_glyphs(strokes, glyphs, y_center, height)
    strikes = [s for s in result.leftover
               if _is_long_strike(s, strokes) or _crosses_glyph(s, result, y_center, height)]
    if strikes:
        return STRUCK, result.text, strikes   # 글자 위를 지나는 남는 선 = 취소
    if result.leftover:
        return REVIEW, result.text, []        # 남았는데 취소선은 아님 = 사전에 없는 모양
    return OK, result.text, []

def mark_cells(grid: BomGrid, lines: list[Line], glyphs: list[Glyph],
               short_cols: set[int]) -> list[CellMark]:
    """표의 모든 칸을 줄 단위로 판정. short_cols = 사전으로 볼 열 (I/NO, 수량)"""
    by_cell = strokes_by_cell(grid, lines)   # 칸 → 그 칸의 선 (글자 획 + 취소선)
    height = text_height(by_cell)            # 도면 글자 높이 (테스트 9.2)
    # 표 폭 전체 취소선(샘플 방식)은 split_cells가 이미 판정함 → 그 행은 통째로 취소
    full_struck_rows = {find_slot((s.y1 + s.y2) / 2, grid.row_ys) for s in grid.struck_lines}
    marks = []
    for (row, col), strokes in sorted(by_cell.items()):
        if row == 0:
            continue                         # 머리글은 안 봄
        if row in full_struck_rows:
            marks.append(CellMark(row, col, 0, STRUCK, "", []))
            continue
        row_center = (grid.row_ys[row] + grid.row_ys[row + 1]) / 2
        text_lines = split_text_lines(strokes, height)   # 두 줄 칸은 줄마다 (22000: 지운 2 + 새 1)
        for line_no, text_line in enumerate(text_lines):
            if col in short_cols:
                y_center = line_center(text_line, height, row_center, single=len(text_lines) == 1)
                status, text, strikes = judge_short_line(text_line, glyphs, y_center, height)
            else:
                strikes = [s for s in text_line if _is_long_strike(s, text_line)]
                status, text = (STRUCK if strikes else OK), ""
            marks.append(CellMark(row, col, line_no, status, text, strikes))
    return marks

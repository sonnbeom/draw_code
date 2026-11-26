from dataclasses import dataclass

from bom.pdf_lines.extract_lines import Line
from bom.pdf_lines.geometry import TOUCH_TOL, is_vertical, length
from bom.find_table.select_bom import BomMatch, full_width_lines
from bom.find_table.table_candidates import MIN_TABLE_LINE

@dataclass(frozen=True)
class Cell:
    """칸 하나. 병합된 칸은 col_span이 2 이상"""
    row: int        # 행 번호 (0 = 머리글, 1부터 데이터 행)
    col: int        # 열 번호 (왼쪽부터 0)
    col_span: int   # 가로로 합쳐진 열 수 (보통 1)
    x_min: float
    x_max: float
    y_min: float
    y_max: float

@dataclass(frozen=True)
class BomGrid:
    """칸 나누기 결과"""
    row_ys: list[float]       # 행 경계 y (위 → 아래). 행 수 = len(row_ys) - 1
    col_xs: list[float]       # 열 경계 x (왼쪽 → 오른쪽). 열 수 = len(col_xs) - 1
    struck_lines: list[Line]  # 취소선으로 판정해 행 경계에서 뺀 꽉 찬 가로선
    cells: list[Cell]

def _mid_x(line: Line) -> float:
    return (line.x1 + line.x2) / 2

def _mid_y(line: Line) -> float:
    return (line.y1 + line.y2) / 2

def _merge_close(values: list[float]) -> list[float]:
    """정렬하고 일부 오차 범위 안에 있으면 아예 안 넣고 버림
    칸을 자르는 선으로 쓰기 위"""
    merged = []
    for value in sorted(values):
        if not merged or value - merged[-1] > TOUCH_TOL:
            merged.append(value)
    return merged

def _glyph_strokes(all_lines: list[Line], x_min: float, x_max: float,
                   y_min: float, y_max: float) -> list[Line]:
    """글자를 찾는 함수 표 범위 안의 글자 획 = 표 선 기준(14)보다 짧은 선"""
    return [s for s in all_lines
            if length(s) < MIN_TABLE_LINE # ① 14보다 짧고
            and x_min <= _mid_x(s) <= x_max     # ② 가운데 점의 x가 표 안이고
            and y_min <= _mid_y(s) <= y_max]  #  가운데 점의 y도 표 안이면 글자 획으로 판단

# [🔴 정독] 취소선 판정. 이번 설계의 핵심
def is_struck(line: Line, strokes: list[Line]) -> bool:
    """가로선이 취소선인지 아니면 표의 경계션인지 가려내는 함수 인자로 받은 가로선을 기준으로 글자인지 판정 true -> 취소"""
    line_y = _mid_y(line)
    line_x_min, line_x_max = min(line.x1, line.x2), max(line.x1, line.x2) #가로선의 높이(y)와 가로 범위(x 시작~끝)를 구합니다.
    for stroke in strokes:
        stroke_top_y = min(stroke.y1, stroke.y2)
        stroke_bottom_y = max(stroke.y1, stroke.y2)
        if (stroke_top_y < line_y - TOUCH_TOL            # 획이 선 위에서 시작하고
                and stroke_bottom_y > line_y + TOUCH_TOL  # 선 아래에서 끝나며 (선에 닿기만 한 건 제외)
                and line_x_min <= _mid_x(stroke) <= line_x_max):  # 선이 지나가는 x 안에 있다
            return True
    return False


def find_row_ys(match: BomMatch, all_lines: list[Line]) -> tuple[list[float], list[Line]]:
    """행 경계 y 목록과, 취소선으로 빠진 선 목록"""
    full = full_width_lines(match.lines) # 가로선 표 구하기 폭 전체를 가로지는 것만
    table_x_min = min(min(ln.x1, ln.x2) for ln in full) 
    table_x_max = max(max(ln.x1, ln.x2) for ln in full)
    table_y_min = min(_mid_y(ln) for ln in full)   
    table_y_max = max(_mid_y(ln) for ln in full)   # = BOM 꼭짓점 구하기
    strokes = _glyph_strokes(all_lines, table_x_min, table_x_max, table_y_min, table_y_max) # 글자 선분 구하기
 
    struck_lines = [ln for ln in full if is_struck(ln, strokes)] # 취소선 구하기
    row_ys = _merge_close([_mid_y(ln) for ln in full if ln not in struck_lines]) # 가로선 구하
    return row_ys, struck_lines

def  find_col_lines(match: BomMatch, table_top_y: float, table_bottom_y: float) -> list[Line]:
    """BOM의 모든 선을 검사해 표 안에 세로선에 대해서만 남김"""
    return [ln for ln in match.lines
            if is_vertical(ln)
            and min(ln.y1, ln.y2) >= table_top_y - TOUCH_TOL
            and max(ln.y1, ln.y2) <= table_bottom_y + TOUCH_TOL]

def _has_wall(col_lines: list[Line], x: float, y: float) -> bool:
    """표에서 세로선이 있으면 나누고 그렇지 않으면 나누지 않기 위함"""
    return any(abs(_mid_x(ln) - x) <= TOUCH_TOL and min(ln.y1, ln.y2) <= y <= max(ln.y1, ln.y2)
               for ln in col_lines)

def make_cells(row_ys: list[float], col_xs: list[float], col_lines: list[Line]) -> list[Cell]:
    """칸 목록 표 객체를 만듦 세로선 위치 확인 -> 표 생성."""
    cells = []
    last_col = len(col_xs) - 1          # 열 수 (마지막 경계 = 표 오른쪽 테두리)
    for row in range(len(row_ys) - 1):
        y_min, y_max = row_ys[row], row_ys[row + 1]
        y_middle = (y_min + y_max) / 2  # 이 행 높이 가운데에서 세로선이 있는지 본다
        col = 0
        while col < last_col:
            end_col = col + 1           # 이 칸의 오른쪽 경계 번호
            while end_col < last_col and not _has_wall(col_lines, col_xs[end_col], y_middle):
                end_col += 1            # 벽이 없으면 옆 칸과 합친다
            cells.append(Cell(row, col, end_col - col, col_xs[col], col_xs[end_col], y_min, y_max))
            col = end_col
    return cells


def split_cells(match: BomMatch, all_lines: list[Line]) -> BomGrid:
    """순서대로 호출해서 최종 결과(BomGrid)를 만드는 전체 진행 함수."""
    row_ys, struck_lines = find_row_ys(match, all_lines) # 표 x 구하기(취소선 제외) y 좌표 구하기
    col_lines = find_col_lines(match, row_ys[0], row_ys[-1]) # 표 안에 세로선 구하기 
    col_xs = _merge_close([_mid_x(ln) for ln in col_lines]) # 세로선들의 x좌표를 모으고 가로선 후보 구하기 (일부 오차를 제외하기 위함)
    cells = make_cells(row_ys, col_xs, col_lines) # 칸 만들기 
    return BomGrid(row_ys, col_xs, struck_lines, cells)
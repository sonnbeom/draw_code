from dataclasses import dataclass

from bom.pdf_lines.geometry import bottom_end
from bom.pdf_lines.geometry import bottom_end, find_slot
from bom.find_table.select_bom import BomMatch, Connector, box_row_ys
from bom.cells.split_cells import BomGrid

@dataclass(frozen=True)
class ParentLink:
    """연결선 하나의 짝: 상위 박스 행 → 하위 BOM 열"""
    connector: Connector
    box_row: int | None  # 박스 안 행 번호 (0 = 맨 위). 못 찾으면 None
    col: int | None      # 하위 BOM 열 번호 (Cell.col과 같은 번호, 0 = 맨 왼쪽). 못 찾으면 None


def link_parents(match: BomMatch, grid: BomGrid) -> list[ParentLink]:
    """연결선마다 (박스 행, 열) 짝을 만든다. 순서는 match.connectors 순서 그대로"""
    row_ys_by_side = {}  # 박스 세로변 → 그 박스 행 경계 (박스가 여러 개일 수 있어 박스별로, 한 번만 계산)
    links = []
    for connector in match.connectors:
        side = connector.box_side
        if side not in row_ys_by_side:
            row_ys_by_side[side] = box_row_ys(match.lines, side)

        box_row = find_slot(connector.leg_start[1], row_ys_by_side[side])  # 3-1: 출발점 y → 박스 행
        col = find_slot(bottom_end(connector.drop)[0], grid.col_xs)        # 3-2: 떨어지는 x → 열
        links.append(ParentLink(connector, box_row, col))                  # 3-3: 짝
    return links

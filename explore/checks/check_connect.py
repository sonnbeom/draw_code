import json
import time
from pathlib import Path

from bom.links.connect import ParentLink, link_parents
from bom.pdf_lines.extract_lines import extract_lines
from bom.find_table.select_bom import select_bom
from bom.cells.split_cells import BomGrid, Cell, split_cells
from bom.find_table.table_candidates import find_table_candidates

SAMPLE_DIR = Path(r"C:\sample_data")
entries = json.loads((SAMPLE_DIR / "ground_truth_1000.json").read_text(encoding="utf-8"))
truth = {e["pdf_file"]: e for e in entries}  # 파일 이름 → 정답


def header_cell_at(grid: BomGrid, col: int) -> Cell | None:
    """머리글(0행)에서 col 열을 덮는 칸 (QT'Y처럼 병합된 칸이면 그 병합 칸)"""
    for cell in grid.cells:
        if cell.row == 0 and cell.col <= col < cell.col + cell.col_span:
            return cell
    return None


def links_ok(links: list[ParentLink], grid: BomGrid, num_parents: int) -> bool:
    """docs/18 확인 기준을 모두 통과하면 True"""
    if len(links) != num_parents:
        return False
    if any(link.box_row is None or link.col is None for link in links):
        return False
    box_rows = {(link.connector.box_side, link.box_row) for link in links}  # 박스별 행
    cols = {link.col for link in links}
    if len(box_rows) != num_parents or len(cols) != num_parents:  # 겹치면 set 크기가 줄어든다
        return False
    qty_cell = header_cell_at(grid, links[0].col)
    return (qty_cell is not None
            and qty_cell.col_span == num_parents
            and all(qty_cell.col <= link.col < qty_cell.col + qty_cell.col_span for link in links))


def direction(links: list[ParentLink]) -> str:
    """박스 위쪽 연결선부터 순서대로 열 번호를 늘어놓고 방향을 본다"""
    if len(links) == 1:
        return "상위 1개 (방향 없음)"
    cols = [link.col for link in sorted(links, key=lambda link: link.connector.leg_start[1])]
    if cols == sorted(cols, reverse=True):
        return "위 행 → 오른쪽 열"
    if cols == sorted(cols):
        return "위 행 → 왼쪽 열"
    return "섞임"


ok = 0
failed = []
directions = {}
link_time = 0.0
pdfs = sorted(SAMPLE_DIR.glob("case_*.pdf"))

start = time.perf_counter()
for pdf in pdfs:
    lines = extract_lines(str(pdf))
    match = select_bom(find_table_candidates(lines))
    grid = split_cells(match, lines)

    one_start = time.perf_counter()
    links = link_parents(match, grid)
    link_time += time.perf_counter() - one_start

    num_parents = truth[pdf.name]["num_parents"]
    if links_ok(links, grid, num_parents):
        ok += 1
        name = direction(links)
        directions[name] = directions.get(name, 0) + 1
    else:
        failed.append((pdf.name, num_parents, [(link.box_row, link.col) for link in links]))
elapsed = time.perf_counter() - start

print(f"[샘플 {len(pdfs)}개] 전체 {elapsed:.1f}초 (연결 추적만 {link_time:.2f}초)")
print(f"  통과: {ok}개")
for name, count in directions.items():
    print(f"    {name}: {count}개")
print(f"  틀린 도면 {len(failed)}개 (이름, num_parents, [(박스 행, 열), ...])")
for row in failed[:10]:
    print(f"    {row}")
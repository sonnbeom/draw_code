
"""칸 나누기 확인: 샘플 820개에서
  - 데이터 행 수(머리글 1행 제외) = json num_items
  - 취소선 수 = json 취소 행(is_deleted) 수
  - 머리글 마지막 칸(QT'Y)의 병합 열 수 = json num_parents
"""
import json
import time
from pathlib import Path

from bom.extract_lines import extract_lines
from bom.select_bom import select_bom
from bom.split_cells import split_cells
from bom.table_candidates import find_table_candidates

SAMPLE_DIR = Path(r"C:\sample_data")
HEADER_ROWS = 1  # 샘플 머리글은 1행 (case_0001 그림 확인)
entries = json.loads((SAMPLE_DIR / "ground_truth_1000.json").read_text(encoding="utf-8"))
truth = {e["pdf_file"]: e for e in entries}  # 파일 이름 → 정답

rows_ok = struck_ok = header_ok = 0
failed = []
split_time = 0.0
pdfs = sorted(SAMPLE_DIR.glob("case_*.pdf"))

start = time.perf_counter()
for pdf in pdfs:
    lines = extract_lines(str(pdf))          # 글자 획까지 필요해서 선 목록을 따로 받아 둔다
    match = select_bom(find_table_candidates(lines))

    one_start = time.perf_counter()
    grid = split_cells(match, lines)
    split_time += time.perf_counter() - one_start

    answer = truth[pdf.name]
    data_rows = len(grid.row_ys) - 1 - HEADER_ROWS
    deleted_rows = sum(row["is_deleted"] for row in answer["table_rows"])
    header_cells = [cell for cell in grid.cells if cell.row == 0]

    row_match = data_rows == answer["num_items"]
    struck_match = len(grid.struck_lines) == deleted_rows
    header_match = bool(header_cells) and header_cells[-1].col_span == answer["num_parents"]
    rows_ok += row_match
    struck_ok += struck_match
    header_ok += header_match
    if not (row_match and struck_match and header_match):
        failed.append((pdf.name, data_rows, answer["num_items"], len(grid.struck_lines), deleted_rows))
elapsed = time.perf_counter() - start

print(f"[샘플 {len(pdfs)}개] 전체 {elapsed:.1f}초 (칸 나누기만 {split_time:.1f}초, 도면당 {split_time / len(pdfs):.4f}초)")
print(f"  행 수 = num_items         : {rows_ok}개")
print(f"  취소선 수 = 취소 행 수     : {struck_ok}개")
print(f"  QT'Y 병합 열 = num_parents : {header_ok}개")
print(f"  틀린 도면 {len(failed)}개 (이름, 찾은 행, 정답 행, 찾은 취소선, 정답 취소)")
for row in failed[:10]:
    print(f"    {row}")
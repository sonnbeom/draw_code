"""4-1 ②: 끼워 맞추기 확인. 사전에 안 쓴 샘플(case_0601~0820)에서 읽은 글자 = json 인지.

칸 종류별(품번·품명 한 줄·수량) 맞은 비율, 남는 선이 있는 칸 수, 틀린 예시를 출력.
실행: uv run python -m explore.checks.check_glyphs
"""

import json
import time
from collections import Counter
from pathlib import Path

from bom.links.connect import link_parents
from bom.pdf_lines.extract_lines import extract_lines
from bom.dictionary.glyphs import line_center, load_glyph_dict, match_glyphs, split_text_lines, strokes_by_cell, text_height
from bom.find_table.select_bom import select_bom
from bom.cells.split_cells import split_cells
from bom.find_table.table_candidates import find_table_candidates

SAMPLE_DIR = Path(r"C:\sample_data")
CHECK_CASES = range(601, 821)
PART_NO_COL, PART_NAME_COL = 1, 2


def main() -> None:
    truth = {d["pdf_file"]: d for d in json.loads((SAMPLE_DIR / "ground_truth_1000.json").read_text(encoding="utf-8"))}
    glyphs = load_glyph_dict()
    total, correct, correct_ignore_o, with_leftover = Counter(), Counter(), Counter(), Counter()
    wrong_examples = []
    match_seconds = 0.0
    start = time.perf_counter()

    for case in CHECK_CASES:
        name = f"case_{case:04d}.pdf"
        lines = extract_lines(str(SAMPLE_DIR / name))
        match = select_bom(find_table_candidates(lines))
        if match is None:
            continue
        grid = split_cells(match, lines)
        rows = truth[name]["table_rows"]
        if len(rows) != len(grid.row_ys) - 2:
            continue
        qty_cols = sorted(link.col for link in link_parents(match, grid) if link.col is not None)
        parents = [p["part_no"] for p in truth[name]["parents_order_left_to_right"]]
        if len(qty_cols) != len(parents):
            continue

        t0 = time.perf_counter()
        by_cell = strokes_by_cell(grid, lines)
        height = text_height(by_cell)
        for i, row in enumerate(rows):
            if row["is_deleted"]:
                continue
            r = i + 1
            row_center = (grid.row_ys[r] + grid.row_ys[r + 1]) / 2
            cells = [("품번", PART_NO_COL, row["part_no"]), ("품명", PART_NAME_COL, row["part_name"])]
            cells += [("수량", col, row["quantities"][p]) for col, p in zip(qty_cols, parents)]
            for kind, col, text in cells:
                strokes = by_cell.get((r, col), [])
                text_lines = split_text_lines(strokes, height) if strokes else []
                if len(text_lines) != 1:           # 두 줄 칸은 따로 (③에서)
                    continue
                y_center = line_center(strokes, height, row_center, single=True)
                result = match_glyphs(strokes, glyphs, y_center, height)
                total[kind] += 1
                if result.leftover:
                    with_leftover[kind] += 1
                want = text.replace(" ", "")
                if result.text == want:
                    correct[kind] += 1
                if result.text.replace("O", "0") == want.replace("O", "0"):   # 0과 O는 모양이 거의 같음
                    correct_ignore_o[kind] += 1
                elif kind != "품명" and len(wrong_examples) < 12:
                    wrong_examples.append((name, kind, text, result.text, len(result.leftover)))
        match_seconds += time.perf_counter() - t0

    for kind in total:
        print(f"{kind}: {correct[kind]}/{total[kind]} 맞음 (0/O 같게 보면 {correct_ignore_o[kind]}), "
              f"남는 선 있는 칸 {with_leftover[kind]}")
    print(f"전체 {time.perf_counter() - start:.1f}초 (끼워 맞추기만 {match_seconds:.1f}초)")
    for example in wrong_examples:
        print("  틀림:", example)


if __name__ == "__main__":
    main()

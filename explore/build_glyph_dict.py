"""4-1 ①: 샘플(case_0001~0600)로 글자 사전을 만들어 bom/glyph_dict.json에 저장.

칸 → 틈으로 글자 자르기 → 글자 수 = json 문자열 길이(공백 빼고)인 칸만 → 글자마다 json 글자를 붙여 모양을 센다.
쓰는 칸: 품번(열 1), 품명(열 2, 한 줄만), 수량(연결선 열). 취소 행(is_deleted)은 뺀다.
실행: uv run python -m explore.build_glyph_dict
"""

import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from bom.connect import link_parents
from bom.extract_lines import extract_lines
from bom.glyphs import (MIN_DICT_COUNT, Glyph, line_center, save_glyph_dict, shape_of, split_by_gap,
                        split_text_lines, strokes_by_cell, text_height)
from bom.select_bom import select_bom
from bom.split_cells import split_cells
from bom.table_candidates import find_table_candidates

SAMPLE_DIR = Path(r"C:\sample_data")
BUILD_CASES = range(1, 601)          # 사전용. 601~820은 끼워 맞추기 확인용으로 남김 (데이터 누수 방지)
PART_NO_COL, PART_NAME_COL = 1, 2


def cell_texts(row: dict, qty_cols: list[int], parents: list[str]) -> dict[int, str]:
    """열 번호 → 그 칸의 정답 글자 (json)"""
    texts = {PART_NO_COL: row["part_no"], PART_NAME_COL: row["part_name"]}
    for col, parent in zip(qty_cols, parents):
        texts[col] = row["quantities"][parent]
    return texts


def main() -> None:
    truth = {d["pdf_file"]: d for d in json.loads((SAMPLE_DIR / "ground_truth_1000.json").read_text(encoding="utf-8"))}
    counts: Counter = Counter()                  # (글자, 모양) → 횟수
    widths: dict[tuple, list[float]] = defaultdict(list)
    used_cells = skipped_cells = 0
    start = time.perf_counter()

    for case in BUILD_CASES:
        name = f"case_{case:04d}.pdf"
        lines = extract_lines(str(SAMPLE_DIR / name))
        match = select_bom(find_table_candidates(lines))
        if match is None:
            continue
        grid = split_cells(match, lines)
        rows = truth[name]["table_rows"]
        if len(rows) != len(grid.row_ys) - 2:     # 행 수가 안 맞으면 그 도면은 건너뜀
            continue
        qty_cols = sorted(link.col for link in link_parents(match, grid) if link.col is not None)
        parents = [p["part_no"] for p in truth[name]["parents_order_left_to_right"]]
        if len(qty_cols) != len(parents):
            continue

        by_cell = strokes_by_cell(grid, lines)
        height = text_height(by_cell)
        for i, row in enumerate(rows):
            if row["is_deleted"]:
                continue
            r = i + 1                                  # 0 = 머리글
            row_center = (grid.row_ys[r] + grid.row_ys[r + 1]) / 2
            for col, text in cell_texts(row, qty_cols, parents).items():
                strokes = by_cell.get((r, col), [])
                chars = text.replace(" ", "")
                text_lines = split_text_lines(strokes, height) if strokes else []
                if len(text_lines) != 1:               # 빈 칸·두 줄 칸은 사전에 안 씀
                    skipped_cells += 1
                    continue
                pieces = split_by_gap(strokes)
                if len(pieces) != len(chars):
                    skipped_cells += 1
                    continue
                y_center = line_center(strokes, height, row_center, single=True)
                for piece, ch in zip(pieces, chars):
                    x_left = min(min(s.x1, s.x2) for s in piece)
                    x_right = max(max(s.x1, s.x2) for s in piece)
                    shape = shape_of(piece, x_left, y_center, height)
                    counts[(ch, shape)] += 1
                    widths[(ch, shape)].append((x_right - x_left) / height)
                used_cells += 1

    glyphs = [Glyph(ch, shape, round(sum(widths[(ch, shape)]) / len(widths[(ch, shape)]), 3), n)
              for (ch, shape), n in counts.items() if n >= MIN_DICT_COUNT]
    save_glyph_dict(glyphs)

    # ── 확인 출력 ──
    print(f"쓴 칸 {used_cells}, 건너뛴 칸 {skipped_cells}, {time.perf_counter() - start:.1f}초")
    by_char = defaultdict(list)
    for g in glyphs:
        by_char[g.char].append(g)
    print(f"글자 {len(by_char)}종, 모양 {len(glyphs)}개 (한 번만 나온 모양 {sum(1 for n in counts.values() if n < MIN_DICT_COUNT)}개 제외)")
    for ch in sorted(by_char):
        variants = sorted(by_char[ch], key=lambda g: -g.count)
        print(f"  {ch!r}: 모양 {len(variants)}개, 횟수 {[g.count for g in variants][:6]}")
    by_shape = defaultdict(set)
    for g in glyphs:
        by_shape[g.shape].add(g.char)
    same = [sorted(chs) for chs in by_shape.values() if len(chs) > 1]
    print("같은 모양 다른 글자:", same or "없음")


if __name__ == "__main__":
    main()

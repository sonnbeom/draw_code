"""4-1 ③ 확인: 칸별 취소 판정 (bom/strikes/rules.py).

- 테스트 도면 6개: 도면마다 취소 칸 (행, 열[, 줄])과 검수 칸 출력 → 직접 센 것과 비교 (TODO 4-1)
- 샘플 820개: 취소 칸이 있는 행 = json is_deleted 인지
실행: uv run python -m explore.checks.check_strikes
"""

import json
import time
from pathlib import Path

from bom.links.connect import link_parents
from bom.pdf_lines.extract_lines import extract_lines
from bom.dictionary.glyphs import load_glyph_dict
from bom.strikes.rules import REVIEW, STRUCK, mark_cells
from bom.find_table.select_bom import select_bom
from bom.cells.split_cells import split_cells
from bom.find_table.table_candidates import find_table_candidates

TEST_DIR = Path(r"C:\draw_code_test_data\draw")
SAMPLE_DIR = Path(r"C:\sample_data")
INO_COL = 0   # I/NO는 맨 왼쪽 열 (머리글 OCR 전까지 위치로)

# 테스트 도면 기댓값: 그림과 선 좌표로 직접 확인한 취소 칸 (행, 열). 행 0 = 머리글, 열 0 = I/NO
EXPECTED_STRUCK = {
    "22000": {(1, 3),                                    # 수량 두 줄 칸: 지운 2 + 새 1
              (3, 1),                                    # 품번 두 줄 칸: 지운 품번 + 새 품번
              (16, 0), (16, 1), (16, 2), (16, 3),        # 행 전체 취소
              (17, 3),                                   # 수량 두 줄 칸
              (20, 1), (20, 2)},                         # 품번·품명
    "28440": {(3, 0), (3, 1), (3, 2), (3, 3), (3, 4)},   # 행 전체 (수량 2 두 칸)
    "88300": {(7, 0), (7, 1), (7, 2), (7, 3),            # 파랑 취소 행 2개
              (8, 0), (8, 1), (8, 2), (8, 3)},
    "88361": {(r, c) for r in (3, 4) for c in range(7)},  # 파랑 취소 행 2개 (지운 '-' 6칸 포함)
    "88400": set(),                                       # 취소 없음
    "88500": {(12, 1), (12, 2), (12, 3),                  # 하위 I/NO 12 품번·품명·재질
              (23, 0), (23, 1), (23, 2), (23, 3),         # 하위 I/NO 22 (I/NO 칸 포함)
              (12, 15), (27, 15), (33, 15), (34, 15), (35, 15), (38, 15),   # 수량 12열 (상위 I/NO 12 취소)
              (23, 26), (31, 26), (33, 26), (34, 26), (35, 26), (37, 26)},  # 수량 23열 (상위 I/NO 22 취소)
}
# 검수 기댓값: 사전에 없는 모양 (그림 확인: 정상 '4'. 사전에 추가하면 비워야 함)
EXPECTED_REVIEW = {"88300": {(4, 0)}, "88400": {(4, 0)}}


def marks_of(pdf: Path, glyphs):
    lines = extract_lines(str(pdf))
    match = select_bom(find_table_candidates(lines))
    if match is None:
        return None, None
    grid = split_cells(match, lines)
    short_cols = {INO_COL} | {link.col for link in link_parents(match, grid) if link.col is not None}
    return grid, mark_cells(grid, lines, glyphs, short_cols)


def main() -> None:
    glyphs = load_glyph_dict()
    start = time.perf_counter()

    print("── 테스트 도면 (기댓값 = 직접 확인한 취소 칸)")
    passed = 0
    for pdf in sorted(TEST_DIR.glob("*.pdf")):
        key = pdf.name[:5]
        _, marks = marks_of(pdf, glyphs)
        struck = {(m.row, m.col) for m in marks if m.status == STRUCK}
        review = {(m.row, m.col) for m in marks if m.status == REVIEW}
        want_struck, want_review = EXPECTED_STRUCK[key], EXPECTED_REVIEW.get(key, set())
        good = struck == want_struck and review == want_review
        passed += good
        print(f"{'✓' if good else '✗'} {key}: 취소 {len(struck)}칸 (기대 {len(want_struck)}), "
              f"검수 {len(review)}칸 (기대 {len(want_review)})")
        if struck - want_struck:
            print(f"    잘못 취소: {sorted(struck - want_struck)}")
        if want_struck - struck:
            print(f"    놓친 취소: {sorted(want_struck - struck)}")
        if review != want_review:
            print(f"    검수 차이: 나옴 {sorted(review)}, 기대 {sorted(want_review)}")
    print(f"기대대로: {passed}/6")

    print("── 샘플 (정답 = json is_deleted 행)")
    truth = {d["pdf_file"]: d for d in json.loads((SAMPLE_DIR / "ground_truth_1000.json").read_text(encoding="utf-8"))}
    ok = checked = reviews = 0
    wrong = []
    for pdf in sorted(SAMPLE_DIR.glob("case_*.pdf")):
        grid, marks = marks_of(pdf, glyphs)
        rows = truth[pdf.name]["table_rows"]
        if marks is None or len(rows) != len(grid.row_ys) - 2:
            continue
        struck_rows = {m.row for m in marks if m.status == STRUCK}
        want_rows = {i + 1 for i, row in enumerate(rows) if row["is_deleted"]}
        reviews += sum(1 for m in marks if m.status == REVIEW)
        checked += 1
        if struck_rows == want_rows:
            ok += 1
        elif len(wrong) < 8:
            wrong.append((pdf.name, sorted(struck_rows), sorted(want_rows)))
    print(f"{'✓' if ok == checked else '✗'} 취소 행 = 정답: {ok}/{checked} 도면, "
          f"검수 칸 합계 {reviews} (기대 0), {time.perf_counter() - start:.1f}초")
    for example in wrong:
        print("  다름 (찾음, 정답):", example)


if __name__ == "__main__":
    main()

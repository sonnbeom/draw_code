"""4-2 확인: 리비전 삼각형 (bom/revisions.py).

샘플: 행·상위별 rev 글자 = json (표 행 no의 "(04)", 상위 rev "03,02")
테스트 6개: 그림으로 확인한 기댓값과 비교
실행: uv run python -m explore.check_revisions
"""

import json
import re
import time
from collections import defaultdict
from pathlib import Path

from bom.connect import link_parents
from bom.extract_lines import extract_lines
from bom.glyphs import load_glyph_dict, strokes_by_cell, text_height
from bom.parent_cells import find_parent_areas
from bom.revisions import REVIEW, find_revisions, rev_text
from bom.select_bom import select_bom
from bom.split_cells import split_cells
from bom.table_candidates import find_table_candidates

TEST_DIR = Path(r"C:\draw_code_test_data\draw")
SAMPLE_DIR = Path(r"C:\sample_data")
TRUTH = Path(r"C:\sample_data\ground_truth_1000.json")

# 기댓값: 그림으로 확인. ("표", 행) 또는 ("상위", 상위 행) → rev 글자
T, P = "표", "상위"
EXPECTED: dict[str, dict[tuple[str, int], str]] = {
    # 22000: 여러 개면 왼쪽으로 줄지어 붙음 (표 4행 = NO 3: △07 △04 △01), 표 24행은 삼각형끼리 0.6 겹침
    "22000": {(T, 1): "01", (T, 2): "01", (T, 3): "06,01", (T, 4): "07,04,01", (T, 6): "03", (T, 14): "01",
              (T, 15): "01", (T, 16): "02", (T, 17): "01", (T, 20): "04,01", (T, 21): "01", (T, 24): "03,01",
              (T, 25): "01", (T, 28): "05", (T, 29): "01", (T, 30): "02"},
    # 28440·88400: 상위 0행 삼각형은 행보다 커서 위로 삐져나옴
    "28440": {(P, 0): "05", (P, 1): "05", (T, 3): "05", (T, 4): "01", (T, 5): "01", (T, 6): "01", (T, 9): "01",
              (T, 10): "01", (T, 13): "02", (T, 14): "04", (T, 15): "03", (T, 16): "03", (T, 17): "05",
              (T, 18): "06", (T, 19): "06", (T, 20): "07", (T, 21): "07"},
    "88300": {(T, 7): "01", (T, 8): "01"},
    "88361": {(P, 0): "04", (P, 1): "04", (T, 3): "04", (T, 4): "04", (T, 8): "04", (T, 9): "04"},
    "88400": {(P, 0): "07", (P, 1): "03", (P, 2): "03", (P, 3): "04", (P, 4): "03", (P, 5): "08", (T, 2): "03", (T, 3): "03",
              (T, 6): "08", (T, 7): "03", (T, 8): "04", (T, 9): "03", (T, 10): "07"},
    # 88500: 한 자리 숫자
    "88500": {(P, 1): "7", (P, 3): "1", (P, 6): "8", (P, 7): "7", (P, 14): "1", (P, 17): "7", (P, 19): "8",
              (P, 20): "7", (T, 9): "7", (T, 11): "1", (T, 19): "7", (T, 23): "1", (T, 25): "7", (T, 36): "8",
              (T, 37): "8", (T, 38): "8", (T, 39): "8"},
}


def revisions(pdf: Path, glyphs):
    lines = extract_lines(str(pdf))
    match = select_bom(find_table_candidates(lines))
    if match is None:
        return None
    grid = split_cells(match, lines)
    height = text_height(strokes_by_cell(grid, lines))
    marks = find_revisions(grid, find_parent_areas(match), lines, glyphs, height)
    return match, grid, marks


def group(marks) -> dict[tuple, list]:
    by_row = defaultdict(list)
    for m in marks:
        by_row[(m.box_side, m.row)].append(m)
    return by_row


def main() -> None:
    start = time.perf_counter()
    glyphs = load_glyph_dict()

    print("── 테스트 도면 (기댓값 = 그림으로 확인)")
    passed = 0
    for pdf in sorted(TEST_DIR.glob("*.pdf")):
        key = pdf.name[:5]
        _, _, marks = revisions(pdf, glyphs)
        got = {("표" if side is None else "상위", row): rev_text(ms) for (side, row), ms in group(marks).items()}
        review = sum(m.status == REVIEW for m in marks)
        want = EXPECTED.get(key)
        good = got == want
        passed += good
        print(f"{'✓' if good else '✗'} {key}: 삼각형 {len(marks)}개, 검수 {review}")
        if not good:
            print(f"    나옴 {sorted(got.items())}")
            print(f"    기대 {sorted(want.items()) if want is not None else '(아직 안 적음)'}")
    print(f"기대대로: {passed}/6")

    print("── 샘플 (정답 = json 행 no의 (..), 상위 rev)")
    truth = {d["pdf_file"]: d for d in json.loads(TRUTH.read_text(encoding="utf-8"))}
    ok = checked = 0
    wrong, reviewed = [], []
    for pdf in sorted(SAMPLE_DIR.glob("case_*.pdf")):
        result = revisions(pdf, glyphs)
        if result is None:
            continue
        match, grid, marks = result
        d = truth[pdf.name]
        rows = d["table_rows"]
        if len(rows) != len(grid.row_ys) - 2:
            continue
        checked += 1
        want = {}
        for i, row in enumerate(rows):
            m = re.search(r"\(([\d,]+)\)", row["no"])
            if m:
                want[("표", i + 1)] = m.group(1)
        # 상위: 수량 열 왼쪽 → 오른쪽 = json parents_order_left_to_right
        links = sorted((ln for ln in link_parents(match, grid) if ln.col is not None), key=lambda ln: ln.col)
        for link, parent in zip(links, d["parents_order_left_to_right"]):
            if parent.get("rev"):
                want[("상위", id(link.connector.box_side), link.box_row)] = parent["rev"]
        got, review_keys = {}, set()
        for (side, row), ms in group(marks).items():
            k = ("표", row) if side is None else ("상위", id(side), row)
            got[k] = rev_text(ms)
            if any(m.status == REVIEW for m in ms):
                review_keys.add(k)
        diff_keys = {k for k in set(got) | set(want) if got.get(k) != want.get(k)}
        if not diff_keys:
            ok += 1
        elif diff_keys <= review_keys:
            reviewed.append(pdf.name)   # 틀린 곳이 전부 검수로 표시됨 (0797: 삼각형 위에 다른 글자가 겹침)
        elif len(wrong) < 5:
            diff = {k: (got.get(k), want.get(k)) for k in set(got) | set(want) if got.get(k) != want.get(k)}
            wrong.append((pdf.name, list(diff.values())[:4]))
    bad = checked - ok - len(reviewed)
    print(f"{'✓' if bad == 0 else '✗'} rev = json: {ok}/{checked} 도면, 검수로 표시 {len(reviewed)} {reviewed} (기대: 0797 1개), "
          f"틀림 {bad}, {time.perf_counter() - start:.1f}초")
    for example in wrong:
        print("  (나옴, 기대):", example)


if __name__ == "__main__":
    main()

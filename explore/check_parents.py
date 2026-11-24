"""4-1 ④ 확인: 상위 삭제/교체 판정 (bom/rules.py mark_parents).

테스트 도면 6개: 상위 행마다 (행 번호, 삭제/교체)를 기댓값과 비교. 샘플: 상위에 취소선이 없으므로 0개여야 함.
실행: uv run python -m explore.check_parents
"""

import time
from pathlib import Path

from bom.extract_lines import extract_lines
from bom.rules import mark_parents
from bom.select_bom import select_bom
from bom.table_candidates import find_table_candidates

TEST_DIR = Path(r"C:\draw_code_test_data\draw")
SAMPLE_DIR = Path(r"C:\sample_data")

# 기댓값: 그림으로 확인한 상위 행 (행 번호 = 3단계 box_row, 0 = 맨 위)
EXPECTED = {
    "22000": set(),
    "28440": set(),
    "88300": set(),
    "88361": {(0, "삭제"), (1, "삭제")},   # 박스 위 2행 88460-NX540, 88360-NX540 (파랑 취소선)
    "88400": set(),
    "88500": {(3, "삭제"),                 # I/NO 22 88500-NR680 (행 0 = 머리글)
              (6, "교체"),                 # I/NO 19 88600-NR480 → 88600-NS510
              (14, "삭제"),                # I/NO 12 88600-NR690
              (19, "교체"),                # I/NO 7  88500-NR560 → 88500-NS510
              (20, "삭제")},               # I/NO 6  88500-NR050
}


def parent_marks(pdf: Path) -> set[tuple[int, str]] | None:
    lines = extract_lines(str(pdf))
    match = select_bom(find_table_candidates(lines))
    if match is None:
        return None
    return {(m.row, m.status) for m in mark_parents(match, lines)}


def main() -> None:
    start = time.perf_counter()
    print("── 테스트 도면 (기댓값 = 그림으로 확인한 상위 행)")
    passed = 0
    for pdf in sorted(TEST_DIR.glob("*.pdf")):
        key = pdf.name[:5]
        got, want = parent_marks(pdf), EXPECTED[key]
        good = got == want
        passed += good
        print(f"{'✓' if good else '✗'} {key}: {sorted(got)} (기대 {sorted(want)})")
    print(f"기대대로: {passed}/6")

    print("── 샘플 (상위 박스에 취소선 없음 → 0개여야 함)")
    clean = checked = 0
    wrong = []
    for pdf in sorted(SAMPLE_DIR.glob("case_*.pdf")):
        got = parent_marks(pdf)
        if got is None:
            continue
        checked += 1
        if not got:
            clean += 1
        elif len(wrong) < 5:
            wrong.append((pdf.name, sorted(got)))
    print(f"{'✓' if clean == checked else '✗'} 상위 표기 0개: {clean}/{checked} 도면, {time.perf_counter() - start:.1f}초")
    for example in wrong:
        print("  나옴:", example)


if __name__ == "__main__":
    main()

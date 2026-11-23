"""BOM 고르기 확인: 테스트 도면 6개 (실제 형식, json 정답 없음 → 기대값을 직접 적어 둠)."""
import time
from pathlib import Path

from bom.extract_lines import extract_lines
from bom.select_bom import select_bom
from bom.table_candidates import find_table_candidates

TEST_DIR = Path(r"C:\draw_code_test_data\draw")

# 도면 번호(파일 이름 앞 5자리) → 기대 연결선 수. None = 지금은 못 찾는 게 정상
EXPECTED = {
    "22000": 1,
    "28440": 2,    # 화살촉 (트러블슈팅 04)
    "88300": 1,
    "88361": 4,    # 화살촉 + 기울어진 연결선 (트러블슈팅 05)
    "88400": 8,    # 화살촉
    "88500": 25,   # 상위가 표 (트러블슈팅 08)
}


def find_bom(pdf: Path):
    """PDF 하나: 선 추출 → 표 후보 묶음 → BOM 고르기."""
    return select_bom(find_table_candidates(extract_lines(str(pdf))))


passed = 0
total_start = time.perf_counter()
for pdf in sorted(TEST_DIR.glob("*.pdf")):
    drawing_no = pdf.name[:5]           # "88361-NX560 BASE ..." → "88361"
    expected = EXPECTED[drawing_no]

    one_start = time.perf_counter()
    match = find_bom(pdf)
    one_time = time.perf_counter() - one_start

    found = None if match is None else len(match.connectors)  # 못 찾으면 None, 찾으면 연결선 수
    ok = found == expected              # 기대 None이면 "못 찾음"이 맞는 결과
    passed += ok                        # True = 1, False = 0 으로 더해짐

    mark = "✓" if ok else "✗"
    found_text = "못 찾음" if found is None else f"상위 {found}개"
    expected_text = "못 찾음 (별도 패턴)" if expected is None else f"상위 {expected}개"
    print(f"{mark} {drawing_no}  결과 {found_text:<8}  기대 {expected_text:<14}  {one_time:.1f}초")

total_time = time.perf_counter() - total_start
print(f"\n[테스트 도면 {len(EXPECTED)}개] 기대대로: {passed}개, 전체 {total_time:.1f}초")

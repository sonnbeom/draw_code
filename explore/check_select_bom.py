"""BOM 고르기 확인: case_0001 결과 출력 + 샘플 820개에서 연결선 수 = json num_parents 인지."""
import json
import time
from pathlib import Path

from bom.extract_lines import extract_lines
from bom.geometry import bbox
from bom.select_bom import select_bom
from bom.table_candidates import find_table_candidates

SAMPLE_DIR = Path(r"C:\sample_data")
entries = json.loads((SAMPLE_DIR / "ground_truth_1000.json").read_text(encoding="utf-8"))
truth = {e["pdf_file"]: e for e in entries}  # 파일 이름 → 정답


def find_bom(pdf: Path):
    """PDF 하나: 선 추출 → 표 후보 묶음 → BOM 고르기."""
    return select_bom(find_table_candidates(extract_lines(str(pdf))))


# 1) case_0001 하나 자세히 ------------------------------------------------
start = time.perf_counter()  # 초 단위 시계. Java의 System.nanoTime()과 비슷
match = find_bom(SAMPLE_DIR / "case_0001.pdf")
elapsed = time.perf_counter() - start

x0, x1, y0, y1 = bbox(match.lines)
print(f"[case_0001] {elapsed:.2f}초")
print(f"  BOM 위치: x {x0:.1f}~{x1:.1f}, y {y0:.1f}~{y1:.1f} (표 윗변 y {match.top.y1:.1f})")
print(f"  상위 품번 {len(match.connectors)}개와 연결됨")
for c in match.connectors:
    print(f"    상위 박스 y {c.leg.y1:.1f} 칸 → 수량 열 x {c.drop.x1:.1f}")

# 2) 샘플 820개 전체 -------------------------------------------------------
pdfs = sorted(SAMPLE_DIR.glob("case_*.pdf"))
success = 0
not_found = []   # BOM을 아예 못 찾은 도면
wrong_count = [] # BOM은 찾았는데 상위 품번 수가 정답과 다른 도면

start = time.perf_counter()
for pdf in pdfs:
    match = find_bom(pdf)
    expected = truth[pdf.name]["num_parents"]
    if match is None:
        not_found.append(pdf.name)
    elif len(match.connectors) != expected:
        wrong_count.append((pdf.name, expected, len(match.connectors)))
    else:
        success += 1
elapsed = time.perf_counter() - start

print(f"\n[샘플 {len(pdfs)}개] {elapsed:.1f}초 (도면당 평균 {elapsed / len(pdfs):.2f}초)")
print(f"  BOM 찾고 상위 품번 수도 정답과 같음: {success}개 ({success / len(pdfs):.1%})")
print(f"  BOM 못 찾음: {len(not_found)}개")
for name in not_found[:10]:  # 많으면 앞 10개만
    print(f"    {name}")
print(f"  BOM은 찾았지만 상위 품번 수가 다름: {len(wrong_count)}개")
for name, expected, got in wrong_count[:10]:
    print(f"    {name}: 정답 {expected}개, 찾은 연결선 {got}개")
"""5단계 확인: OCR 입력 그림 (bom/cell_image.py).

- 테스트 6개: 줄 그림을 PNG로 저장 → 눈으로 확인 (뒤집힘·잘림·취소선 남음)
  기댓값: 22000 수량 (1,3)·품번 (3,1)은 두 줄 (위 = 취소, 아래 = 새 값), 그림에 취소선 0개
- 샘플 0601~0820: 실패 0, 높이가 48보다 많이 큰 그림 수
실행: uv run python -m explore.check_cell_image
"""

import tempfile
import time
from pathlib import Path

import cv2

from bom.cell_image import PAD_Y, TEXT_PX, line_images
from bom.connect import link_parents
from bom.extract_lines import extract_lines
from bom.glyphs import load_glyph_dict, strokes_by_cell, text_height
from bom.rules import mark_cells
from bom.select_bom import select_bom
from bom.split_cells import split_cells
from bom.table_candidates import find_table_candidates

TEST_DIR = Path(r"C:\draw_code_test_data\draw")
SAMPLE_DIR = Path(r"C:\sample_data")
OUT_DIR = Path(tempfile.gettempdir()) / "draw_code_cell_image"   # 그림 저장 (프로젝트 밖)
INO_COL = 0
IMG_H = TEXT_PX + 2 * PAD_Y
TALL_H = IMG_H * 1.2       # 이보다 높으면 출력 (글자보다 큰 획이 섞인 줄)
TAG = {"정상": "ok", "취소": "x", "검수": "chk"}   # 파일 이름은 영어로 (cv2가 Windows 한글 경로를 못 읽음)

# 두 줄 칸 기댓값 (check_strikes와 같은 칸): (행, 열) → 줄 수
EXPECTED_TWO_LINES = {"22000": {(1, 3): 2, (3, 1): 2, (17, 3): 2}}


def images_of(pdf: Path, glyphs):
    lines = extract_lines(str(pdf))
    match = select_bom(find_table_candidates(lines))
    if match is None:
        return None
    grid = split_cells(match, lines)
    height = text_height(strokes_by_cell(grid, lines))
    short_cols = {INO_COL} | {link.col for link in link_parents(match, grid) if link.col is not None}
    marks = mark_cells(grid, lines, glyphs, short_cols)
    strikes = [s for m in marks for s in m.strikes] + list(grid.struck_lines)
    return line_images(grid, lines, height, strikes), strikes, marks


def main() -> None:
    start = time.perf_counter()
    glyphs = load_glyph_dict()

    print(f"── 테스트 도면 (그림 저장: {OUT_DIR})")
    for pdf in sorted(TEST_DIR.glob("*.pdf")):
        key = pdf.name[:5]
        images, strikes, marks = images_of(pdf, glyphs)
        status = {(m.row, m.col, m.line): m.status for m in marks}
        out = OUT_DIR / key
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("*.png"):
            old.unlink()
        for im in images:
            st = status.get((im.row, im.col, im.line), "")
            cv2.imwrite(str(out / f"r{im.row:02d}_c{im.col:02d}_l{im.line}{'_' + TAG[st] if st else ''}.png"), im.image)
        left = len({id(s) for im in images for s in im.strokes} & {id(s) for s in strikes})
        tall = [(im.row, im.col, im.line, im.image.shape[0]) for im in images if im.image.shape[0] > TALL_H]
        print(f"{'✓' if left == 0 else '✗'} {key}: 줄 그림 {len(images)}개, 남은 취소선 {left} (기대 0), "
              f"가장 넓은 {max(im.image.shape[1] for im in images)}px, 높이>{TALL_H:.0f} {len(tall)}개 {tall[:5]}")
        for cell, want in EXPECTED_TWO_LINES.get(key, {}).items():
            got = sorted(im.line for im in images if (im.row, im.col) == cell)
            sts = [status.get((*cell, n), "") for n in got]
            print(f"  {'✓' if len(got) == want else '✗'} 칸 {cell}: 줄 {len(got)}개 (기대 {want}), 판정 {sts}")

    print("── 샘플 0601~0820")
    total = fail = bad_h = 0
    for pdf in sorted(SAMPLE_DIR.glob("case_*.pdf"))[600:820]:
        try:
            result = images_of(pdf, glyphs)
        except Exception as e:   # 그림 만들기에서 죽는 도면이 있는지
            fail += 1
            print("  실패", pdf.name, e)
            continue
        if result is None:
            continue
        images = result[0]
        total += len(images)
        bad_h += sum(im.image.shape[0] > TALL_H for im in images)
    print(f"{'✓' if fail == 0 else '✗'} 줄 그림 {total}개, 실패 {fail} (기대 0), 높이>{TALL_H:.0f} {bad_h}개, "
          f"{time.perf_counter() - start:.1f}초")


if __name__ == "__main__":
    main()

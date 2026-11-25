"""5단계 비교: OCR(칸 모드 / 줄 모드) vs 글자 사전 vs json (docs/설계/19_OCR_전략.md).

샘플 칸마다 정답(json)과 비교해 열별 정답률을 낸다.
  - 열: I/NO(0) · 품번(1) · 품명(2) · 수량(link_parents 열)
  - 칸 모드: 칸 그림(취소선 뺌) → 검출 + 인식 → 줄들을 위 → 아래로 공백으로 이어 붙임
  - 줄 모드: 칸을 골짜기로 줄 나눔(split_by_valley) → 줄마다 인식만 → 공백으로 이어 붙임
  - 사전: 4-1 CellMark.text (I/NO·수량 칸만 사전으로 읽음)
  - 정확 = 글자 그대로 같음 / 느슨 = 공백 무시 + O→0 (0/O는 모양이 같아 형식 규칙으로 풀 문제)
  - 취소·검수 줄이 있는 칸은 이번 비교에서 뺌 (따로 셈)
  - 결과 그림 보고서: explore/out/ocr_{모드}_{모델}/report.md (품번·품명 칸 그림 + OCR + 정답, 틀린 것 전부 + 맞은 것 일부)
실행: uv run python -m explore.compare_readers [시작 끝 [cell|line [en|ch]]]   (기본 600 650 cell en)
"""

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from bom.cell_image import cell_images, line_images
from bom.connect import link_parents
from bom.dash_split import read_line_text
from bom.extract_lines import extract_lines
from bom.glyphs import load_glyph_dict, strokes_by_cell, text_height
from bom.ocr import Ocr
from bom.rules import OK, mark_cells
from bom.select_bom import select_bom
from bom.split_cells import split_cells
from bom.table_candidates import find_table_candidates

SAMPLE_DIR = Path(r"C:\sample_data")
TRUTH = Path(r"C:\sample_data\ground_truth_1000.json")
INO_COL, PART_NO_COL, NAME_COL = 0, 1, 2
EXAMPLES = 5   # 열마다 보여줄 틀린 예시 수
OUT_ROOT = Path(__file__).resolve().parent / "out"
REPORT_COLS = ("품번", "품명")
REPORT_WRONG = 200   # 보고서에 넣을 틀린 칸 수 (열마다)
REPORT_RIGHT = 30    # 보고서에 넣을 맞은 칸 수 (열마다, 정말 맞았는지 눈으로 확인용)


def truth_no(no: str) -> str:
    """json I/NO "3 [BLUE]", "4 (04)" → "3", "4" (표시·리비전은 다른 단계에서 비교)"""
    return re.sub(r"\[.*?\]|\(.*?\)", "", no).strip()


def loose(text: str) -> str:
    return text.replace(" ", "").replace("O", "0")


def join_ocr(lines) -> str:
    """OCR 줄들 → 칸 글자. 높이가 비슷한 조각(PART / NAME)은 같은 줄로 보고 공백으로"""
    return " ".join(ln.text for ln in lines).strip()


def join_lines(texts: list[str]) -> str:
    """줄 모드 형식 규칙: 대문자로 (json 1000개에 소문자 0개)
    + 윗줄이 글자에 붙은 '-'로 끝나면 공백 없이 ('(3-' + 'STEPS'). 떨어진 ' -'면 공백 ('MOUNT -' + 'TYPE A')"""
    result = ""
    for t in (t.strip().upper() for t in texts):
        if not t:
            continue
        glued = result.endswith("-") and not result.endswith(" -")
        result += t if not result or glued else " " + t
    return result


def fix_part_no(text: str) -> str:
    """품번 0/O 형식 규칙 (json 12825행 통계): O는 '-' 바로 뒤 + 다음이 글자일 때만 (-OE100: O 2136 / 0 55)
    나머지 자리는 0 (숫자 사이·끝: 0 약 2만 / O 160) → 이 규칙이 구조적으로 틀리는 칸 약 1.7%"""
    chars = list(text.upper())
    for i, ch in enumerate(chars):
        if ch in "0O":
            after_hyphen = i > 0 and chars[i - 1] == "-"
            next_alpha = i + 1 < len(chars) and chars[i + 1].isalpha() and chars[i + 1] not in "O"
            chars[i] = "O" if after_hyphen and next_alpha else "0"
    return "".join(chars)


def stack(images: list[np.ndarray]) -> np.ndarray:
    """줄 그림들을 위 → 아래로 붙임 (폭은 가장 넓은 것에 맞춰 오른쪽을 흰색으로)"""
    width = max(im.shape[1] for im in images)
    padded = [cv2.copyMakeBorder(im, 0, 4, 0, width - im.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
              for im in images]
    return np.vstack(padded)


def write_report(out: Path, title: str, summary: list[str], items: dict[str, list]) -> None:
    """md 보고서: 칸 그림 | OCR | 정답 | 맞음. 그림은 img/ 아래 png"""
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    for old in img_dir.glob("*.png"):
        old.unlink()
    md = [f"# {title}", "", *[f"- {line}" for line in summary], ""]
    for name, rows in items.items():
        wrong_rows = [x for x in rows if not x[5]]
        right_rows = [x for x in rows if x[5]]
        for label, group in (("틀림 (느슨 기준)", wrong_rows), ("맞음", right_rows)):
            md += [f"## {name} {label} {len(group)}개", "", "| 칸 | 그림 | OCR | 정답 |", "|---|---|---|---|"]
            for case, r, image, got, want, _ in group:
                file = f"{name_key(name)}_{case}_r{r:02d}.png"   # 파일 이름은 영어로 (cv2가 한글 경로를 못 씀)
                cv2.imwrite(str(img_dir / file), image)
                md.append(f"| {case} 행{r} | ![](img/{file}) | `{got}` | `{want}` |")
            md.append("")
    (out / "report.md").write_text("\n".join(md), encoding="utf-8")


def name_key(name: str) -> str:
    return {"품번": "partno", "품명": "name"}[name]


def main() -> None:
    lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) >= 3 else (600, 650)
    mode = sys.argv[3] if len(sys.argv) >= 4 else "cell"
    model = sys.argv[4] if len(sys.argv) >= 5 else "en"
    start = time.perf_counter()
    glyphs = load_glyph_dict()
    ocr = Ocr(model)
    report = defaultdict(list)   # 열 이름 → [(case, 행, 그림, OCR, 정답, 느슨 맞음)]
    truth = {d["pdf_file"]: d for d in json.loads(TRUTH.read_text(encoding="utf-8"))}

    # 열 이름 → [칸 수, OCR 정확, OCR 느슨, 사전 정확, 사전 대상 칸 수]
    stats = defaultdict(lambda: [0, 0, 0, 0, 0])
    wrong = defaultdict(list)
    skipped = drawings = cells_read = 0
    for pdf in sorted(SAMPLE_DIR.glob("case_*.pdf"))[lo:hi]:
        lines = extract_lines(str(pdf))
        match = select_bom(find_table_candidates(lines))
        if match is None:
            continue
        grid = split_cells(match, lines)
        d = truth[pdf.name]
        rows = d["table_rows"]
        if len(rows) != len(grid.row_ys) - 2:
            continue   # 칸 나누기 결함 샘플 (0475·0476)
        drawings += 1
        height = text_height(strokes_by_cell(grid, lines))
        links = sorted((ln for ln in link_parents(match, grid) if ln.col is not None), key=lambda ln: ln.col)
        qty_cols = {link.col: p["part_no"] for link, p in zip(links, d["parents_order_left_to_right"])}
        marks = mark_cells(grid, lines, glyphs, {INO_COL} | set(qty_cols))
        by_cell = defaultdict(list)
        for m in marks:
            by_cell[(m.row, m.col)].append(m)
        strikes = [s for m in marks for s in m.strikes]
        if mode == "cell":
            images = {(c.row, c.col): [c] for c in cell_images(grid, lines, height, strikes)}
        else:
            images = defaultdict(list)
            for im in line_images(grid, lines, height, strikes):
                images[(im.row, im.col)].append(im)   # 위 → 아래 순서로 들어옴

        for i, row in enumerate(rows):
            r = i + 1
            want_by_col = {INO_COL: ("I/NO", truth_no(row["no"])), PART_NO_COL: ("품번", row["part_no"]),
                           NAME_COL: ("품명", row["part_name"])}
            for col, part_no in qty_cols.items():
                want_by_col[col] = ("수량", row["quantities"].get(part_no, ""))
            for col, (name, want) in want_by_col.items():
                ms = by_cell.get((r, col), [])
                if any(m.status != OK for m in ms):
                    skipped += 1
                    continue
                imgs = images.get((r, col), [])
                if mode == "cell":
                    got = join_ocr(ocr.read_cell(imgs[0].image)) if imgs else ""
                else:
                    got = join_lines([read_line_text(im.strokes, height, ocr) for im in imgs])
                if name == "품번":
                    got = fix_part_no(got)
                cells_read += bool(imgs)
                st = stats[name]
                st[0] += 1
                st[1] += got == want
                st[2] += loose(got) == loose(want)
                if ms and name in ("I/NO", "수량"):
                    st[4] += 1
                    st[3] += "".join(m.text for m in ms) == want
                if got != want and len(wrong[name]) < EXAMPLES:
                    wrong[name].append((pdf.stem[-4:], r, got, want))
                if name in REPORT_COLS and imgs:
                    right = loose(got) == loose(want)
                    have = sum(x[5] == right for x in report[name])
                    if have < (REPORT_RIGHT if right else REPORT_WRONG):
                        report[name].append((pdf.stem[-4:], r, stack([im.image for im in imgs]), got, want, right))

    elapsed = time.perf_counter() - start
    head = (f"{'칸' if mode == 'cell' else '줄'} 모드 OCR({model}) vs 사전 (case {lo + 1:04d}~{hi:04d}, 도면 {drawings}개, "
            f"취소·검수 칸 제외 {skipped}, {elapsed:.0f}초, OCR 칸당 {elapsed / max(cells_read, 1) * 1000:.0f}ms)")
    print("── " + head)
    summary = []
    for name in ("I/NO", "품번", "품명", "수량"):
        n, ok, ok_loose, d_ok, d_n = stats[name]
        dict_part = f", 사전 {d_ok}/{d_n} ({d_ok / d_n:.1%})" if d_n else ""
        line = f"{name}: OCR 정확 {ok}/{n} ({ok / max(n, 1):.1%}), 느슨 {ok_loose}/{n} ({ok_loose / max(n, 1):.1%}){dict_part}"
        summary.append(line)
        print(line)
        for case, r, got, want in wrong[name]:
            print(f"    {case} 행{r}: 나옴 {got!r} / 정답 {want!r}")
    out = OUT_ROOT / f"ocr_{mode}_{model}"
    write_report(out, head, summary, {name: report[name] for name in REPORT_COLS})
    print(f"그림 보고서: {out / 'report.md'}")


if __name__ == "__main__":
    main()

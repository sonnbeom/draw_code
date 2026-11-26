"""5단계 줄 모드: 떨어진 '-'는 선분으로 찾아 넣고, 나머지 조각만 OCR로 읽는다 (docs/설계/19_OCR_전략.md, Claude 작성).

왜: OCR이 양옆이 띄어진 '-'를 놓친다 (NUT(M8) - TYPE A → 'NUT(M8)  TYPE A').
    선분에는 '-'가 그대로 있다 (샘플 0601~0820 품명 2761칸, 떨어진 '-' 개수 = 정답 ' - ' 개수 전부 일치)
  ① 떨어진 '-' 찾기: 글자 덩어리(split_by_gap) 중 가로 획 하나 + 길이 DASH_LEN 안 + 양옆 간격 > SPACE_GAP (줄 끝은 떨어진 것)
  ② 그 자리에서 줄을 조각으로 자르고, '-' 양옆 띄어쓰기도 간격으로 정함 (" - " / 줄 끝이면 " -" 등)
  ③ 조각만 OCR로 읽고 순서대로 붙임
붙은 '-'(ASSY-RH, 간격 0.2)는 자르지 않음: OCR이 잘 읽음
"""

from bom.read_text.cell_image import render_strokes
from bom.pdf_lines.extract_lines import Line
from bom.pdf_lines.geometry import is_horizontal, length
from bom.dictionary.glyphs import DASH_LEN, split_by_gap
from bom.read_text.ocr import Ocr

SPACE_GAP = 0.4   # 글자 덩어리 사이 간격이 글자 높이 × 이 값보다 크면 띄어쓰기 (글자 사이 0.2, 띄어쓰기 1.0~1.2, 머리글 0.69)


def _x_span(group: list[Line]) -> tuple[float, float]:
    return min(min(s.x1, s.x2) for s in group), max(max(s.x1, s.x2) for s in group)


def _is_dash(group: list[Line], height: float) -> bool:
    """가로 획 하나, 길이가 '-' 범위 (샘플·테스트 모두 1.0~1.1)"""
    return (len(group) == 1 and is_horizontal(group[0])
            and DASH_LEN[0] <= length(group[0]) / height <= DASH_LEN[1])


def split_at_loose_dashes(strokes: list[Line], height: float) -> list[list[Line] | str]:
    """한 줄의 선분 → [조각, 글자, 조각, …]. 조각 = OCR로 읽을 선분들, 글자 = 우리가 넣을 '-' (띄어쓰기 포함)
    떨어진 '-'가 없으면 [선분 전체] 그대로"""
    groups = sorted(split_by_gap(strokes), key=lambda g: _x_span(g)[0])
    spans = [_x_span(g) for g in groups]
    # gaps[i] = i번째 덩어리 왼쪽 간격 (줄 맨 앞은 None)
    gaps = [None] + [(spans[i][0] - spans[i - 1][1]) / height for i in range(1, len(groups))]
    gaps.append(None)   # 마지막 덩어리 오른쪽 = 줄 끝

    result: list[list[Line] | str] = []
    piece: list[Line] = []
    for i, group in enumerate(groups):
        left, right = gaps[i], gaps[i + 1]
        loose = _is_dash(group, height) and (left is None or left > SPACE_GAP) and (right is None or right > SPACE_GAP)
        if not loose:
            piece += group
            continue
        if piece:
            result.append(piece)
            piece = []
        # 줄 맨 앞·끝 쪽은 띄어쓰기를 넣지 않음 (줄 잇기에서 정함)
        result.append((" " if left is not None else "") + "-" + (" " if right is not None else ""))
    if piece:
        result.append(piece)
    return result


def read_line_text(strokes: list[Line], height: float, ocr: Ocr) -> str:
    """한 줄의 선분 → 글자. 조각은 OCR, 떨어진 '-'는 선분에서"""
    text = ""
    for part in split_at_loose_dashes(strokes, height):
        text += part if isinstance(part, str) else ocr.read_line(render_strokes(part, height))[0].strip()
    return text

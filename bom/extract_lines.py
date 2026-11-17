from dataclasses import dataclass

import pymupdf

@dataclass(frozen=True)
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    color: tuple[float, float, float] # RGB 0~1. 검정 = (0, 0, 0)
    width: float                      # 펜 굵기 (pt)
    path_id : int                     # 원래 몇 번째 path(그리기 묶음)였는지, 디버깅용


def extract_lines(pdf_path: str, page_no: int = 0) -> list[Line]:
    # PDF의 page_no 쪽에 그려진 모든 선분을 Line 목록으로 돌려준다.
    doc = pymupdf.open(pdf_path)
    page = doc[page_no]
    lines: list[Line] = []

    # get_drawings()는 page에 그려진 모든 path를 리스트로 받음 색 굵기는 path 단위로
    for path_id, path in enumerate(page.get_drawings()):
        color = tuple(path['color']) if path['color'] else (0, 0, 0)  # RGB 0~1. 검정 = (0, 0, 0)
        width = path['width']
        
        for item in path['items']:
            kind = item[0]

            if kind == "l":
                p1, p2 = item[1], item[2]
                lines.append(Line(p1[0], p1[1], p2[0], p2[1], color, width, path_id))

            elif kind == "qu":
                q = item[1]
                corners = [q.ul, q.ur, q.lr, q.ll]  # 왼위 → 오위 → 오아래 → 왼아래 (한 바퀴)
                for i in range(4):
                    a = corners[i]
                    b = corners[(i + 1) % 4]  # 마지막 꼭짓점은 첫 꼭짓점과 이어짐
                    lines.append(Line(a.x, a.y, b.x, b.y, color, width, path_id))
            else:
                # 지금까지 데이터엔 "l"·"qu"만 있음. 다른 게 나오면 조용히 버리지 말고 바로 알린다
                raise ValueError(f"예상 못한 item 종류: {kind} (path {path_id})")
    doc.close()
    return lines
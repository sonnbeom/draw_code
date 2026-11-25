"""5단계: OCR 엔진 감싸기 (docs/설계/19_OCR_전략.md, Claude 작성).

그림 → 글자. 엔진을 바꿔도(Tesseract, 미세조정 모델) 이 파일만 고친다 (Java로 치면 인터페이스 뒤의 구현체).
  - read_cell: 칸 모드. 검출 + 인식 → 줄마다 (글자, 자신감, 줄 가운데 y, 왼쪽 x)
  - read_line: 줄 모드. 인식만 → (글자, 자신감)
방향 판정(cls)은 끈다: 우리가 그린 그림이라 뒤집힐 일이 없음.
모델: "en" = 영어 전용 PP-OCRv4 인식 모델 (models/, ModelScope RapidAI/RapidOCR에서 받음. 한자·전각 기호를 낼 수 없음)
      "ch" = RapidOCR 기본 (중국어+영어). 비교용
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from rapidocr_onnxruntime import RapidOCR

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODELS = {
    "en": {"rec_model_path": str(MODEL_DIR / "en_PP-OCRv4_rec_mobile.onnx"),
           "rec_keys_path": str(MODEL_DIR / "en_dict.txt")},   # 글자 목록 95개 (+ 공백은 라이브러리가 붙임)
    "ch": {},
}


@dataclass(frozen=True)
class OcrLine:
    text: str
    score: float      # 자신감 0~1
    y_center: float   # 그림 속 줄 가운데 y px (CellImage.line_ys와 짝지음)
    x_min: float      # 그림 속 줄 왼쪽 x px


class Ocr:
    def __init__(self, model: str = "en"):
        self.model = model
        self.engine = RapidOCR(**MODELS[model])
        # 검출 크기 조정: 기본(limit_type=min, 736)은 짧은 변을 736px까지 '키움' → 높이 49px 칸이 15배로 커져
        # 글자가 뭉개짐 (case_0601 품번 88114-TQ200 → '1','A','?'). max = 2000px 넘을 때만 줄이고 키우지 않음
        self.engine.text_det.limit_type = "max"
        self.engine.text_det.limit_side_len = 2000

    def read_cell(self, image: np.ndarray) -> list[OcrLine]:
        """칸 그림 → 찾은 줄들 (위 → 아래, 같은 높이면 왼쪽 → 오른쪽)"""
        # text_score=0: 자신감 낮은 줄도 버리지 않고 받음 (거르는 건 우리가 결과를 보고 정함)
        result, _ = self.engine(image, use_det=True, use_cls=False, use_rec=True, text_score=0)
        lines = []
        for box, text, score in result or []:
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            lines.append(OcrLine(text, float(score), (min(ys) + max(ys)) / 2, min(xs)))
        return sorted(lines, key=lambda ln: (ln.y_center, ln.x_min))

    def read_line(self, image: np.ndarray) -> tuple[str, float]:
        """줄 그림 → (글자, 자신감)"""
        result, _ = self.engine(image, use_det=False, use_cls=False, use_rec=True)
        if not result:
            return "", 0.0
        text, score = result[0]
        return text, float(score)

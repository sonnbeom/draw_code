# 02. ValueError: document closed (2026-11-18)

## 증상
`extract_lines()` 실행 중 `ValueError: document closed`.

## 원인
`doc.close()`가 path를 도는 바깥 `for` 문 **안쪽**에 들여쓰기 돼 있었음 → 첫 path를 처리한 뒤 문서를 닫고, 다음 반복에서 닫힌 문서를 읽음.
- Python은 중괄호 대신 **들여쓰기로 블록을 정한다**. Java라면 `}` 위치가 틀린 것과 같다

## 해결
`doc.close()`를 함수 본문 들여쓰기(4칸)로 내려 반복이 모두 끝난 뒤 닫음.

## 교훈
- 자원을 닫는 줄은 반복문 밖에 있는지 들여쓰기로 확인한다
- `with pymupdf.open(path) as doc:`를 쓰면 블록이 끝날 때 자동으로 닫힌다 (Java의 try-with-resources)

import fitz
from collections import Counter

doc = fitz.open(r"C:\sample_data\case_0001.pdf")
page = doc[0]  # 첫 페이지(도면은 1페이지)

drawings = page.get_drawings()  # 페이지에 그려진 도형들을 전부 꺼내기 결과는 딕셔너리들의 리스트 

print(drawings[0])  # 도형 정보 출력

cnt = Counter(len(d["items"]) for d in drawings)  # items가 N개인 path가 몇 개 있는지”를 세는 코드예요.
print("items 개수별 path 수:", sorted(cnt.items()))
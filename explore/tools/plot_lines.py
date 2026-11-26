import matplotlib.pyplot as plt

from bom.pdf_lines.extract_lines import extract_lines 

PDF = r"C:\sample_data\case_0001.pdf"

lines = extract_lines(PDF)
print("선분 수:", len(lines))  # 기대값 7106 (PDF 원본 l 개수)
print("첫 선분:", lines[0])

fig, ax = plt.subplots(figsize=(16, 11))
for ln in lines:
    ax.plot([ln.x1, ln.x2], [ln.y1, ln.y2], color=ln.color, linewidth=0.3)

ax.set_aspect("equal")  # 가로·세로 비율 유지 (안 하면 도면이 찌그러짐)
ax.invert_yaxis()       # PDF 좌표는 y가 아래로 커지므로 뒤집어야 원본과 같은 방향
plt.savefig("explore/case_0001_lines.png", dpi=200)
print("저장: explore/case_0001_lines.png")
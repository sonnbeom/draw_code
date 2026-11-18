import matplotlib.pyplot as plt

from bom.extract_lines import extract_lines
from bom.geometry import bbox
from bom.table_candidates import filter_candidates, find_table_candidates, remove_frame

PDF = r"C:\sample_data\case_0001.pdf"

lines = extract_lines(PDF)
candidates = filter_candidates(lines)
no_frame = remove_frame(candidates)
groups = find_table_candidates(lines)
print(f"전체 {len(lines)} → 후보 {len(candidates)} → 테두리 뺀 뒤 {len(no_frame)} → 묶음 {len(groups)}개")

for i, g in enumerate(groups[:5]):  # 큰 묶음 5개만 출력
    x0, x1, y0, y1 = bbox(g)
    print(f"  묶음 {i}: 선 {len(g)}개, x {x0:.1f}~{x1:.1f}, y {y0:.1f}~{y1:.1f}")

fig, ax = plt.subplots(figsize=(16, 11))

# 바탕: 원본 선 전체를 연한 회색으로
for ln in lines:
    ax.plot([ln.x1, ln.x2], [ln.y1, ln.y2], color="0.85", linewidth=0.3)

# 묶음마다 다른 색 (tab10 = matplotlib 기본 10색)
colors = plt.get_cmap("tab10")
for i, g in enumerate(groups):
    for ln in g:
        ax.plot([ln.x1, ln.x2], [ln.y1, ln.y2], color=colors(i % 10), linewidth=1.0)
    if i < 5:  # 큰 묶음 5개에 번호 표시
        x0, _, y0, _ = bbox(g)  # _ = 안 쓰는 값 자리
        ax.text(x0, y0, str(i), color=colors(i % 10), fontsize=12)

ax.set_aspect("equal")
ax.invert_yaxis()
plt.savefig("explore/case_0001_groups.png", dpi=200)
print("저장: explore/case_0001_groups.png")
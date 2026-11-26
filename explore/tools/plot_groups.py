import matplotlib.pyplot as plt

from bom.pdf_lines.extract_lines import extract_lines
from bom.pdf_lines.geometry import bbox
from bom.find_table.table_candidates import filter_candidates, find_table_candidates, remove_frame

PDF = r"C:\sample_data\case_0001.pdf"

lines = extract_lines(PDF)
candidates = filter_candidates(lines)
no_frame = remove_frame(candidates)
groups = find_table_candidates(lines)
print(f"전체 {len(lines)} → 후보 {len(candidates)} → 테두리 뺀 뒤 {len(no_frame)} → 묶음 {len(groups)}개")

for group_no, group in enumerate(groups[:5]):  # 큰 묶음 5개만 출력
    x_min, x_max, y_min, y_max = bbox(group)
    print(f"  묶음 {group_no}: 선 {len(group)}개, x {x_min:.1f}~{x_max:.1f}, y {y_min:.1f}~{y_max:.1f}")

fig, ax = plt.subplots(figsize=(16, 11))

# 바탕: 원본 선 전체를 연한 회색으로
for ln in lines:
    ax.plot([ln.x1, ln.x2], [ln.y1, ln.y2], color="0.85", linewidth=0.3)

# 묶음마다 다른 색 (tab10 = matplotlib 기본 10색)
colors = plt.get_cmap("tab10")
for group_no, group in enumerate(groups):
    for ln in group:
        ax.plot([ln.x1, ln.x2], [ln.y1, ln.y2], color=colors(group_no % 10), linewidth=1.0)
    if group_no < 5:  # 큰 묶음 5개에 번호 표시
        x_min, _, y_min, _ = bbox(group)  # _ = 안 쓰는 값 자리
        ax.text(x_min, y_min, str(group_no), color=colors(group_no % 10), fontsize=12)

ax.set_aspect("equal")
ax.invert_yaxis()
plt.savefig("explore/case_0001_groups.png", dpi=200)
print("저장: explore/case_0001_groups.png")
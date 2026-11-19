# 01. bbox 반환 순서가 달라 선이 전부 지워짐 (2026-11-18)

## 증상
`explore/plot_groups.py` 그림이 회색 바탕뿐이고 색칠된 묶음이 없음. 묶음 0개.

## 원인
`bom/geometry.py`의 `bbox`가 `(x_min, y_min, x_max, y_max)`를 돌려주는데, `remove_frame`은 `x_min, x_max, y_min, y_max = bbox(lines)`로 받음.
- tuple은 **이름이 아니라 순서로** 풀린다 → `x_max`에 y_min이, `y_min`에 x_max가 들어감
- 도면 폭 w = 0 근처, 높이 h = 음수 → "도면 폭의 50% 이상" 조건이 모든 선에서 참 → 모든 선이 테두리로 판정돼 지워짐

## 해결
| 후보 | 판단 |
|---|---|
| 받는 쪽을 `bbox` 순서에 맞춤 | 다른 호출부도 같은 실수 가능 |
| **`bbox`가 `(x_min, x_max, y_min, y_max)`를 돌려주게 통일** | ✓ x끼리, y끼리 묶여 읽기 쉬움 |
| 이름 있는 그릇(dataclass)으로 돌려줌 | 가장 안전. 이후 결과 그릇(`BomMatch`, `Connector`)은 dataclass로 만듦 |

## 교훈
- tuple로 여러 값을 돌려줄 때는 docstring에 순서를 적는다
- 값이 많거나 여러 곳에서 쓰면 dataclass로 이름을 붙인다 (Java의 record처럼)

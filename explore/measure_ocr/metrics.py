""" OCR 평가 지표: 편집 거리 CER """

# 거리를 DP로 채우는 함수
def _table(got: str, want: str) -> list[list[int]]:
    """dp[i][j] = got 앞 i글자 → want 앞 j글자 최소 수정 횟수."""
    rows, cols = len(got) + 1, len(want) + 1
    dp = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            if got[i - 1] == want[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j - 1],   # 바꾸기 (왼쪽 위)
                    dp[i - 1][j],       # 빼기   (위)
                    dp[i][j - 1],       # 넣기   (왼쪽)
                )
    return dp

# 오른쪽 하단만 체크 = 편집거리만 체크하는 것
def edit_distance(got: str, want: str) -> int:
    """got을 want로 만드는 최소 수정 횟수."""
    return _table(got, want)[-1][-1]

def edit_ops(got: str, want: str) -> list[tuple[str, str]]:
    """got(OCR 결과)을 want(정답)로 고치는 수정 목록을 돌려준다.

    각 항목은 (정답 글자, 읽은 글자) 쌍이고, 틀린 곳만 담긴다. 맞은 글자는 기록하지 않는다.
      - 바꾸기  ('0', 'O') : 정답 0을 O로 잘못 읽음      → 양쪽 다 글자
      - 빼기    ('', '-')  : 정답엔 없는 -를 더 읽음      → 정답 쪽이 빈칸
      - 넣기    ('-', '')  : 정답엔 있는 -를 놓침         → 읽은 쪽이 빈칸

    예)
      edit_ops("1O2", "102") → [('0', 'O')]
      edit_ops("a-b", "ab")  → [('', '-')]
      edit_ops("ab", "a-b")  → [('-', '')]

    동작 방식:
      표를 다 채운 뒤 오른쪽 아래(답)에서 출발해 왼쪽 위 (0, 0)까지
      "이 칸은 어느 방향에서 왔나?"를 거꾸로 따라간다.
        ↖ 대각선 : got 1글자 + want 1글자 소비 (같으면 통과, 다르면 바꾸기)
        ↑ 위     : got 1글자만 소비 → OCR이 더 읽음 (빼기)
        ← 왼쪽   : want 1글자만 소비 → OCR이 놓침 (넣기)
    """
    dp = _table(got, want)  # dp[i][j] = got 앞 i글자 → want 앞 j글자 최소 수정 횟수

    # i: got 위치 = 표의 행 번호 (세로, 위아래)
    # j: want 위치 = 표의 열 번호 (가로, 좌우)
    # 표 맨 위·맨 왼쪽에 빈 문자열("") 칸이 있어서 번호가 한 칸 밀린다.
    #   → 표의 i행 글자는 got[i - 1], j열 글자는 want[j - 1]
    i, j = len(got), len(want)              # 오른쪽 아래(최종 답 칸)에서 출발
    ops = []

    while i > 0 or j > 0:                   # 왼쪽 위 (0, 0)에 도착하면 끝
        # ① 같은 글자: 표를 채울 때 왼쪽 위 값을 그대로 가져온 칸
        #    → 수정할 게 없으니 기록 없이 ↖ 이동
        if i > 0 and j > 0 and got[i - 1] == want[j - 1]:
            i, j = i - 1, j - 1

        # ② 바꾸기: 글자는 다르고, 왼쪽 위 + 1 이 지금 칸 값과 같음
        #    → 글자 수는 맞는데 잘못 읽음 (예: 0 → O)
        #    → got·want 한 글자씩 소비하므로 i, j 둘 다 줄이며 ↖ 이동
        #    (세 방향이 동점이면 먼저 검사하는 바꾸기가 선택됨. 거리는 같음)
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            ops.append((want[j - 1], got[i - 1]))
            i, j = i - 1, j - 1

        # ③ 빼기: 위 + 1 이 지금 칸 값과 같음
        #    → got에만 있는 글자 = 정답엔 없는데 OCR이 더 읽음 (예: 끼어든 공백)
        #    → got 글자만 소비하므로 i만 줄이며 ↑ 이동
        #    (j == 0 이면 왼쪽 위·왼쪽이 없으니 항상 여기로 옴)
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops.append(("", got[i - 1]))
            i -= 1

        # ④ 넣기: 위 셋이 다 아니면 왼쪽에서 온 칸
        #    → want에만 있는 글자 = 정답엔 있는데 OCR이 놓침 (예: 못 읽은 -)
        #    → want 글자만 소비하므로 j만 줄이며 ← 이동
        #    (i == 0 이면 위쪽이 없으니 항상 여기로 옴)
        else:
            ops.append((want[j - 1], ""))
            j -= 1

    ops.reverse()                           # 뒤에서부터 모았으니 앞 → 뒤 순서로 뒤집기
    return ops



if __name__ == "__main__":
    dist_cases = [
        ("M8X25", "M8X25", 0),
        ("M8X2S", "M8X25", 1),
        ("OLX", "DLX", 1),
        ("(3- STEPS)", "(3-STEPS)", 1),
        ("8861O-TMCOO", "88610-TMC00", 3),
        ("", "-", 1),
    ]
    ops_cases = [
        ("M8X25", "M8X25", []),
        ("M8X2S", "M8X25", [("5", "S")]),
        ("OLX", "DLX", [("D", "O")]),
        ("(3- STEPS)", "(3-STEPS)", [("", " ")]),
        ("8861O-TMCOO", "88610-TMC00", [("0", "O")] * 3),
        ("", "-", [("-", "")]),
    ]
    ok = 0
    for got, want, expected in dist_cases:
        d = edit_distance(got, want)
        ok += d == expected
        print(f"{'✓' if d == expected else '✗'} 거리 {got!r} → {want!r}: 기대 {expected}, 결과 {d}")
    for got, want, expected in ops_cases:
        ops = edit_ops(got, want)
        ok += ops == expected
        print(f"{'✓' if ops == expected else '✗'} 수정 {got!r} → {want!r}: 기대 {expected}, 결과 {ops}")
    total = len(dist_cases) + len(ops_cases)
    print(f"{ok}/{total} 통과")
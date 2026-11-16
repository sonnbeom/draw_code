from PIL import Image, ImageDraw

def rasterize(points, size=16, canvas=256):
    # 1. 범위 재기
    xs = [x for x, y in points]; ys = [y for x, y in points]
    minx, miny = min(xs), min(ys)
    w, h = max(xs) - minx, max(ys) - miny
    scale = max(w, h) or 1

    # 2~3. 정규화 → 큰 캔버스 좌표로 (여백 10%, 가운데 정렬)
    pad = canvas * 0.1
    box = canvas - 2 * pad
    ox = pad + (box - w / scale * box) / 2
    oy = pad + (box - h / scale * box) / 2
    pts = [(ox + (x - minx) / scale * box,
            oy + (y - miny) / scale * box) for x, y in points]

    # 4. 점 사이 메우기 → 라이브러리가 선을 그려 줌
    img = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(img).line(pts, fill=255, width=canvas // 16)

    # 5. 16×16으로 줄이고 256개로 펼치기
    small = img.resize((size, size), Image.BILINEAR)
    return [1 if v > 64 else 0 for v in small.tobytes()]

pixels = rasterize([(10, 22), (30, 22)])   # 가로선 '-'
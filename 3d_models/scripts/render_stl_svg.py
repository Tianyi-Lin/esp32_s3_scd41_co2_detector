import math
import struct

src = "/Users/bytedance/Documents/New project/ESP32_S3_LCD_enclosure_preview.stl"
dst = "/Users/bytedance/Documents/New project/ESP32_S3_LCD_enclosure_preview.svg"

with open(src, "rb") as f:
    f.read(80)
    count = struct.unpack("<I", f.read(4))[0]
    triangles = []
    for _ in range(count):
        values = struct.unpack("<12fH", f.read(50))
        triangles.append((values[3:6], values[6:9], values[9:12]))

points = [p for tri in triangles for p in tri]
cx = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
cy = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
cz = (min(p[2] for p in points) + max(p[2] for p in points)) / 2

az = math.radians(-38)
el = math.radians(28)

def transform(p):
    x, y, z = p[0] - cx, p[1] - cy, p[2] - cz
    x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
    y, z = y * math.cos(el) - z * math.sin(el), y * math.sin(el) + z * math.cos(el)
    return x, -z, y

projected = []
for tri in triangles:
    pts = [transform(p) for p in tri]
    ax, ay, _ = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1], pts[1][2] - pts[0][2]
    bx, by, _ = pts[2][0] - pts[0][0], pts[2][1] - pts[0][1], pts[2][2] - pts[0][2]
    nz = ax * by - ay * bx
    shade = max(0.25, min(1.0, 0.58 + 0.42 * (1 if nz >= 0 else -1)))
    depth = sum(p[2] for p in pts) / 3
    projected.append((depth, pts, shade))

all_xy = [(p[0], p[1]) for _, tri, _ in projected for p in tri]
minx, maxx = min(p[0] for p in all_xy), max(p[0] for p in all_xy)
miny, maxy = min(p[1] for p in all_xy), max(p[1] for p in all_xy)
w, h, pad = 1200, 900, 80
scale = min((w - 2 * pad) / (maxx - minx), (h - 2 * pad) / (maxy - miny))

def screen(p):
    return pad + (p[0] - minx) * scale, pad + (p[1] - miny) * scale

with open(dst, "w", encoding="utf-8") as out:
    out.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    out.write('<rect width="100%" height="100%" fill="#f7f8fa"/>')
    out.write('<text x="40" y="48" font-family="sans-serif" font-size="26" fill="#273142">ESP32-S3-LCD 外壳概念预览</text>')
    for _, tri, shade in sorted(projected, key=lambda item: item[0]):
        pts = " ".join(f"{screen(p)[0]:.2f},{screen(p)[1]:.2f}" for p in tri)
        b = int(205 * shade)
        g = int(150 * shade)
        r = int(55 * shade)
        out.write(f'<polygon points="{pts}" fill="rgb({r},{g},{b})" stroke="#273142" stroke-width="0.7"/>')
    out.write('<text x="40" y="865" font-family="sans-serif" font-size="20" fill="#4b5563">上盖包含屏幕开口、传感器散热槽和杜邦线增高罩</text>')
    out.write('</svg>')

print(dst)

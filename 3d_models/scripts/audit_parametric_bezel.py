"""Read-only comparison of the rebuilt and original spline-edged cover."""
import json
import math
import sys
import time
import FreeCAD as A
import Part

source = A.openDocument(
    "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
candidate = A.openDocument(sys.argv[-1])
a, b = source.FrontBezel.Shape, candidate.Body.Tip.Shape
print("SIZES", a.Volume, b.Volume, a.Area, b.Area, flush=True)
for tol in (1e-7, 1e-6, 1e-5, 1e-4, 1e-3):
    try:
        cut1, cut2 = a.cut(b, tol), b.cut(a, tol)
        print("FUZZY", tol, cut1.Volume, cut2.Volume,
              cut1.isValid(), cut2.isValid(), flush=True)
    except Exception as exc:
        print("FUZZY_ERROR", tol, str(exc), flush=True)

for source_shape, other, direction in ((a, b, "original_to_rebuilt"),
                                      (b, a, "rebuilt_to_original")):
    worst = (0, None)
    total = 0
    for i, face in enumerate(source_shape.Faces):
        if isinstance(face.Surface, (Part.Plane, Part.Cylinder)):
            continue
        pts, triangles = face.tessellate(.02)
        selected = pts[::max(1, len(pts)//100)]
        distances = [other.distToShape(Part.Vertex(p))[0] for p in selected]
        if max(distances) > worst[0]:
            worst = (max(distances), i+1)
        total += len(selected)
        print("FACE_DISTANCE", direction, i+1, type(face.Surface).__name__,
              len(selected), max(distances), flush=True)
    print("SAMPLED_SURFACE_DISTANCE", direction, total, worst, flush=True)

for shape, label in ((a, "original"), (b, "rebuilt")):
    try:
        shape.check(True)
        print("EXTENDED_CHECK", label, "PASS", flush=True)
    except Exception as exc:
        print("EXTENDED_CHECK", label, str(exc), flush=True)
A.closeDocument(candidate.Name)
A.closeDocument(source.Name)

import FreeCAD as App
import Part
from collections import defaultdict

source = App.getDocument("ESP32_STEP_Source_Compact") if "ESP32_STEP_Source_Compact" in App.listDocuments() else None
if source is None:
    source = App.newDocument("ESP32_STEP_Source_Compact")
    Part.insert("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B.stp", source.Name)
shape_objects = [
    obj for obj in source.Objects
    if hasattr(obj, "Shape") and not obj.Shape.isNull()
]
shape = Part.makeCompound([obj.Shape.copy() for obj in shape_objects])
shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 90.0)
bb = shape.BoundBox
shape.translate(App.Vector(
    -(bb.XMin + bb.XMax) / 2.0,
    -(bb.YMin + bb.YMax) / 2.0,
    16.7 - bb.ZMin,
))

circles = defaultdict(list)
for edge in shape.Edges:
    try:
        curve = edge.Curve
        radius = float(curve.Radius)
        center = curve.Center
        axis = curve.Axis
    except Exception:
        continue
    if abs(axis.z) < 0.98 or not (0.45 <= radius <= 4.0):
        continue
    key = (round(center.x, 3), round(center.y, 3), round(radius, 3))
    circles[key].append(round(center.z, 3))

print("GEOMETRY_BBOX", bb.XLength, bb.YLength, bb.ZLength)
print("CIRCULAR_FEATURES_BEGIN")
for (x, y, radius), zs in sorted(circles.items(), key=lambda item: (item[0][0], item[0][1], item[0][2])):
    unique_z = sorted(set(zs))
    if len(unique_z) >= 2 or radius >= 0.9:
        print("CIRCLE", x, y, radius, unique_z)
print("CIRCULAR_FEATURES_END")

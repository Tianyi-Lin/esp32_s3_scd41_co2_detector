"""Read-only inspection of the existing cover and real display surfaces."""
import FreeCAD as App
import Part

ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
doc = App.openDocument(ROOT + "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
def bounds(shape):
    b = shape.BoundBox
    return tuple(round(v, 7) for v in (b.XMin, b.XMax, b.YMin, b.YMax, b.ZMin, b.ZMax))
p = doc.DesignParameters
for prop in ("FrontBezelThickness", "RearShellDepth", "ScreenToLidGap",
             "BezelInnerWallHeight", "ScreenWindowLength", "ScreenWindowWidth",
             "ScreenCornerRadius", "ScreenWindowCenterX", "BezelTransitionFilletRadius"):
    print("PARAM", prop, getattr(p, prop), flush=True)
lid = doc.FrontBezel.Shape
print("LID", bounds(lid), "VOLUME", lid.Volume,
      "POSE", doc.FrontBezel.Placement, flush=True)
for i, face in enumerate(lid.Faces, 1):
    surface = type(face.Surface).__name__
    extra = ""
    if isinstance(face.Surface, Part.Plane):
        extra = ("NORMAL", tuple(round(v, 5) for v in face.normalAt(0, 0)))
    print("LID_FACE", i, surface, round(face.Area, 6), bounds(face), extra, flush=True)
print("BOARD", bounds(doc.ESP32BoardAssembly.Shape), flush=True)
for i, solid in enumerate(doc.ESP32BoardAssembly.Shape.Solids, 1):
    b = solid.BoundBox
    if b.XLength > 20 and b.YLength > 12:
        print("DISPLAY_CANDIDATE", i, "VOLUME", solid.Volume, bounds(solid), flush=True)
        for j, face in enumerate(solid.Faces, 1):
            if isinstance(face.Surface, Part.Plane) and face.BoundBox.ZLength < 1e-6 and face.Area > 50:
                print("HORIZONTAL_FACE", i, j, face.Area, bounds(face),
                      tuple(round(v, 5) for v in face.normalAt(0,0)), flush=True)
print("EXISTING_BOARD_OVERLAP", lid.common(doc.ESP32BoardAssembly.Shape).Volume, flush=True)
App.closeDocument(doc.Name)

import FreeCAD as App
import Part

path = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"
doc = App.openDocument(path)
p = doc.DesignParameters
for key in p.PropertiesList:
    if any(word in key for word in ("Convection", "VentSlot", "ConnectorGap", "Deck", "Wall")):
        print("PARAM", key, str(getattr(p, key)), flush=True)
s = doc.RearShell.Shape
print("SHELL", s.BoundBox, s.Volume, doc.RearShell.Placement, flush=True)
for i, f in enumerate(s.Faces):
    if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Axis.x) > .9999:
        print("X_CYLINDER", i+1, "R", f.Surface.Radius, "CENTER", f.Surface.Center,
              "BBOX", f.BoundBox, flush=True)
App.closeDocument(doc.Name)

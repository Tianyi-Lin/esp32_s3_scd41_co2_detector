from pathlib import Path
import FreeCAD as App
import Part

path = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/草图直接编辑工程/上盖_草图编辑.FCStd")
doc = App.openDocument(str(path))
print("LOFT_PROPERTIES", doc.WindowLoft.PropertiesList, flush=True)
print("FILLET_PROPERTIES", doc.WindowFillet.PropertiesList, flush=True)


def assess(tag, shape):
    print("SHAPE", tag, shape.Volume, len(shape.Faces), shape.isValid(), flush=True)
    try:
        shape.check(True)
        print("BOP_PASS", tag, flush=True)
    except Exception as exc:
        print("BOP_FAIL", tag, str(exc), flush=True)
    for i, face in enumerate(shape.Faces):
        surf = face.Surface
        if isinstance(surf, Part.BSplineSurface):
            data = dict(face=i+1, type=str(type(surf)), ud=surf.UDegree, vd=surf.VDegree,
                        um=surf.getUMultiplicities(), vm=surf.getVMultiplicities(),
                        uk=surf.getUKnots(), vk=surf.getVKnots())
            if any(m >= surf.UDegree for m in data["um"][1:-1]) or any(
                    m >= surf.VDegree for m in data["vm"][1:-1]):
                print("C0_SURFACE", data, flush=True)
    for i, edge in enumerate(shape.Edges):
        curve = edge.Curve
        if isinstance(curve, Part.BSplineCurve):
            if any(m >= curve.Degree for m in curve.getMultiplicities()[1:-1]):
                print("C0_CURVE", i+1, curve.Degree, curve.getMultiplicities(),
                      curve.getKnots(), flush=True)


for feature in [doc.BasePad, doc.WindowLoft, doc.WindowFillet, doc.Counterbores]:
    assess(feature.Name, feature.Shape)
for ruled in [False, True]:
    doc.WindowLoft.Ruled = ruled
    doc.recompute()
    assess("RUled_%s" % ruled, doc.Counterbores.Shape)
for radius in [.399, .401, .35, .45, .3]:
    doc.WindowFillet.Radius = radius
    doc.recompute()
    assess("R_%s" % radius, doc.Counterbores.Shape)
App.closeDocument(doc.Name)

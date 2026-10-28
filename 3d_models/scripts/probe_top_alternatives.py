from pathlib import Path
import FreeCAD as App
import Part
import sys
sys.path.insert(0, "/Users/bytedance/Documents/New project")
import rebuild_editable_enclosure as base
from rebuild_direct_sketch_enclosure import DirectModel

path = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/草图直接编辑工程/上盖_草图编辑.FCStd")
doc = App.openDocument(str(path))
shape = doc.WindowLoft.Shape.copy()
for i, face in enumerate(shape.Faces):
    print("LOFT_FACE", i+1, type(face.Surface), flush=True)
edges = [i+1 for i, edge in enumerate(shape.Edges)
         if edge.BoundBox.ZLength < 1e-6 and abs(edge.CenterOfMass.z-base.ZTOP-3) < 1e-6
         and edge.BoundBox.XLength < 37 and edge.BoundBox.YLength < 22
         and abs(edge.CenterOfMass.x) < 20 and abs(edge.CenterOfMass.y) < 12]
print("EDGES", edges, flush=True)

def assess(tag, item):
    try:
        item.check(True)
        print("PASS", tag, item.Volume, len(item.Faces), flush=True)
        item.exportBrep(str(base.STAGE/(tag+".brep")))
        return True
    except Exception as exc:
        print("FAIL", tag, item.Volume, str(exc).replace("\n"," "), flush=True)
        return False

for tag, inds in [
    ("forward", edges), ("reverse", list(reversed(edges))),
    *[("rotate%d"%i, edges[i:]+edges[:i]) for i in range(1,8)],
]:
    try:
        result = shape.makeFillet(.4, [shape.Edges[i-1] for i in inds])
        assess(tag, result)
    except Exception as exc:
        print("EXCEPTION", tag, exc, flush=True)

# Analytic conversion of the loft before the fillet; inspection only.
print("SHAPE_APIS", [x for x in dir(shape) if any(s in x.lower() for s in
      ("refine", "split", "analytic", "nurbs", "toler", "fix"))], flush=True)
for ruled in [False, True]:
    for ref in [False, True]:
        doc.WindowLoft.Ruled = ruled
        doc.WindowLoft.Refine = ref
        doc.WindowFillet.Refine = ref
        doc.recompute()
        assess("ruled%s_ref%s"%(ruled, ref), doc.WindowFillet.Shape)
App.closeDocument(doc.Name)
print("STAGE", base.STAGE, flush=True)

import FreeCAD as App
import Part
import sys
sys.path.insert(0, "/Users/bytedance/Documents/New project")
import rebuild_editable_enclosure as base
from rebuild_direct_sketch_enclosure import DirectModel
path = base.ROOT/"草图直接编辑工程"/"上盖_草图编辑.FCStd"
doc = App.openDocument(str(path))
shape = doc.WindowLoft.Shape.copy()
edges = [i+1 for i, ed in enumerate(shape.Edges) if ed.BoundBox.ZLength < 1e-6
         and abs(ed.CenterOfMass.z-base.ZTOP-3) < 1e-6
         and ed.BoundBox.XLength < 37 and ed.BoundBox.YLength < 22
         and abs(ed.CenterOfMass.x) < 20 and abs(ed.CenterOfMass.y) < 12]
def assess(tag, item):
    try:
        item.check(True)
        print("PASS", tag, item.Volume, len(item.Faces), flush=True)
        item.exportBrep(str(base.STAGE/(tag+".brep")))
        return True
    except Exception as exc:
        print("FAIL", tag, item.Volume, str(exc).replace("\n"," "), flush=True)
        for i,f in enumerate(item.Faces):
            s=f.Surface
            if isinstance(s,Part.BSplineSurface) and (
                    any(m>=s.UDegree for m in s.getUMultiplicities()[1:-1]) or
                    any(m>=s.VDegree for m in s.getVMultiplicities()[1:-1])):
                print("BAD_FACE", i+1, f.CenterOfMass, f.Area, flush=True)
        return False
for i in edges:
    try:
        result=shape.makeFillet(.4,[shape.Edges[i-1]])
        assess("single_%d"%i,result)
    except Exception as exc: print("EXCEPTION", i, str(exc), flush=True)
# Check whether the point where the closed profile starts changes the outcome.
class Shifted(DirectModel):
    def rounded(self, sk, *args, **kwargs):
        super().rounded(sk,*args,**kwargs)
        if sk.Name.startswith("WindowSection"):
            # Reversing the loft direction is tested separately below.
            pass
doc.WindowLoft.Profile = doc.WindowSection2
doc.WindowLoft.Sections = [doc.WindowSection1]
doc.recompute()
sh=doc.WindowLoft.Shape
ids=[i+1 for i,ed in enumerate(sh.Edges) if ed.BoundBox.ZLength<1e-6
     and abs(ed.CenterOfMass.z-base.ZTOP-3)<1e-6
     and ed.BoundBox.XLength<37 and ed.BoundBox.YLength<22
     and abs(ed.CenterOfMass.x)<20 and abs(ed.CenterOfMass.y)<12]
if not sh.isNull():
    assess("reversed_loft",sh.makeFillet(.4,[sh.Edges[i-1] for i in ids]))
print("STAGE",base.STAGE,flush=True)
App.closeDocument(doc.Name)

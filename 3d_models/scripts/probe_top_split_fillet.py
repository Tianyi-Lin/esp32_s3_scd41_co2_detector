import FreeCAD as App
import Part
import sys
sys.path.insert(0, "/Users/bytedance/Documents/New project")
import rebuild_editable_enclosure as base
path=base.ROOT/"草图直接编辑工程"/"上盖_草图编辑.FCStd"
doc=App.openDocument(str(path))
shape=doc.WindowLoft.Shape.copy()
def assess(tag,sh):
    try:
        sh.check(True)
        print("PASS",tag,sh.Volume,len(sh.Faces),flush=True)
        sh.exportBrep(str(base.STAGE/(tag+".brep")))
        return True
    except Exception as exc:
        print("FAIL",tag,sh.Volume,str(exc).replace("\n"," "),flush=True)
        return False
for axis in ("x","y"):
    parts=[]
    for side in (-1,1):
        box=Part.makeBox(100,100,100,App.Vector(-100 if side<0 and axis=="x" else 0 if axis=="x" else -50,
            -100 if side<0 and axis=="y" else 0 if axis=="y" else -50, -10))
        half=shape.common(box)
        edges=[ed for ed in half.Edges if ed.BoundBox.ZLength<1e-6
               and abs(ed.CenterOfMass.z-base.ZTOP-3)<1e-6
               and abs(ed.CenterOfMass.x)<20 and abs(ed.CenterOfMass.y)<12
               and not (ed.BoundBox.XLength<1e-6 and axis=="x")
               and not (ed.BoundBox.YLength<1e-6 and axis=="y")]
        print("HALF_EDGES",axis,side,len(edges),flush=True)
        try:
            ff=half.makeFillet(.4,edges)
            assess("half_%s_%s"%(axis,side),ff)
            parts.append(ff)
        except Exception as exc:print("ERROR",axis,side,str(exc),flush=True)
    if len(parts)==2:
        for tol in (0., 1e-6, 1e-5, 1e-4):
            combined=parts[0].fuse(parts[1],tol)
            assess("fused_%s_%s"%(axis,tol),combined)
            assess("refined_%s_%s"%(axis,tol),combined.removeSplitter())
            print("VOL_DELTA",combined.Volume-doc.WindowFillet.Shape.Volume,flush=True)
print("STAGE",base.STAGE,flush=True)
App.closeDocument(doc.Name)

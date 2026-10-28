"""Rebuild the closed-ring fillet as native open-chain fillets and native union."""
import json
import sys
from pathlib import Path
import FreeCAD as App
import Part
import Sketcher
sys.path.insert(0, "/Users/bytedance/Documents/New project")
import repair_sketch_engineering as links
from rebuild_direct_sketch_enclosure import DirectModel


def assess(name, feature):
    s=feature.Shape
    assert not s.isNull() and s.isValid() and len(s.Solids)==1,(name,feature.State)
    s.check(True)
    print("NATIVE_BOP_PASS",name,s.Volume,len(s.Faces),flush=True)


def cutting_sketch(doc, body, name, xmin, xmax):
    sk=body.newObject("Sketcher::SketchObject",name)
    sk.Label="圆角分段辅助草图（不改变最终外形）"
    sk.Placement.Base.z=doc.OuterProfile.Placement.Base.z+doc.BasePad.Length.Value+1
    sk.setExpression("Placement.Base.z",
                     "OuterProfile.Placement.Base.z + BasePad.Length + 1 mm")
    pts=[(xmin,-50),(xmax,-50),(xmax,50),(xmin,50)]
    for i in range(4):
        a,b=pts[i],pts[(i+1)%4]
        j=sk.addGeometry(Part.LineSegment(App.Vector(*a,0),App.Vector(*b,0)),False)
        # Block only the auxiliary cutting outline; user design sketches remain dimensional.
        sk.addConstraint(Sketcher.Constraint("Block",j))
    doc.recompute()
    assert sk.FullyConstrained
    return sk


def native_half(doc, body, profile, base_feature, name):
    f=body.newObject("PartDesign::Pocket",name)
    f.Label="临时半侧分区（后续合并为一个上盖）"
    f.Profile=profile
    f.Type=1
    f.Length=10
    f.Refine=False
    if base_feature:
        f.BaseFeature=base_feature
    doc.recompute()
    assess(name,f)
    body.Tip=f
    return f


def round_half(doc, body, base_feature, name, axis="x"):
    z=doc.OuterProfile.Placement.Base.z+doc.BasePad.Length.Value
    inds=[i+1 for i,ed in enumerate(base_feature.Shape.Edges) if ed.BoundBox.ZLength<1e-6
          and abs(ed.CenterOfMass.z-z)<1e-6
          and abs(ed.CenterOfMass.x)<20 and abs(ed.CenterOfMass.y)<12
          and not (ed.BoundBox.XLength<1e-6 and axis=="x")]
    print("FILLET_EDGES",name,inds,flush=True)
    assert len(inds)==4
    f=body.newObject("PartDesign::Fillet",name)
    f.Label="显示窗左半圆角 R0.4" if name=="WindowFillet" else "显示窗右半圆角（随左半半径）"
    f.Base=(base_feature,["Edge%d"%i for i in inds])
    f.Radius=.4
    if name!="WindowFillet":
        f.setExpression("Radius","WindowFillet.Radius")
    f.Refine=False
    doc.recompute()
    assess(name,f)
    body.Tip=f
    return f


def repair(doc):
    # Keep the original dimensioned master sketches and their names.
    for name in ("Counterbores","ThroughHoles","WindowFillet"):
        doc.removeObject(name)
    doc.Body.Tip=doc.WindowLoft
    doc.recompute()
    source=doc.WindowLoft
    # A native sub-shape binder references the loft BEFORE the split/fillet.
    # It is a live reference, never a frozen copy of the shape.
    right=doc.addObject("PartDesign::Body","FilletAuxBody")
    right.Label="圆角辅助实体（自动关联，无需修改）"
    binder=right.newObject("PartDesign::SubShapeBinder","WindowSourceBinder")
    binder.Label="引用显示窗未倒圆实体（自动联动）"
    binder.Support=[(source,[""])]
    doc.recompute()
    assess("binder",binder)
    left_sk=cutting_sketch(doc,doc.Body,"LeftFilletSplitSketch",0,60)
    left=native_half(doc,doc.Body,left_sk,None,"LeftFilletHalf")
    lf=round_half(doc,doc.Body,left,"WindowFillet")
    right_sk=cutting_sketch(doc,right,"RightFilletSplitSketch",-60,0)
    rh=native_half(doc,right,right_sk,binder,"RightFilletHalf")
    rf=round_half(doc,right,rh,"RightWindowFillet")
    doc.Body.Tip=lf
    union=doc.Body.newObject("PartDesign::Boolean","WindowFilletUnion")
    union.Label="两半圆角合并（仍为一个完整上盖）"
    print("UNION_PROPERTIES",union.PropertiesList,flush=True)
    union.Group=[right]
    union.Type=0
    union.Refine=False
    doc.recompute()
    assess("union",union)
    doc.Body.Tip=union
    for name,profile,label,depth,through in [
        ("ThroughHoles",doc.ThroughHolesSketch,"四角通孔",4,True),
        ("Counterbores",doc.CounterboresSketch,"四角沉孔",1.35,False)]:
        f=doc.Body.newObject("PartDesign::Pocket",name)
        f.Label=label
        f.Profile=profile
        f.Length=depth
        if through:f.Type=1
        f.Refine=False
        doc.recompute()
        assess(name,f)
        doc.Body.Tip=f
    for o in doc.Objects:
        if hasattr(o,"Visibility"):
            o.Visibility=o in (doc.Body,doc.Body.Tip)
    return doc.Body.Tip


def main():
    path=links.SOURCE/"上盖_草图编辑.FCStd"
    doc=App.openDocument(str(path))
    before=doc.Body.Tip.Shape.copy()
    repair(doc)
    links.top_links(doc)
    links.check(doc)
    links.check_alignment(doc,"top")
    print("DOC_STATE",[(o.Name,o.State) for o in doc.Objects if "Invalid" in o.State],flush=True)
    tests=[links.exercise(doc,"top",*args) for args in [
        ("ThroughHolesSketch","Hole1_X",.15),
        ("ThroughHolesSketch","Diameter",.1),
        ("WindowSection1","Width",.05),
        ("OuterProfile","Length",.1)]]
    path=links.STAGE/"上盖_草图编辑.FCStd"
    doc.saveAs(str(path))
    print("SAVED",path,flush=True)
    for first,other in ((before,doc.Body.Tip.Shape),(doc.Body.Tip.Shape,before)):
        maximum=0
        count=0
        for face in first.Faces:
            points,_=face.tessellate(.02)
            points=points[::max(1,len(points)//100)]
            for p in points:
                maximum=max(maximum,other.distToShape(Part.Vertex(p))[0])
            count+=len(points)
        print("SURFACE_DISTANCE",count,maximum,flush=True)
    App.closeDocument(doc.Name)
    doc=App.openDocument(str(path))
    links.check(doc)
    links.check_alignment(doc,"top")
    print("REOPEN_PASS",path,flush=True)
    App.closeDocument(doc.Name)


if __name__=="__main__":
    main()

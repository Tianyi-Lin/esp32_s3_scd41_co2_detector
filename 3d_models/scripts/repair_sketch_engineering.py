"""Repair native sketch associations and validate editable results in staging."""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import FreeCAD as App
import Part
import Sketcher

ROOT = Path("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)")
SOURCE = ROOT/"草图直接编辑工程"
STAGE = Path(tempfile.mkdtemp(prefix="sketch-linked-repair-",
                             dir="/Users/bytedance/Documents/New project/.cad-recovery"))


def constraint_index(sk, name):
    for i, con in enumerate(sk.Constraints):
        if con.Name == name:
            return i
    raise KeyError((sk.Name, name))


def link(sk, name, expr):
    constraint_index(sk, name)
    sk.setExpression("Constraints."+name, expr)


def link_centers(doc, source, target, pairs, invert_y=False):
    master, child = doc.getObject(source), doc.getObject(target)
    for a, b in pairs:
        for axis in ("X", "Y"):
            link(child, "Hole%d_%s"%(b,axis),
                 ("-" if invert_y and axis=="Y" else "")+
                 "%s.Constraints.Hole%d_%s"%(source,a,axis))
    doc.recompute()
    child.Label += "（孔位随主控）"


def placement(doc, target, axis, expr):
    doc.getObject(target).setExpression("Placement.Base."+axis, expr)


def bottom_links(doc):
    doc.SensorBossSketch.Label = "03 CO2 凸台和安装孔位草图（主控）"
    doc.CoverHolesSketch.Label = "四角安装孔位草图（主控）"
    pairs = [(i,i) for i in range(1,5)]
    link_centers(doc, "SensorBossSketch", "SensorHolesSketch", pairs)
    link_centers(doc, "CoverHolesSketch", "CounterboreSketch", pairs)
    link_centers(doc, "SensorBossSketch", "CounterboreSketch", [(i,i+4) for i in range(1,5)])
    placement(doc, "SensorBossSketch", "z", "OuterProfile.Placement.Base.z + BasePad.Length")
    for target in ("CoverHolesSketch", "SensorHolesSketch", "VentSketch"):
        placement(doc, target, "z", "SensorBossSketch.Placement.Base.z + SensorBossPad.Length")
    placement(doc, "CounterboreSketch", "z", "OuterProfile.Placement.Base.z")


def middle_links(doc):
    pairs = [(i,i) for i in range(1,5)]
    doc.BossSketch.Label = "ESP32 凸台和安装孔位草图（主控）"
    doc.ColumnSketch.Label = "四角螺丝柱和通孔位置草图（主控）"
    link_centers(doc, "BossSketch", "BossHolesSketch", pairs)
    link_centers(doc, "ColumnSketch", "ColumnHolesSketch", pairs)
    for suffix in ("Negative","Positive"):
        link_centers(doc, "GuideSketch"+suffix, "ButtonHoleSketch"+suffix,
                     [(1,1)], invert_y=True)
        doc.getObject("GuideSketch"+suffix).Label += "（孔位主控）"
    # Both flat-cut sketches track their matching corner column, including radius changes.
    for name in ("UpperFlatsSketch", "LowerFlatsSketch"):
        sk = doc.getObject(name)
        sk.addProperty("App::PropertyLength", "CutOffset", "切面尺寸",
                       "45°切面到螺丝柱轴心的距离，影响剩余孔壁厚度")
        sk.CutOffset = 2.7818530470919226
        if name == "LowerFlatsSketch":
            sk.setExpression("CutOffset", "UpperFlatsSketch.CutOffset")
        radius = "(ColumnSketch.Constraints.Diameter / 2)"
        chord = "sqrt(%s^2 - CutOffset^2)" % radius
        for k in range(4):
            circle = doc.ColumnSketch.Geometry[k]
            sx, sy = (1 if circle.Center.x>0 else -1), (1 if circle.Center.y>0 else -1)
            nx, ny = -sx/math.sqrt(2), -sy/math.sqrt(2)
            tx, ty = -ny, nx
            for ci, c in enumerate(sk.Constraints):
                if c.First == k*4+3 and c.Type == "Radius":
                    sk.setExpression("Constraints[%d]"%ci, radius)
                if c.First not in (k*4,k*4+1) or c.Type not in ("DistanceX","DistanceY"):
                    continue
                sign = 1 if c.First == k*4 else -1
                axis = "X" if c.Type == "DistanceX" else "Y"
                n, tangent = (nx,tx) if axis=="X" else (ny,ty)
                expr = "ColumnSketch.Constraints.Hole%d_%s + CutOffset*(%.17g) + (%s)*(%.17g)"%(
                    k+1,axis,n,chord,sign*tangent)
                sk.setExpression("Constraints[%d]"%ci,expr)
    placement(doc, "ColumnSketch", "z", "OuterProfile.Placement.Base.z")
    doc.ColumnPad.setExpression("Length", "OuterPad.Length")
    placement(doc, "BossSketch", "z", "DeckSketch.Placement.Base.z + DeckPad.Length")
    placement(doc, "BossHolesSketch", "z", "BossSketch.Placement.Base.z + BossPad.Length")
    placement(doc, "ColumnHolesSketch", "z", "OuterProfile.Placement.Base.z + OuterPad.Length")
    placement(doc, "UpperFlatsSketch", "z", "OuterProfile.Placement.Base.z + OuterPad.Length")
    placement(doc, "LowerFlatsSketch", "z", "DeckSketch.Placement.Base.z")
    doc.UpperFlats.setExpression("Length",
        "UpperFlatsSketch.Placement.Base.z - (DeckSketch.Placement.Base.z + DeckPad.Length)")
    doc.LowerFlats.setExpression("Length",
        "DeckSketch.Placement.Base.z - OuterProfile.Placement.Base.z")


def top_links(doc):
    doc.ThroughHolesSketch.Label = "四角安装孔位草图（主控）"
    link_centers(doc, "ThroughHolesSketch", "CounterboresSketch", [(i,i) for i in range(1,5)])
    for target in ("ThroughHolesSketch", "CounterboresSketch", "WindowSection2"):
        placement(doc, target, "z", "OuterProfile.Placement.Base.z + BasePad.Length")
    offset = doc.WindowSection1.Placement.Base.z-doc.OuterProfile.Placement.Base.z
    placement(doc, "WindowSection1", "z", "OuterProfile.Placement.Base.z + (%.17g mm)"%offset)


def check(doc, extended=True):
    doc.recompute()
    assert all("Invalid" not in obj.State for obj in doc.Objects), [
        (o.Name,o.State) for o in doc.Objects if "Invalid" in o.State]
    sks=[o for o in doc.Objects if o.TypeId=="Sketcher::SketchObject"]
    assert all(s.FullyConstrained for s in sks),[(s.Name,s.FullyConstrained) for s in sks]
    s=doc.Body.Tip.Shape
    assert s.isValid() and len(s.Solids)==1 and s.Volume>0
    if extended:
        s.check(True)
    return s


def centers_world(sk):
    return [sk.Placement.multVec(g.Center) for g in sk.Geometry if isinstance(g,Part.Circle)]


def same_axis(a,b):
    return abs(a.x-b.x)<1e-7 and abs(a.y-b.y)<1e-7


def check_alignment(doc, kind):
    if kind=="bottom":
        boss=centers_world(doc.SensorBossSketch)
        holes=centers_world(doc.SensorHolesSketch)
        cb=centers_world(doc.CounterboreSketch)
        cv=centers_world(doc.CoverHolesSketch)
        for i in range(4):
            assert same_axis(boss[i],holes[i]) and same_axis(boss[i],cb[i+4])
            assert same_axis(cv[i],cb[i])
    elif kind=="middle":
        for a,b in [(doc.BossSketch,doc.BossHolesSketch),(doc.ColumnSketch,doc.ColumnHolesSketch)]:
            assert all(same_axis(x,y) for x,y in zip(centers_world(a),centers_world(b)))
        for sk in (doc.UpperFlatsSketch,doc.LowerFlatsSketch):
            for k,col in enumerate(doc.ColumnSketch.Geometry):
                arc=sk.Geometry[k*4+3]
                assert (arc.Center-col.Center).Length<1e-6
                assert abs(arc.Radius-col.Radius)<1e-7
        for suf in ("Negative","Positive"):
            a=centers_world(doc.getObject("GuideSketch"+suf))[0]
            b=centers_world(doc.getObject("ButtonHoleSketch"+suf))[0]
            assert abs(a.x-b.x)<1e-7 and abs(a.z-b.z)<1e-7
    else:
        assert all(same_axis(x,y) for x,y in zip(centers_world(doc.ThroughHolesSketch),
                                               centers_world(doc.CounterboresSketch)))


def exercise(doc,kind,sketch,name,delta,extended=True):
    sk=doc.getObject(sketch)
    idx=constraint_index(sk,name)
    old=sk.getDatum(idx)
    before=doc.Body.Tip.Shape.copy()
    sk.setDatum(idx,App.Units.Quantity(old.Value+delta,App.Units.Length))
    check(doc,extended)
    check_alignment(doc,kind)
    assert abs(sk.getDatum(idx).Value-old.Value-delta)<1e-8
    sk.setDatum(idx,old)
    after=check(doc,extended)
    check_alignment(doc,kind)
    assert abs(after.Volume-before.Volume)<.003
    print("EDIT_TEST_PASS",kind,sketch,name,delta,flush=True)
    return {"sketch":sketch,"dimension":name,"delta_mm":delta,"alignment":"PASS","geometry":"PASS"}


def main():
    print("STAGE",STAGE,flush=True)
    records=[]
    specs=[
        ("bottom","下盖_草图编辑.FCStd",bottom_links,
         [("SensorBossSketch","Hole1_X",.2),("SensorBossSketch","Hole1_Y",.2),
          ("CoverHolesSketch","Hole1_X",.15),("SensorHolesSketch","Diameter",.1)]),
        ("middle","中间外壳_草图编辑.FCStd",middle_links,
         [("BossSketch","Hole1_X",.15),("BossSketch","Hole1_Y",.15),
          ("ColumnSketch","Hole1_X",.1),("ColumnSketch","Diameter",.1),
          ("GuideSketchNegative","Hole1_X",.1),("GuideSketchPositive","Hole1_Y",.1)]),
    ]
    for kind,filename,setup,tests in specs:
        source=SOURCE/filename
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        doc=App.openDocument(str(source))
        before=doc.Body.Tip.Shape.copy()
        setup(doc)
        shape=check(doc)
        check_alignment(doc,kind)
        assert before.cut(shape).Volume<1e-5 and shape.cut(before).Volume<1e-5
        rec={"file":filename,"original_geometry_unchanged":True,"extended_check":"PASS"}
        rec["tests"]=[exercise(doc,kind,*t) for t in tests]
        doc.ReadMe.Label="编辑标注“主控”的草图调整孔位；凸台/通孔/沉孔会自动同轴跟随"
        doc.recompute()
        doc.saveAs(str(STAGE/filename))
        App.closeDocument(doc.Name)
        doc=App.openDocument(str(STAGE/filename))
        check(doc)
        check_alignment(doc,kind)
        App.closeDocument(doc.Name)
        rec["saved_reopened"]="PASS"
        records.append(rec)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    (STAGE/"verification.json").write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print("DONE",STAGE,flush=True)


if __name__=="__main__":
    main()

"""Enlarge all 12 M2.5 cover counterbores to 5.1 mm; preserve depths."""
import os
import math
import FreeCAD as App
import Part
import Mesh

DIRECTORY = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd")
PARTS = ("FrontBezel","RemovableBottomCover")
OLD_R, NEW_R, TOL = 2.45, 2.55, 1e-7
OUTER = {(x,y) for x in (-18.1,18.1) for y in (-12.2,12.2)}
CO2 = {(x,y) for x in (-9.0,9.0) for y in (-10.0,10.0)}

def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)

def cylinders(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
        round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),round(f.BoundBox.ZMax,6))
        for f in shape.Faces if isinstance(f.Surface,Part.Cylinder))

pending=[]
for filename in FILES:
    doc=App.openDocument(os.path.join(DIRECTORY,filename))
    p=doc.DesignParameters
    others={o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
            if "Shape" in o.PropertiesList and o.Name not in PARTS}
    for partname in PARTS:
        obj=doc.getObject(partname)
        pose=App.Placement(obj.Placement)
        before=local_shape(obj)
        old_cyls=cylinders(before)
        recesses=[c for c in old_cyls if abs(c[0]-OLD_R)<TOL]
        expected_centers=OUTER if partname=="FrontBezel" else OUTER|CO2
        assert {(x,y) for r,x,y,z0,z1 in recesses}==expected_centers
        assert len(recesses)==len(expected_centers)
        if partname=="FrontBezel":
            assert all(abs(z0-26.65)<TOL and abs(z1-28)<TOL
                       for r,x,y,z0,z1 in recesses)
        else:
            assert all(abs(z0)<TOL and abs(z1-1.4)<TOL
                       for r,x,y,z0,z1 in recesses)
        tools=[]
        for r,x,y,z0,z1 in recesses:
            # Extend the tool outside the cover only, leaving the recess floor
            # at its existing measured position on each respective face.
            tool_z=z0 if partname=="FrontBezel" else z0-.05
            tools.append(Part.makeCylinder(NEW_R,z1-z0+.05,App.Vector(x,y,tool_z)))
        cuts=Part.makeCompound(tools)
        after=before.cut(cuts).removeSplitter()
        assert after.isValid() and len(after.Solids)==1
        assert after.cut(before).Volume<TOL
        assert before.cut(after).cut(cuts).Volume<TOL
        expected_volume=sum(math.pi*(NEW_R**2-OLD_R**2)*(z1-z0)
                            for r,x,y,z0,z1 in recesses)
        print("VOLUME_CHECK",partname,before.Volume-after.Volume,expected_volume,
              "BOOLEAN_REMOVED",before.cut(after).Volume,flush=True)
        # The existing filleted bezel has tiny non-planar face integration
        # differences. Exact boolean locality and full cutter emptiness are
        # checked independently; allow 0.001 mm3 only for this volume estimate.
        volume_tolerance=.001 if partname=="FrontBezel" else 1e-6
        assert abs(before.Volume-after.Volume-expected_volume)<volume_tolerance
        assert after.common(cuts).Volume<TOL
        new_cyls=cylinders(after)
        assert [c for c in new_cyls if abs(c[0]-NEW_R)<TOL]==sorted(
            (NEW_R,x,y,z0,z1) for r,x,y,z0,z1 in recesses)
        assert not any(abs(c[0]-OLD_R)<TOL for c in new_cyls)
        # Every through-hole, boss and curved exterior wall stays unchanged.
        assert [c for c in old_cyls if abs(c[0]-OLD_R)>TOL]==[
            c for c in new_cyls if abs(c[0]-NEW_R)>TOL]
        for field in ("XMin","XMax","YMin","YMax","ZMin","ZMax"):
            assert abs(getattr(before.BoundBox,field)-getattr(after.BoundBox,field))<TOL
        obj.Shape=after
        obj.Placement=pose
        print("VERIFIED",filename,partname,"COUNT",len(recesses),
              "DIAMETER",2*NEW_R,"DEPTHS",[round(z1-z0,6) for r,x,y,z0,z1 in recesses],
              "REMOVED_VOLUME",before.Volume-after.Volume,flush=True)
    p.CoverHeadPocketDiameter=2*NEW_R
    p.CO2BottomHeadPocketDiameter=2*NEW_R
    p.Layout=p.Layout.replace("直径4.9mm、深1.4mm","直径5.1mm、深1.4mm")
    p.Layout += "上下盖所有M2.5沉孔统一直径5.1mm：上盖4处、底盖8处；保留原沉孔深度与通孔尺寸。"
    doc.recompute()
    for name,(shape,pose) in others.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A==pose,name
    print("OTHER_OBJECTS_UNCHANGED",len(others),flush=True)
    pending.append(doc)

for partname in PARTS:
    one=local_shape(pending[0].getObject(partname))
    two=local_shape(pending[1].getObject(partname))
    assert one.cut(two).Volume<TOL and two.cut(one).Volume<TOL
for doc in pending:
    doc.save()
for partname,suffix in (("FrontBezel","前盖"),("RemovableBottomCover","可拆底盖")):
    stl=os.path.join(DIRECTORY,"ESP32-S3-LCD-1.47B_紧凑双层外壳_"+suffix+".stl")
    Part.export([pending[0].getObject(partname)],stl)
    mesh=Mesh.Mesh(stl)
    assert mesh.isSolid()
    print("STL_CLOSED",suffix,mesh.CountFacets,flush=True)
for doc in pending:
    path=doc.FileName
    App.closeDocument(doc.Name)
    check=App.openDocument(path)
    for partname in PARTS:
        s=local_shape(check.getObject(partname))
        assert s.isValid() and len(s.Solids)==1
        count=sum(abs(c[0]-NEW_R)<TOL for c in cylinders(s))
        assert count==(4 if partname=="FrontBezel" else 8)
    print("SAVED_REOPENED",path,flush=True)
    App.closeDocument(check.Name)

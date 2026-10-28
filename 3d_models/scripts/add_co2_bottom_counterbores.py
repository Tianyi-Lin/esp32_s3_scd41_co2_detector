"""Add four exterior flat-bottom recesses; retain all other current geometry."""
import os
import math
import FreeCAD as App
import Part
import Mesh

DIRECTORY = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd")
RADIUS, DEPTH, BORE_RADIUS = 2.45, 1.40, 1.40
CENTERS = [(x,y) for x in (-9.0,9.0) for y in (-10.0,10.0)]
TOL = 1e-7

def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)

def cylinders(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
                   round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),
                   round(f.BoundBox.ZMax,6)) for f in shape.Faces
                  if isinstance(f.Surface,Part.Cylinder))

pending=[]
for filename in FILES:
    doc=App.openDocument(os.path.join(DIRECTORY,filename))
    cover,p=doc.RemovableBottomCover,doc.DesignParameters
    pose=App.Placement(cover.Placement)
    before=local_shape(cover)
    others={o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
            if "Shape" in o.PropertiesList and o!=cover}
    assert abs(before.BoundBox.ZMin)<TOL and abs(before.BoundBox.ZMax-3)<TOL
    assert abs(p.BottomCoverThickness.Value-2)<TOL
    assert abs(p.CO2MountSpacingLongEdge.Value-20)<TOL
    assert abs(p.CO2MountSpacingShortEdge.Value-18)<TOL
    assert sorted((x,y) for r,x,y,z0,z1 in cylinders(before)
                  if abs(r-BORE_RADIUS)<TOL)==sorted(CENTERS)
    tools=Part.makeCompound([Part.makeCylinder(RADIUS,DEPTH+.05,
           App.Vector(x,y,-.05)) for x,y in CENTERS])
    after=before.cut(tools).removeSplitter()
    removed=before.cut(after)
    assert after.isValid() and len(after.Solids)==1
    assert after.cut(before).Volume<TOL
    assert removed.cut(tools).Volume<TOL
    expected=4*math.pi*(RADIUS**2-BORE_RADIUS**2)*DEPTH
    assert abs(removed.Volume-expected)<1e-6
    assert after.common(tools).Volume<TOL
    for x,y in CENTERS:
        assert (RADIUS,x,y,0.0,DEPTH) in cylinders(after)
        assert (BORE_RADIUS,x,y,DEPTH,3.0) in cylinders(after)
        # A continuous annular support remains from the recess floor to the
        # sensor PCB support plane, including the original 1 mm standoff.
        support=Part.makeCylinder(RADIUS,3.0-DEPTH,App.Vector(x,y,DEPTH)).cut(
            Part.makeCylinder(BORE_RADIUS,3.0-DEPTH,App.Vector(x,y,DEPTH)))
        assert support.cut(after).Volume<TOL
    outer_before=[c for c in cylinders(before) if abs(c[1])>17]
    outer_after=[c for c in cylinders(after) if abs(c[1])>17]
    assert outer_before==outer_after
    for field in ("XMin","XMax","YMin","YMax","ZMin","ZMax"):
        assert abs(getattr(before.BoundBox,field)-getattr(after.BoundBox,field))<TOL
    cover.Shape=after
    cover.Placement=pose
    for key,val in (("CO2BottomHeadPocketDiameter",2*RADIUS),
                    ("CO2BottomHeadPocketDepth",DEPTH)):
        if key not in p.PropertiesList:
            p.addProperty("App::PropertyLength",key,"Dimensions")
        setattr(p,key,val)
    p.Layout += "CO2底板四孔从外侧增加直径4.9mm、深1.4mm的平底圆柱沉孔，通孔直径2.8mm，保留20×18mm孔距。"
    doc.recompute()
    assert cover.Placement.toMatrix().A==pose.toMatrix().A
    for name,(shape,placement) in others.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A==placement,name
    print("VERIFIED",filename,"RECESSES",[(x,y,2*RADIUS,DEPTH) for x,y in CENTERS],
          "SUPPORT_REMAINING",3.0-DEPTH,"REMOVED_VOLUME",removed.Volume,
          "OTHER_OBJECTS_UNCHANGED",len(others),flush=True)
    pending.append(doc)

assert local_shape(pending[0].RemovableBottomCover).cut(
    local_shape(pending[1].RemovableBottomCover)).Volume<TOL
assert local_shape(pending[1].RemovableBottomCover).cut(
    local_shape(pending[0].RemovableBottomCover)).Volume<TOL
for doc in pending:
    doc.save()
stl=os.path.join(DIRECTORY,"ESP32-S3-LCD-1.47B_紧凑双层外壳_可拆底盖.stl")
Part.export([pending[0].RemovableBottomCover],stl)
mesh=Mesh.Mesh(stl)
assert mesh.isSolid()
print("STL_CLOSED",mesh.CountFacets,flush=True)
for doc in pending:
    path=doc.FileName
    App.closeDocument(doc.Name)
    reopened=App.openDocument(path)
    s=local_shape(reopened.RemovableBottomCover)
    assert s.isValid() and len(s.Solids)==1
    assert all((RADIUS,x,y,0.0,DEPTH) in cylinders(s) for x,y in CENTERS)
    print("SAVED_REOPENED",path,flush=True)
    App.closeDocument(reopened.Name)

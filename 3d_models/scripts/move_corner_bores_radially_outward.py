"""Move the four shared cover-hole axes; leave the tower/wall outlines fixed."""
import os
import math
import FreeCAD as App
import Part
import Mesh

DIRECTORY = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd")
PARTS = ("RearShell","FrontBezel","RemovableBottomCover")
OLD_X, OLD_Y = 18.1, 12.2
NEW_X, NEW_Y = 18.56, 12.545
OLD_CENTERS = {(x,y) for x in (-OLD_X,OLD_X) for y in (-OLD_Y,OLD_Y)}
NEW_CENTERS = {(x,y) for x in (-NEW_X,NEW_X) for y in (-NEW_Y,NEW_Y)}
TOL=1e-7

def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)

def cyls(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
        round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),round(f.BoundBox.ZMax,6))
        for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
        and abs(f.Surface.Axis.z)>.999999)

def bore_targets(shape,partname,centers):
    radii=(1.15,) if partname=="RearShell" else (1.45,2.55)
    return [c for c in cyls(shape) if (c[1],c[2]) in centers and c[0] in radii]

def radial_segments(shape,x,y,z):
    ux,uy=math.copysign(.8,x),math.copysign(.6,y)
    center=App.Vector(x,y,z)
    direction=App.Vector(ux,uy,0)
    line=Part.makeLine(center-direction*7,center+direction*7)
    intersection=shape.common(line)
    intervals=[]
    for edge in intersection.Edges:
        coords=sorted((v.Point-center).dot(direction) for v in edge.Vertexes)
        if len(coords)==2:
            intervals.append(tuple(round(t,7) for t in coords))
    return sorted(intervals)

pending=[]
for filename in FILES:
    doc=App.openDocument(os.path.join(DIRECTORY,filename))
    p=doc.DesignParameters
    unchanged={o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
               if "Shape" in o.PropertiesList and o.Name not in PARTS}
    for partname in PARTS:
        obj=doc.getObject(partname)
        pose=App.Placement(obj.Placement)
        before=local_shape(obj)
        targets=bore_targets(before,partname,OLD_CENTERS)
        assert len(targets)==(4 if partname=="RearShell" else 8),(partname,targets)
        fills=[]
        cuts=[]
        expected=[]
        for r,x,y,z0,z1 in targets:
            nx,ny=math.copysign(NEW_X,x),math.copysign(NEW_Y,y)
            fills.append(Part.makeCylinder(r,z1-z0,App.Vector(x,y,z0)))
            cuts.append(Part.makeCylinder(r,z1-z0,App.Vector(nx,ny,z0)))
            expected.append((r,nx,ny,z0,z1))
        fill_tool=Part.makeCompound(fills)
        cut_tool=Part.makeCompound(cuts)
        after=before.multiFuse(fills).cut(cut_tool).removeSplitter()
        assert after.isValid() and len(after.Solids)==1,partname
        added=after.cut(before)
        removed=before.cut(after)
        assert added.cut(fill_tool).Volume<TOL,partname
        assert removed.cut(cut_tool).Volume<TOL,partname
        assert after.common(cut_tool).Volume<TOL,partname
        # Every part remains within its old envelope; no exterior or interior
        # contours are redesigned. Only the old/new cylindrical bores differ.
        volume_tolerance=.003 if partname=="FrontBezel" else 1e-6
        assert abs(before.Volume-after.Volume)<volume_tolerance,(partname,before.Volume,after.Volume)
        for field in ("XMin","XMax","YMin","YMax","ZMin","ZMax"):
            assert abs(getattr(before.BoundBox,field)-getattr(after.BoundBox,field))<TOL
        actual=bore_targets(after,partname,NEW_CENTERS)
        assert actual==sorted(expected),(partname,actual,expected)
        assert not bore_targets(after,partname,OLD_CENTERS)
        assert [c for c in cyls(before) if c not in targets]==[
            c for c in cyls(after) if c not in actual],partname
        if partname=="RearShell":
            for sx in (-1,1):
                for sy in (-1,1):
                    for z in (8.0,24.0):
                        old_sections=radial_segments(before,sx*OLD_X,sy*OLD_Y,z)
                        new_sections=radial_segments(after,sx*NEW_X,sy*NEW_Y,z)
                        assert old_sections==[(-3.1,-1.15),(1.15,4.25)],old_sections
                        assert new_sections==[(-3.675,-1.15),(1.15,3.675)],new_sections
            # A 5.1 mm head pocket is in the covers, not in the side columns.
            assert p.CoverHeadPocketDiameter.Value==5.1
            print("RADIAL_WALL_THICKNESS_OLD",1.95,3.10,
                  "RADIAL_WALL_THICKNESS_NEW",2.525,2.525,flush=True)
        if filename==FILES[0]:
            for name in ("ESP32BoardAssembly","HeaderPinsKeepout","CO2SensorEnvelope",
                         "ButtonPlungerPositive","ButtonPlungerNegative"):
                assert added.common(doc.getObject(name).Shape).Volume<TOL,(partname,name)
        obj.Shape=after
        obj.Placement=pose
        assert obj.Placement.toMatrix().A==pose.toMatrix().A
        print("VERIFIED",filename,partname,"BORES",actual,
              "ADDED_REMOVED_VOLUME",added.Volume,removed.Volume,flush=True)
    for key,value in (("CoverScrewCenterX",NEW_X),("CoverScrewCenterY",NEW_Y),
                      ("CoverScrewRadialOutwardShift",.575),
                      ("CoverScrewRadialWallThickness",2.525),
                      ("SideBodyColumnCenterX",OLD_X),("SideBodyColumnCenterY",OLD_Y)):
        if key not in p.PropertiesList:
            p.addProperty("App::PropertyLength",key,"Dimensions")
        setattr(p,key,value)
    p.Layout += "四角共用固定孔沿外圆角径向外移0.575mm至X=±18.56、Y=±12.545，侧壁该径向内外净壁厚各2.525mm；柱外形不动，上下盖对应孔同步，沉孔直径5.1mm不变。"
    doc.recompute()
    for name,(shape,pose) in unchanged.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A==pose,name
    assert p.CO2MountSpacingLongEdge.Value==20 and p.CO2MountSpacingShortEdge.Value==18
    assert p.HeaderSlotLength.Value==22.92 and p.HeaderSlotWidth.Value==2.6
    print("OTHER_OBJECTS_UNCHANGED",len(unchanged),flush=True)
    pending.append(doc)

for name in PARTS:
    a=local_shape(pending[0].getObject(name))
    b=local_shape(pending[1].getObject(name))
    assert a.cut(b).Volume<TOL and b.cut(a).Volume<TOL
for doc in pending:
    doc.save()
for name,suffix in (("RearShell","后壳"),("FrontBezel","前盖"),
                    ("RemovableBottomCover","可拆底盖")):
    path=os.path.join(DIRECTORY,"ESP32-S3-LCD-1.47B_紧凑双层外壳_"+suffix+".stl")
    Part.export([pending[0].getObject(name)],path)
    mesh=Mesh.Mesh(path)
    assert mesh.isSolid()
    print("STL_CLOSED",suffix,mesh.CountFacets,flush=True)
for doc in pending:
    path=doc.FileName
    App.closeDocument(doc.Name)
    check=App.openDocument(path)
    for name in PARTS:
        shape=local_shape(check.getObject(name))
        assert shape.isValid() and len(shape.Solids)==1
        assert len(bore_targets(shape,name,NEW_CENTERS))==(4 if name=="RearShell" else 8)
    print("SAVED_REOPENED",path,flush=True)
    App.closeDocument(check.Name)

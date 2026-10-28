"""Move matching cover axes and balance corner-column walls; validate before saving."""
import os
import math
import ast
import FreeCAD as App
import Part
import Mesh

DIRECTORY = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd")
PARTS = ("RearShell", "FrontBezel", "RemovableBottomCover")
OLD_X, OLD_Y = 18.1, 12.2
NEW_X, NEW_Y = 18.66, 12.62
RIM, TOWER_RADIUS = 1.0, 3.55
OLD_CENTERS = {(x,y) for x in (-OLD_X,OLD_X) for y in (-OLD_Y,OLD_Y)}
NEW_CENTERS = {(x,y) for x in (-NEW_X,NEW_X) for y in (-NEW_Y,NEW_Y)}
PCB_MOUNTS = ((-16.814,-6.640),(-16.814,6.640),(15.186,-8.160),(15.186,8.160))
TOL = 1e-6
SAVE = os.environ.get("CAD_SAVE_BALANCED_CORNERS") == "1"

def front_blank():
    """Reproduce only the existing window and fillets, without running the generator."""
    source=open("/Users/bytedance/Documents/New project/create_compact_stacked_enclosure.py").read()
    parsed=ast.parse(source)
    functions=[node for node in parsed.body if isinstance(node,ast.FunctionDef)
               and node.name in ("rounded_prism","rounded_wire")]
    env={"App":App,"Part":Part,"outer_w":45.,"outer_d":33.5,
         "base_h":25.,"lid_t":3.,"corner_r":5.}
    exec(compile(ast.Module(body=functions,type_ignores=[]),"front_helpers","exec"),env)
    start=source.index("lid_shape = rounded_prism(")
    end=source.index("# Both cover locating rims",start)
    exec(compile(source[start:end],"front_window_only","exec"),env)
    return env["lid_shape"]

FRONT_BLANK=front_blank()

def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)

def rounded_prism(w,d,h,r,z):
    result=Part.makeBox(w-2*r,d,h,App.Vector(-w/2+r,-d/2,z))
    result=result.fuse(Part.makeBox(w,d-2*r,h,App.Vector(-w/2,-d/2+r,z)))
    for x in (-w/2+r,w/2-r):
        for y in (-d/2+r,d/2-r):
            result=result.fuse(Part.makeCylinder(r,h,App.Vector(x,y,z)))
    return result.removeSplitter()

def cylinder(r,x,y,z0,z1):
    return Part.makeCylinder(r,z1-z0,App.Vector(x,y,z0))

def cyls(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
        round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),round(f.BoundBox.ZMax,6))
        for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
        and abs(f.Surface.Axis.z)>.999999)

def bore_targets(shape,partname,centers):
    radii=(1.15,) if partname=="RearShell" else (1.45,2.55)
    return [c for c in cyls(shape) if (c[1],c[2]) in centers and c[0] in radii]

def radial_segments(shape,x,y,z):
    direction=App.Vector(math.copysign(.8,x),math.copysign(.6,y),0)
    center=App.Vector(x,y,z)
    result=[]
    for edge in shape.common(Part.makeLine(center-direction*7,center+direction*7)).Edges:
        coords=sorted((v.Point-center).dot(direction) for v in edge.Vertexes)
        if len(coords)==2:
            result.append(tuple(round(t,6) for t in coords))
    return sorted(result)

def close(a,b,tol=1e-6):
    return abs(a-b)<tol

def alter_covers(before,name):
    old=bore_targets(before,name,OLD_CENTERS)
    assert len(old)==8,(name,old)
    # A 0.001 mm lateral overlap eliminates coincident-edge slivers in the
    # existing filleted front cover. It does not enlarge the material region.
    fills=[cylinder(r+.001,x,y,z0,z1) for r,x,y,z0,z1 in old]
    cuts=[]
    if name=="FrontBezel":
        intervals=((1.45,24.9,28.4),(2.55,26.65,28.4))
        expected=[(r,x,y,z0,z1) for x,y in NEW_CENTERS
                  for r,z0,z1 in ((1.45,25,26.65),(2.55,26.65,28))]
    else:
        intervals=((1.45,-.1,2.1),(2.55,-.1,1.4))
        expected=[(r,x,y,z0,z1) for x,y in NEW_CENTERS
                  for r,z0,z1 in ((1.45,1.4,2),(2.55,0,1.4))]
    for x,y in NEW_CENTERS:
        cuts.extend(cylinder(r,x,y,z0,z1) for r,z0,z1 in intervals)
    fill_tool=Part.makeCompound(fills)
    if name=="FrontBezel":
        # The old left counterbores intersect the display's upper fillet.
        # Restore only material within that fillet, never a cylindrical bump.
        fill_tool=fill_tool.common(FRONT_BLANK)
    cut_tool=Part.makeCompound(cuts)
    after=before.fuse(fill_tool).cut(cut_tool).removeSplitter()
    print("COVER_OLD_CYLINDERS_LEFT",name,bore_targets(after,name,OLD_CENTERS),flush=True)
    print("COVER_NEW_CYLINDERS",name,bore_targets(after,name,NEW_CENTERS),flush=True)
    assert not bore_targets(after,name,OLD_CENTERS)
    assert bore_targets(after,name,NEW_CENTERS)==sorted(expected)
    assert after.cut(before).cut(fill_tool).Volume<TOL
    assert before.cut(after).cut(cut_tool).Volume<TOL
    assert after.common(cut_tool).Volume<TOL
    # No other vertical holes may change, including all four CO2 mount holes.
    remaining_before=[c for c in cyls(before) if c not in old]
    remaining_after=[c for c in cyls(after) if c not in expected]
    print("OTHER_CYLINDER_DIFFERENCE", name,
          set(remaining_before)-set(remaining_after),
          set(remaining_after)-set(remaining_before),flush=True)
    assert remaining_before==remaining_after
    assert abs(after.Volume-before.Volume)<.003,(name,before.Volume,after.Volume)
    for x,y in NEW_CENTERS:
        z=27.5 if name=="FrontBezel" else .5
        intervals=radial_segments(after,x,y,z)
        outer=[i for i in intervals if i[0]>0]
        assert len(outer)==1 and close(outer[0][0],2.55) and close(outer[0][1],3.55),intervals
    return after

def alter_body(before):
    oldtowers=Part.makeCompound([cylinder(3.1,x,y,2.05,25) for x,y in OLD_CENTERS])
    newtowers=Part.makeCompound([cylinder(TOWER_RADIUS,x,y,2.05,25) for x,y in NEW_CENTERS])
    cavity=rounded_prism(41,29.5,23.15,3,1.95)
    protected=rounded_prism(41.4,29.9,2,3.2,13.5)
    protected=protected.multiFuse([cylinder(2,x,y,15.5,17.436) for x,y in PCB_MOUNTS])
    trim=oldtowers.cut(newtowers).common(cavity).cut(protected)
    fills=[cylinder(1.151,x,y,2.05,25) for x,y in OLD_CENTERS]
    after=before.multiFuse(fills).cut(trim).multiFuse(newtowers.Solids)
    cuts=[cylinder(1.15,x,y,1.95,25.1) for x,y in NEW_CENTERS]
    cuts.extend(cylinder(1.1,x,y,13.2,17.736) for x,y in PCB_MOUNTS)
    cuts.extend(Part.makeBox(22.92,2.6,7.936,App.Vector(-15.349,y-1.3,10))
                for y in (-8.89,8.89))
    after=after.cut(Part.makeCompound(cuts)).removeSplitter()
    allowed=oldtowers.fuse(newtowers)
    assert after.cut(before).cut(allowed).Volume<TOL
    assert before.cut(after).cut(allowed).Volume<TOL
    assert not bore_targets(after,"RearShell",OLD_CENTERS)
    assert bore_targets(after,"RearShell",NEW_CENTERS)==sorted(
        (1.15,x,y,2.05,25) for x,y in NEW_CENTERS)
    for x,y in NEW_CENTERS:
        for z in (8,24):
            section=radial_segments(after,x,y,z)
            assert section==[(-3.55,-1.15),(1.15,3.55)],section
    # The deck remains connected to every straight wall along its full length.
    for x,y,dx,dy in ((-20.6,-9,.4,18),(20.2,-9,.4,18),
                       (-14,-14.85,28,.4),(-14,14.45,28,.4)):
        probe=Part.makeBox(dx,dy,2,App.Vector(x,y,13.5))
        assert probe.cut(after).Volume<TOL
    return after

pending=[]
for filename in FILES:
    doc=App.openDocument(os.path.join(DIRECTORY,filename))
    p=doc.DesignParameters
    unchanged={o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
               if "Shape" in o.PropertiesList and o.Name not in PARTS}
    for name in PARTS:
        obj=doc.getObject(name)
        pose=App.Placement(obj.Placement)
        before=local_shape(obj)
        after=alter_body(before) if name=="RearShell" else alter_covers(before,name)
        assert after.isValid() and len(after.Solids)==1,(filename,name)
        for field in ("XMin","XMax","YMin","YMax","ZMin","ZMax"):
            assert close(getattr(before.BoundBox,field),getattr(after.BoundBox,field)),(name,field)
        if filename==FILES[0]:
            additions=after.cut(before)
            for other in ("ESP32BoardAssembly","HeaderPinsKeepout","CO2SensorEnvelope",
                          "ButtonPlungerPositive","ButtonPlungerNegative"):
                collision=additions.common(doc.getObject(other).Shape).Volume
                assert collision<TOL,(name,other,collision)
            if name=="RearShell":
                print("BODY_BOARD_INTERSECTION_BEFORE_AFTER",
                      before.common(doc.ESP32BoardAssembly.Shape).Volume,
                      after.common(doc.ESP32BoardAssembly.Shape).Volume,flush=True)
                for x,y in NEW_CENTERS:
                    distance=cylinder(3.55,x,y,2.05,25).distToShape(doc.ESP32BoardAssembly.Shape)[0]
                    overlap=cylinder(3.55,x,y,2.05,25).common(doc.ESP32BoardAssembly.Shape).Volume
                    print("COLUMN_ELECTRONICS_CLEARANCE",x,y,distance,"OVERLAP",overlap,flush=True)
        obj.Shape=after
        obj.Placement=pose
        print("VALIDATED",filename,name,"VOLUME",before.Volume,after.Volume,flush=True)
    for key,value in (("CoverScrewCenterX",NEW_X),("CoverScrewCenterY",NEW_Y),
                      ("CoverScrewRadialOutwardShift",.7),("CoverScrewRadialWallThickness",2.4),
                      ("SideBodyColumnCenterX",NEW_X),("SideBodyColumnCenterY",NEW_Y),
                      ("SideBodyColumnDiameter",7.1),("CoverHeadPocketOuterRim",1.0)):
        if key not in p.PropertiesList:
            p.addProperty("App::PropertyLength",key,"Dimensions")
        setattr(p,key,value)
    p.Layout += "四角固定孔及螺丝柱径向外移0.70mm至X=±18.66、Y=±12.62；螺丝柱直径7.1mm，中层Ø2.3孔沿角点径向内外净壁厚各2.4mm；上下盖Ø5.1沉孔到外缘最薄1.0mm，孔位同步。"
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
    assert a.cut(b).Volume<TOL and b.cut(a).Volume<TOL,name
print("ALL_VALIDATIONS_PASSED", "SAVE" if SAVE else "DRY_RUN",flush=True)
if SAVE:
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

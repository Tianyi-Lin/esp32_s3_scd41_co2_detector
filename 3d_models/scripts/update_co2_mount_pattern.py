"""Correct the carrier/cover mounting pattern without changing other parts."""
import os
import FreeCAD as App
import Part

OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
NAMES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd")
OLD_X, OLD_Y = 8.89, 10.16
NEW_X, NEW_Y = 9.0, 10.0
THROUGH_R, BOSS_R = 1.4, 2.5
old_world = [(sx*OLD_X,sy*OLD_Y) for sx in (-1,1) for sy in (-1,1)]
new_world = [(sx*NEW_X,sy*NEW_Y) for sx in (-1,1) for sy in (-1,1)]
pending = []

def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(), copy=True)

def cylinders(shape,r):
    return sorted({(round(f.Surface.Center.x,6),round(f.Surface.Center.y,6))
                   for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
                   and abs(f.Surface.Radius-r)<1e-6})

for filename in NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR,filename))
    p = doc.DesignParameters
    cover,pcb,envelope = doc.RemovableBottomCover,doc.CO2SensorPCB,doc.CO2SensorEnvelope
    changed = {cover.Name,pcb.Name,envelope.Name}
    others = {o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
              if "Shape" in o.PropertiesList and o.Name not in changed}
    cover_pose,pcb_pose,env_pose = (App.Placement(o.Placement) for o in (cover,pcb,envelope))
    before_cover = local_shape(cover)
    assert cylinders(before_cover,THROUGH_R) == sorted(old_world)
    thickness = p.BottomCoverThickness.Value
    boss_h = p.CO2BottomStandoffHeight.Value
    assert abs(thickness-2)<1e-7 and abs(boss_h-1)<1e-7
    after_cover = before_cover.copy()
    # Remove only the four old bosses above the plate, then close old bores.
    for x,y in old_world:
        after_cover = after_cover.cut(Part.makeCylinder(BOSS_R+0.01,boss_h+0.1,
                                      App.Vector(x,y,thickness)))
        after_cover = after_cover.fuse(Part.makeCylinder(THROUGH_R,thickness,
                                       App.Vector(x,y,0)))
    for x,y in new_world:
        after_cover = after_cover.fuse(Part.makeCylinder(BOSS_R,boss_h,
                                       App.Vector(x,y,thickness)))
        after_cover = after_cover.cut(Part.makeCylinder(THROUGH_R,thickness+boss_h+0.2,
                                      App.Vector(x,y,-0.1)))
    after_cover = after_cover.removeSplitter()
    assert after_cover.isValid() and len(after_cover.Solids)==1
    assert cylinders(after_cover,THROUGH_R)==sorted(new_world)
    assert cylinders(after_cover,BOSS_R)==sorted(new_world)
    # The exterior cover-fixing holes and their existing counterbores stay exact.
    for r in (1.45,2.45):
        assert cylinders(after_cover,r)==cylinders(before_cover,r)
    affected = Part.makeCompound([Part.makeCylinder(2.8,3.2,App.Vector(x,y,-0.1))
                                 for x,y in old_world])
    assert after_cover.cut(before_cover).cut(affected).Volume < 1e-7
    assert before_cover.cut(after_cover).cut(affected).Volume < 1e-7
    assert abs(after_cover.Volume-before_cover.Volume)<1e-6
    cover.Shape = after_cover
    cover.Placement = cover_pose

    # Work in the PCB's original frame, where long/short spacing is 20/18.
    before_pcb = local_shape(pcb)
    zmin,zmax = before_pcb.BoundBox.ZMin,before_pcb.BoundBox.ZMax
    old_local = [(sx*OLD_Y,sy*OLD_X) for sx in (-1,1) for sy in (-1,1)]
    new_local = [(sx*NEW_Y,sy*NEW_X) for sx in (-1,1) for sy in (-1,1)]
    assert cylinders(before_pcb,THROUGH_R)==sorted(old_local)
    after_pcb = before_pcb.copy()
    for x,y in old_local:
        after_pcb = after_pcb.fuse(Part.makeCylinder(THROUGH_R,zmax-zmin,
                                   App.Vector(x,y,zmin)))
    for x,y in new_local:
        after_pcb = after_pcb.cut(Part.makeCylinder(THROUGH_R,zmax-zmin+0.2,
                                  App.Vector(x,y,zmin-0.1)))
    after_pcb = after_pcb.removeSplitter()
    assert after_pcb.isValid() and len(after_pcb.Solids)==1
    assert cylinders(after_pcb,THROUGH_R)==sorted(new_local)
    assert abs(after_pcb.Volume-before_pcb.Volume)<1e-6
    pcb.Shape = after_pcb
    pcb.Placement = pcb_pose
    assert cylinders(pcb.Shape,THROUGH_R)==sorted(new_world)
    parts = [o.Shape.transformed(env_pose.inverse().toMatrix(),copy=True)
             for o in (pcb,doc.CO2SensorCan,doc.CO2SensorConnectors)]
    envelope.Shape = Part.makeCompound(parts)
    envelope.Placement = env_pose
    for key,value in (("CO2MountSpacingX",18.0),("CO2MountSpacingY",20.0),
                       ("CO2MountSpacingLongEdge",20.0),("CO2MountSpacingShortEdge",18.0)):
        if key not in p.PropertiesList:
            p.addProperty("App::PropertyLength",key,"Dimensions")
        setattr(p,key,value)
    p.Layout += "CO2 安装孔中心距为长边 20 mm、短边 18 mm；旋转后底板 X 向 18 mm、Y 向 20 mm。"
    doc.recompute()
    for name,(shape,pose) in others.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A==pose,name
    for obj,pose in ((cover,cover_pose),(pcb,pcb_pose),(envelope,env_pose)):
        assert obj.Placement.toMatrix().A==pose.toMatrix().A
    assert envelope.Shape.isValid() and len(envelope.Shape.Solids)==4
    if filename==NAMES[0]:
        assert abs(pcb.Shape.BoundBox.ZMin-cover.Shape.BoundBox.ZMax)<1e-7
        for name in ("RearShell","RemovableBottomCover","ESP32BoardAssembly","HeaderPinsKeepout"):
            assert envelope.Shape.common(doc.getObject(name).Shape).Volume<1e-6,name
    print("VERIFIED",filename)
    print("COVER_AND_PCB_HOLE_CENTERS_XY",cylinders(cover.Shape,THROUGH_R))
    print("LONG_SHORT_PITCH_MM",20.0,18.0)
    print("OTHER_SHAPES_PRESERVED",len(others))
    pending.append(doc)

for doc in pending:
    doc.save()
Part.export([pending[0].RemovableBottomCover],os.path.join(
    OUT_DIR,"ESP32-S3-LCD-1.47B_紧凑双层外壳_可拆底盖.stl"))
for doc in pending:
    print("SAVED",doc.FileName)
    App.closeDocument(doc.Name)

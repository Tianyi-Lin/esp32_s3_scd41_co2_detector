"""Add protected bottom vents, round side-slot ends, deepen the flat reliefs."""
import ast
import math
import os
import FreeCAD as App
import Part
import Mesh

ROOT='/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)'
SOURCE='/Users/bytedance/Documents/New project/create_compact_stacked_enclosure.py'
FILES=('ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd','ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd')
PARTS={'RearShell':'后壳','RemovableBottomCover':'可拆底盖'}
TOL=1e-6
with open(SOURCE,encoding='utf-8') as f:
    tree=ast.parse(f.read())
helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
         ('horizontal_capsule_cut_x','relieve_pcb_columns','bottom_vent_pattern')]
exec(compile(ast.Module(body=helpers,type_ignores=[]),SOURCE,'exec'))


def local(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)


def cylinder_records(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
                   round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),round(f.BoundBox.ZMax,6))
                  for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
                  and abs(f.Surface.Axis.z)>.999999)


docs=[App.openDocument(os.path.join(ROOT,filename)) for filename in FILES]
main=docs[0]
original={name:local(main.getObject(name)) for name in PARTS}
for name in PARTS:
    b=local(docs[1].getObject(name))
    assert original[name].cut(b).Volume<TOL and b.cut(original[name]).Volume<TOL
assert main.DesignParameters.OuterLength.Value==45.4
assert main.DesignParameters.PCBColumnReliefBottomZ.Value>19.

# Round existing rectangular slots within their original 14 x 0.9 mm envelope.
rectangles=[]
capsules=[]
fills=[]
for side in (-1,1):
    x0=-23. if side<0 else 20.
    wall_x=-22.7 if side<0 else 20.5
    wall=Part.makeBox(2.2,20.,23.,App.Vector(wall_x,-10.,2.))
    for i in range(5):
        z=5.+1.7*i
        rect=Part.makeBox(3.,14.,.9,App.Vector(x0,-7.,z))
        cap=horizontal_capsule_cut_x(3.,14.,.9,x0,0.,z+.45)
        assert original['RearShell'].common(rect).Volume<TOL
        assert cap.cut(rect).Volume<TOL
        rectangles.append(rect)
        capsules.append(cap)
        fills.append(rect.common(wall).cut(cap))
fill_tool=Part.makeCompound(fills)
capsule_tool=Part.makeCompound(capsules)
rounded_body=original['RearShell'].fuse(fill_tool).cut(capsule_tool).removeSplitter()
assert original['RearShell'].cut(rounded_body).Volume<TOL
assert rounded_body.cut(original['RearShell']).cut(fill_tool).Volume<TOL
assert abs(rounded_body.Volume-original['RearShell'].Volume-fill_tool.Volume)<TOL
print('ROUNDED_SIDE_SLOTS',len(capsules),'TOTAL_SIZE',14.,.9,'END_RADIUS',.45,flush=True)

# Preserve the existing angle and offset; extend the same planes to deck top.
body,relief_tool,pcb,metrics=relieve_pcb_columns(
    rounded_body,main.ESP32BoardAssembly.Shape,
    [(-18.86,-12.82),(-18.86,12.82)],3.55,1.15,relief_bottom_z=15.5)
assert abs(metrics['plane_offset']-main.DesignParameters.PCBColumnReliefPlaneOffset.Value)<TOL
assert rounded_body.cut(body).cut(relief_tool).Volume<TOL
assert body.cut(rounded_body).Volume<TOL
below=Part.makeBox(60.,50.,15.5,App.Vector(-30.,-25.,0.))
assert original['RearShell'].cut(body).common(below).Volume<TOL,'deck or lower body cut'
for x,y in ((-18.86,-12.82),(-18.86,12.82)):
    normal=App.Vector(2**-.5,(1 if y<0 else -1)*2**-.5,0)
    faces=[f for f in body.Faces if isinstance(f.Surface,Part.Plane)
           and abs(abs(f.normalAt(0,0).dot(normal))-1)<1e-8
           and abs((f.CenterOfMass-App.Vector(x,y,0)).dot(normal)-metrics['plane_offset'])<TOL
           and f.BoundBox.ZLength>5.]
    assert len(faces)==1
    assert abs(faces[0].BoundBox.ZMin-15.5)<TOL and abs(faces[0].BoundBox.ZMax-25.)<TOL
    print('CONTINUOUS_45_DEG_FACE',x,y,'Z',faces[0].BoundBox.ZMin,faces[0].BoundBox.ZMax,flush=True)
slot_arcs=[f for f in body.Faces if isinstance(f.Surface,Part.Cylinder)
           and abs(f.Surface.Axis.x)>.999999 and abs(f.Surface.Radius-.45)<TOL]
assert len(slot_arcs)==20,('side slot end arcs',len(slot_arcs))
assert body.common(capsule_tool).Volume<TOL
before_bores=[c for c in cylinder_records(original['RearShell']) if c[0] in (1.1,1.15,1.6)]
after_bores=[c for c in cylinder_records(body) if c[0] in (1.1,1.15,1.6)]
assert before_bores==after_bores,'mounting bores or PCB bosses changed'
print('RELIEF_METRICS',metrics,flush=True)

# A 7x7 central lattice with holes near the four screw pockets omitted.
mounts=[(x,y) for x in (-9.,9.) for y in (-10.,10.)]
centers=bottom_vent_pattern(mounts)
assert len(centers)==37
holes=Part.makeCompound([Part.makeCylinder(.75,2.2,App.Vector(x,y,-.1)) for x,y in centers])
bottom=original['RemovableBottomCover'].cut(holes).removeSplitter()
assert bottom.cut(original['RemovableBottomCover']).Volume<TOL
assert original['RemovableBottomCover'].cut(bottom).cut(holes).Volume<TOL
assert abs(original['RemovableBottomCover'].Volume-bottom.Volume-len(centers)*math.pi*.75**2*2.)<TOL
old_cyls=cylinder_records(original['RemovableBottomCover'])
new_cyls=cylinder_records(bottom)
assert [c for c in new_cyls if c[0]!=.75]==old_cyls
assert [c for c in new_cyls if c[0]==.75]==sorted((.75,x,y,0.,2.) for x,y in centers)
assert bottom.common(holes).Volume<TOL
sensor_bb=main.CO2SensorPCB.Shape.BoundBox
for x,y in centers:
    assert sensor_bb.XMin<x-.75 and x+.75<sensor_bb.XMax
    assert sensor_bb.YMin<y-.75 and y+.75<sensor_bb.YMax
min_pocket_web=min(math.hypot(x-mx,y-my)-.75-2.55 for x,y in centers for mx,my in mounts)
assert min_pocket_web>=1.5-TOL
assert sensor_bb.ZMin-2.>=1.-TOL
print('BOTTOM_VENTS',len(centers),'DIAMETER',1.5,'PITCH',3.,'ENVELOPE',19.5,19.5,
      'MIN_POCKET_WEB',min_pocket_web,'SENSOR_PCB_BOUNDS',sensor_bb,flush=True)

new_shapes={'RearShell':body,'RemovableBottomCover':bottom}
for name,shape in new_shapes.items():
    assert shape.isValid() and len(shape.Solids)==1,name
    for axis in ('XMin','XMax','YMin','YMax','ZMin','ZMax'):
        assert abs(getattr(shape.BoundBox,axis)-getattr(original[name].BoundBox,axis))<TOL,(name,axis)
    print('VALID_SINGLE_SOLID',name,'VOLUME',shape.Volume,flush=True)

for doc in docs:
    unchanged={o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
               if 'Shape' in o.PropertiesList and o.Name not in PARTS}
    for name in PARTS:
        obj=doc.getObject(name)
        pose=App.Placement(obj.Placement)
        obj.Shape=new_shapes[name].copy()
        obj.Placement=pose
    p=doc.DesignParameters
    for key,value in (('BottomVentDiameter',1.5),('BottomVentPitch',3.),
                      ('BottomVentFootprintLength',19.5),('BottomVentFootprintWidth',19.5),
                      ('BottomVentMinimumPocketWeb',min_pocket_web),
                      ('ConvectionSlotEndRadius',.45),('PCBColumnReliefBottomZ',15.5),
                      ('PCBColumnReliefMinWall',metrics['min_wall']),
                      ('PCBColumnReliefNominalThreadMinWall',metrics['min_nominal_thread_wall'])):
        if key not in p.PropertiesList:
            p.addProperty('App::PropertyLength',key,'Dimensions')
        setattr(p,key,value)
    if 'BottomVentCount' not in p.PropertiesList:
        p.addProperty('App::PropertyInteger','BottomVentCount','Dimensions')
    p.BottomVentCount=len(centers)
    p.Layout+=('底盖中央37个Ø1.5mm通气圆孔，3mm间距，覆盖19.5×19.5mm，略小于CO2模块板；'
               '避开四个传感器沉孔，至沉孔最薄留边1.7mm，板下保留1mm空气层。'
               '两短侧各5条通风槽保持14×0.9mm，端部改为R0.45半圆。'
               '左侧两根柱仍为45度单平面避让，下沿由Z19.6495延长到中层板上表面Z15.5；'
               '不切入中层板，孔位和壁厚不变。')
    doc.recompute()
    for name,(shape,pose) in unchanged.items():
        obj=doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A==pose,name
    print('OTHER_SHAPES_AND_PLACEMENTS_UNCHANGED',doc.Label,len(unchanged),flush=True)

for a,b in [('RearShell','ESP32BoardAssembly'),('RearShell','CO2SensorEnvelope'),
            ('RearShell','HeaderPinsKeepout'),('RearShell','FrontBezel'),
            ('RearShell','RemovableBottomCover'),('RearShell','ButtonPlungerPositive'),
            ('RearShell','ButtonPlungerNegative'),('RemovableBottomCover','CO2SensorEnvelope')]:
    volume=main.getObject(a).Shape.common(main.getObject(b).Shape).Volume
    print('ASSEMBLED_OVERLAP',a,b,volume,flush=True)
    assert volume<TOL,(a,b,volume)
for name in PARTS:
    a,b=local(docs[0].getObject(name)),local(docs[1].getObject(name))
    assert a.cut(b).Volume<TOL and b.cut(a).Volume<TOL
for doc in docs:
    doc.save()
    print('SAVED',doc.FileName,flush=True)
for name,suffix in PARTS.items():
    path=os.path.join(ROOT,'ESP32-S3-LCD-1.47B_紧凑双层外壳_'+suffix+'.stl')
    Part.export([main.getObject(name)],path)
    mesh=Mesh.Mesh(path)
    assert mesh.isSolid(),name
    print('STL_CLOSED',name,mesh.CountFacets,flush=True)
for doc in docs:
    path=doc.FileName
    App.closeDocument(doc.Name)
    check=App.openDocument(path)
    for name in PARTS:
        shape=local(check.getObject(name))
        assert shape.isValid() and len(shape.Solids)==1
        assert shape.cut(new_shapes[name]).Volume<TOL and new_shapes[name].cut(shape).Volume<TOL
    print('REOPEN_VERIFIED',path,flush=True)
    App.closeDocument(check.Name)

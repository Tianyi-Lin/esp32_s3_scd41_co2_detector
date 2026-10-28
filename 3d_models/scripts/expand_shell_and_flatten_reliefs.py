"""Expand the three external outlines 0.2 mm per side and use flat PCB reliefs."""
import ast
import math
import os
import FreeCAD as App
import Part
import Mesh

ROOT='/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)'
SOURCE='/Users/bytedance/Documents/New project/create_compact_stacked_enclosure.py'
BEFORE_RELIEF='/Users/bytedance/Documents/New project/.cad-recovery/before-pcb-inner-relief-8kfB3VJE/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd'
FILES=('ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd','ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd')
PARTS={'RearShell':(2.05,25.,'后壳'), 'FrontBezel':(25.,28.,'前盖'),
       'RemovableBottomCover':(0.,2.,'可拆底盖')}
OLD={(x,y) for x in (-18.66,18.66) for y in (-12.62,12.62)}
NEW={(x,y) for x in (-18.86,18.86) for y in (-12.82,12.82)}
PCB_MOUNTS=((-16.814,-6.640),(-16.814,6.640),(15.186,-8.160),(15.186,8.160))
TOL=1e-6

with open(SOURCE,encoding='utf-8') as f:
    source=f.read()
tree=ast.parse(source)
helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
         ('rounded_prism','rounded_wire','horizontal_capsule_cut_x','relieve_pcb_columns')]
exec(compile(ast.Module(body=helpers,type_ignores=[]),SOURCE,'exec'))


def local(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(),copy=True)


def cyl(r,x,y,z0,z1):
    return Part.makeCylinder(r,z1-z0,App.Vector(x,y,z0))


def cylinder_records(shape):
    return sorted((round(f.Surface.Radius,6),round(f.Surface.Center.x,6),
                   round(f.Surface.Center.y,6),round(f.BoundBox.ZMin,6),round(f.BoundBox.ZMax,6))
                  for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
                  and abs(f.Surface.Axis.z)>.999999)


def bore_records(shape,name,centers):
    radii=(1.15,) if name=='RearShell' else (1.45,2.55)
    return [c for c in cylinder_records(shape) if (c[1],c[2]) in centers and c[0] in radii]


def front_blank():
    env=dict(App=App,Part=Part,rounded_prism=rounded_prism,rounded_wire=rounded_wire,
             outer_w=45.,outer_d=33.5,base_h=25.,lid_t=3.,corner_r=4.)
    start=source.index('lid_shape = rounded_prism(')
    end=source.index('# Both cover locating rims',start)
    exec(compile(source[start:end],'front_window_without_holes','exec'),env)
    return env['lid_shape']


FRONT_BLANK=front_blank()
docs=[App.openDocument(os.path.join(ROOT,f)) for f in FILES]
reference=App.openDocument(BEFORE_RELIEF)
uncut=local(reference.RearShell)
main=docs[0]
for name in PARTS:
    a,b=local(docs[0].getObject(name)),local(docs[1].getObject(name))
    assert a.cut(b).Volume<TOL and b.cut(a).Volume<TOL,('documents differ',name)
before=local(main.RearShell)
board=main.ESP32BoardAssembly.Shape
left_upper=Part.makeCompound([cyl(3.55,-18.66,y,19.64952121420756,25.) for y in (-12.62,12.62)])
# Recover ONLY the earlier PCB-profile relief, not other historical changes.
assert before.cut(uncut).Volume<TOL
assert uncut.cut(before).cut(left_upper).Volume<TOL
assert abs(uncut.Volume-before.Volume-16.711990615625837)<1e-5


def extension(name):
    z0,z1,_=PARTS[name]
    old=rounded_prism(45.,33.5,z1-z0,4.,z0)
    new=rounded_prism(45.4,33.9,z1-z0,4.,z0)
    return new.cut(old)


def alter_cover(before,name):
    records=bore_records(before,name,OLD)
    assert len(records)==8,(name,records)
    fills=Part.makeCompound([cyl(r+.001,x,y,z0,z1) for r,x,y,z0,z1 in records])
    if name=='FrontBezel':
        fills=fills.common(FRONT_BLANK)
        intervals=((1.45,24.9,28.4),(2.55,26.65,28.4))
    else:
        intervals=((1.45,-.1,2.1),(2.55,-.1,1.4))
    cuts=Part.makeCompound([cyl(r,x,y,z0,z1) for x,y in NEW for r,z0,z1 in intervals])
    outside=extension(name)
    result=before.fuse(fills).fuse(outside).cut(cuts).removeSplitter()
    assert result.cut(before).cut(fills.fuse(outside)).Volume<TOL
    assert before.cut(result).cut(cuts).Volume<TOL
    assert not bore_records(result,name,OLD)
    assert len(bore_records(result,name,NEW))==8
    # Preserve all internal holes and circular surfaces except the shifted
    # corner bores and the four external R4 corner surfaces.
    def invariant(records,centers,outer_cx,outer_cy):
        return [c for c in records if not
                ((c[1],c[2]) in centers and c[0] in (1.45,2.55)) and not
                (c[0]==4. and abs(c[1])==outer_cx and abs(c[2])==outer_cy)]
    assert invariant(cylinder_records(before),OLD,18.5,12.75)==invariant(
        cylinder_records(result),NEW,18.7,12.95),name
    return result


def alter_body():
    oldtowers=Part.makeCompound([cyl(3.55,x,y,2.05,25.) for x,y in OLD])
    newtowers=Part.makeCompound([cyl(3.55,x,y,2.05,25.) for x,y in NEW])
    cavity=rounded_prism(41.,29.5,23.15,3.,1.95)
    protected=rounded_prism(41.4,29.9,2.,3.2,13.5)
    protected=protected.multiFuse([cyl(1.6,x,y,15.5,17.436) for x,y in PCB_MOUNTS])
    trim=oldtowers.cut(newtowers).common(cavity).cut(protected)
    restored=uncut.multiFuse([cyl(1.151,x,y,2.05,25.) for x,y in OLD])
    result=restored.cut(trim).multiFuse(newtowers.Solids).fuse(extension('RearShell'))
    cuts=[cyl(1.15,x,y,1.95,25.1) for x,y in NEW]
    cuts.extend(cyl(1.1,x,y,13.2,17.736) for x,y in PCB_MOUNTS)
    cuts.extend(Part.makeBox(22.92,2.6,7.936,App.Vector(-15.349,y-1.3,10.)) for y in (-8.89,8.89))
    # Continue the existing apertures through the 0.2 mm exterior extension.
    usb=horizontal_capsule_cut_x(4.,12.,6.2,20.,0.,18.8)
    cuts.append(usb)
    vents=[]
    for x in (-23.,20.):
        for i in range(5):
            vents.append(Part.makeBox(3.,14.,.9,App.Vector(x,-7.,5.+i*1.7)))
    cuts.extend(vents)
    buttons=[]
    for side in (-1,1):
        buttons.append(Part.makeCylinder(1.7,5.,App.Vector(10.55,side*17.5,19.25),App.Vector(0,-side,0)))
    cuts.extend(buttons)
    allcuts=Part.makeCompound(cuts)
    result=result.cut(allcuts).removeSplitter()
    result,tool,pcb,metrics=relieve_pcb_columns(result,board,[(-18.86,-12.82),(-18.86,12.82)],3.55,1.15)
    allowed=oldtowers.fuse(newtowers).fuse(extension('RearShell'))
    assert result.cut(before).cut(allowed).Volume<TOL
    assert before.cut(result).cut(allowed).Volume<TOL
    assert not bore_records(result,'RearShell',OLD)
    assert bore_records(result,'RearShell',NEW)==sorted((1.15,x,y,2.05,25.) for x,y in NEW)
    for passage in [usb]+vents+buttons:
        assert result.common(passage).Volume<TOL,'blocked port'
    # Confirm each new relief really is ONE planar, vertical 45-degree face.
    for x,y in ((-18.86,-12.82),(-18.86,12.82)):
        angle=math.pi/4 if y<0 else -math.pi/4
        normal=App.Vector(math.cos(angle),math.sin(angle),0)
        faces=[f for f in result.Faces if isinstance(f.Surface,Part.Plane)
               and abs(abs(f.normalAt(0,0).dot(normal))-1)<1e-8
               and abs((f.CenterOfMass-App.Vector(x,y,0)).dot(normal)-metrics['plane_offset'])<1e-6
               and f.BoundBox.ZLength>5.]
        assert len(faces)==1,(x,y,len(faces))
        print('ONE_FLAT_45_DEG_FACE',x,y,'AREA',faces[0].Area,'HEIGHT',faces[0].BoundBox.ZLength,flush=True)
        column=cyl(3.55,x,y,2.05,25.)
        print('COLUMN_PCB_GAP',x,y,result.common(column).distToShape(pcb)[0],flush=True)
    print('RELIEF_METRICS',metrics,flush=True)
    # Existing PCB standoffs, through-holes and deck remain identical locally.
    for x,y in PCB_MOUNTS:
        zone=cyl(1.601,x,y,13.5,17.436)
        assert before.common(zone).cut(result).Volume<TOL
        assert result.common(zone).cut(before).Volume<TOL
    for x,y,dx,dy in ((-20.6,-9,.4,18),(20.2,-9,.4,18),(-14,-14.85,28,.4),(-14,14.45,28,.4)):
        assert Part.makeBox(dx,dy,2.,App.Vector(x,y,13.5)).cut(result).Volume<TOL
    top=max((f for f in pcb.Faces if f.BoundBox.ZLength<1e-5),key=lambda f:f.CenterOfMass.z)
    profile=Part.Face(top.OuterWire)
    profile.translate(App.Vector(0,0,pcb.BoundBox.ZMin-profile.BoundBox.ZMin))
    sweep=profile.extrude(App.Vector(0,0,25.1-pcb.BoundBox.ZMin))
    assert result.common(sweep).Volume<TOL
    return result,metrics


new_body,metrics=alter_body()
new_shapes={'RearShell':new_body}
for name in ('FrontBezel','RemovableBottomCover'):
    new_shapes[name]=alter_cover(local(main.getObject(name)),name)
for name,shape in new_shapes.items():
    assert shape.isValid() and len(shape.Solids)==1,name
    assert abs(shape.BoundBox.XLength-45.4)<TOL and abs(shape.BoundBox.YLength-33.9)<TOL
    print('VALID_SINGLE_SOLID',name,'BOUNDS',shape.BoundBox,'VOLUME',shape.Volume,flush=True)
    if name!='RearShell':
        z=27.5 if name=='FrontBezel' else .5
        wafer=rounded_prism(45.4,33.9,.01,4.,z)
        outline=min(wafer.Faces,key=lambda f:f.CenterOfMass.z).OuterWire
        for x,y in NEW:
            rim=outline.distToShape(Part.Wire([Part.makeCircle(2.55,App.Vector(x,y,z))]))[0]
            assert rim>=1.29-TOL,(name,rim)
            print('COUNTERBORE_OUTER_RIM',name,x,y,rim,flush=True)

for doc in docs:
    unchanged={o.Name:(o.Shape,o.Placement.toMatrix().A) for o in doc.Objects
               if 'Shape' in o.PropertiesList and o.Name not in PARTS}
    for name in PARTS:
        obj=doc.getObject(name)
        pose=App.Placement(obj.Placement)
        obj.Shape=new_shapes[name].copy()
        obj.Placement=pose
    p=doc.DesignParameters
    for key,value in (('OuterLength',45.4),('OuterWidth',33.9),('WallThickness',2.2),
                      ('CoverScrewCenterX',18.86),('CoverScrewCenterY',12.82),
                      ('SideBodyColumnCenterX',18.86),('SideBodyColumnCenterY',12.82),
                      ('CoverScrewRadialOutwardShift',math.hypot(.76,.62)),
                      ('CoverScrewDiagonalShiftFromPrevious',math.sqrt(2)*.2),
                      ('OuterExpansionPerSide',.2),('ButtonOuterProjection',2.),
                      ('PCBColumnReliefClearance',.3),('PCBColumnReliefMinWall',metrics['min_wall']),
                      ('PCBColumnReliefBottomZ',metrics['bottom_z']),
                      ('PCBColumnReliefNominalThreadMinWall',metrics['min_nominal_thread_wall']),
                      ('PCBColumnReliefPlaneOffset',metrics['plane_offset'])):
        if key not in p.PropertiesList:
            p.addProperty('App::PropertyLength',key,'Dimensions')
        setattr(p,key,value)
    if 'PCBColumnReliefAngle' not in p.PropertiesList:
        p.addProperty('App::PropertyAngle','PCBColumnReliefAngle','Dimensions')
    p.PCBColumnReliefAngle=45.
    p.Layout += ('本次替代原PCB轮廓避让：三件外形45.4×33.9mm，四边各外扩0.2mm，R4不变；'
                 '四角柱和三件对应孔同步移至X±18.86、Y±12.82；内腔与电子件位置不动。'
                 '左侧两柱各一个45度竖直平面避让，PCB间隙至少0.3mm；'
                 'Ø2.3孔壁约1.632mm，按M2.5外径约1.532mm；上下盖沉孔到外缘仍至少1.29mm。'
                 '侧面开孔全部切通新增外壁；按钮本体不变，露出外壁2.0mm。')
    doc.recompute()
    for name,(shape,pose) in unchanged.items():
        o=doc.getObject(name)
        assert o.Shape.isSame(shape) and o.Placement.toMatrix().A==pose,name
    assert p.PCBBossRadius.Value==1.6 and p.CoverHeadPocketDiameter.Value==5.1
    assert p.CO2MountSpacingLongEdge.Value==20 and p.CO2MountSpacingShortEdge.Value==18
    assert p.HeaderSlotLength.Value==22.92 and p.HeaderSlotWidth.Value==2.6
    print('ELECTRONICS_BUTTONS_AND_PLACEMENTS_UNCHANGED',doc.Label,len(unchanged),flush=True)

pairs=[('RearShell','ESP32BoardAssembly'),('FrontBezel','ESP32BoardAssembly'),
       ('RemovableBottomCover','ESP32BoardAssembly'),('RearShell','CO2SensorEnvelope'),
       ('RemovableBottomCover','CO2SensorEnvelope'),('FrontBezel','CO2SensorEnvelope'),
       ('RearShell','HeaderPinsKeepout'),('RearShell','FrontBezel'),
       ('RearShell','RemovableBottomCover'),('RearShell','ButtonPlungerPositive'),
       ('RearShell','ButtonPlungerNegative'),('ESP32BoardAssembly','ButtonPlungerPositive'),
       ('ESP32BoardAssembly','ButtonPlungerNegative')]
for a,b in pairs:
    volume=main.getObject(a).Shape.common(main.getObject(b).Shape).Volume
    print('ASSEMBLED_OVERLAP',a,b,volume,flush=True)
    assert volume<TOL,(a,b,volume)

for name in PARTS:
    a=local(docs[0].getObject(name))
    b=local(docs[1].getObject(name))
    assert a.cut(b).Volume<TOL and b.cut(a).Volume<TOL
for doc in docs:
    doc.save()
    print('SAVED',doc.FileName,flush=True)
for name,(_,_,suffix) in PARTS.items():
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

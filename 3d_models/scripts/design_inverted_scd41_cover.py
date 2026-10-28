"""Independent recessed, outward-facing SCD41 cover, retaining the 20 mm PCB gap."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import FreeCAD as App
import Mesh
import MeshPart
import Part

sys.path.insert(0,'/Users/bytedance/Documents/New project')
import rebuild_editable_enclosure as base
from rebuild_direct_sketch_enclosure import DirectModel, detach

ROOT=Path('/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)')
SOURCE=ROOT/'后盖_传感器横置_20261028'/'装配检查_传感器横置.FCStd'
STAGE=Path(tempfile.mkdtemp(prefix='inverted-scd41-cover-',
    dir='/Users/bytedance/Documents/New project/.cad-recovery'))
STEM='后盖_传感器倒装_薄膜内缩1mm_预览'
MOUNTS=[(x,y) for x in (-10.,10.) for y in (-9.,9.)]
CORNERS=[(x,y) for x in (-18.86,18.86) for y in (-12.82,12.82)]
OUTER_Z=-4.28
FLOOR_Z=OUTER_Z+2
SUPPORT_Z=3.0
INTERFACE_Z=2.0


def clean(shape):
    result=Part.Shape()
    result.importBrepFromString(shape.exportBrepToString())
    return result


def ci(sk,name):
    return next(i for i,c in enumerate(sk.Constraints) if c.Name==name)


def center_links(doc,child,master,mapping):
    for source,target in mapping:
        for axis in ('X','Y'):
            doc.getObject(child).setExpression('Constraints.Hole%d_%s'%(target,axis),
                '%s.Constraints.Hole%d_%s'%(master,source,axis))


def build_cover():
    m=DirectModel('InvertedSCD41Cover',STEM)
    sk=m.sketch('OuterProfile','01 后盖外轮廓草图',OUTER_Z)
    m.rounded(sk,45.4,33.9,4)
    m.extrude(sk,'BasePad','02 后盖底板 2 mm',2)
    sk=m.sketch('SkirtSketch','03 加深围边草图（壁厚2.2）',FLOOR_Z)
    m.rounded(sk,45.4,33.9,4)
    m.rounded(sk,41,29.5,1.8)
    m.extrude(sk,'SkirtPad','04 向外加深的后盖围边',INTERFACE_Z-FLOOR_Z)
    sk=m.sketch('CornerBossSketch','05 外侧四角螺丝柱草图（孔位主控）',FLOOR_Z)
    m.circles(sk,CORNERS,7.1)
    m.extrude(sk,'CornerBossPad','06 四角螺丝柱连接至原配合面',INTERFACE_Z-FLOOR_Z)
    sk=m.sketch('SensorBossSketch','07 CO2 横置孔位草图（主控：20×18）',FLOOR_Z)
    m.circles(sk,MOUNTS,5)
    m.extrude(sk,'SensorBossPad','08 倒装 PCB 支撑台',SUPPORT_Z-FLOOR_Z)
    for name,label,locations,diameter in [
        ('CoverHoles','四角外壳通孔',CORNERS,2.9),
        ('SensorHoles','CO2 安装通孔',MOUNTS,2.8)]:
        sk=m.sketch(name+'Sketch',label+'草图（随主控）',SUPPORT_Z)
        m.circles(sk,locations,diameter)
        m.extrude(sk,name,label+'（贯穿）',10,pocket=True,through=True)
    sk=m.sketch('CounterboreSketch','外底面八个沉孔草图（随主控）',OUTER_Z)
    m.circles(sk,CORNERS+MOUNTS,5.1)
    m.extrude(sk,'Counterbores','外底面沉孔 Ø5.1 深1.4',1.4,pocket=True,reversed=True)
    sk=m.sketch('SensorWindowSketch','SCD41 外露窗口草图（侧隙0.3）',SUPPORT_Z)
    m.rounded(sk,10.7,10.7,.7)
    m.extrude(sk,'SensorWindow','传感器外露贯穿窗口',10,pocket=True,through=True)
    vents=[(sx*9.,y) for sx in (-1,1) for y in (-3.,0.,3.)]
    vents += [(x,sy*9.) for sy in (-1,1) for x in (-3.,0.,3.)]
    sk=m.sketch('VentSketch','窗口外围12个通气孔草图',SUPPORT_Z)
    m.circles(sk,vents,1.5)
    m.extrude(sk,'Vents','外围通气孔（贯穿）',10,pocket=True,through=True)
    detach(m)
    b=m.doc.addObject('App::VarSet','ProtectionDimensions')
    b.Label='倒装保护尺寸（薄膜退让、传感器高度、安装面）'
    for name,value,description in [
        ('SensorPackageHeight',6.28,'从PCB元件面到传感器白色表面的模型高度'),
        ('MembraneRecess',1.,'白色表面相对后盖外底面向内退让量'),
        ('PCBContactZ',3.,'保持原来的传感器PCB安装平面Z'),
        ('InterfaceZ',2.,'与现有中间壳对应的后盖配合平面Z')]:
        b.addProperty('App::PropertyLength',name,'倒装保护尺寸',description)
        setattr(b,name,value)
    m.doc.OuterProfile.setExpression('Placement.Base.z',
        'ProtectionDimensions.PCBContactZ - ProtectionDimensions.SensorPackageHeight - ProtectionDimensions.MembraneRecess')
    for name in ('SkirtSketch','CornerBossSketch','SensorBossSketch'):
        m.doc.getObject(name).setExpression('Placement.Base.z',
            'OuterProfile.Placement.Base.z + BasePad.Length')
    m.doc.SkirtPad.setExpression('Length','ProtectionDimensions.InterfaceZ - SkirtSketch.Placement.Base.z')
    m.doc.CornerBossPad.setExpression('Length','SkirtPad.Length')
    m.doc.SensorBossPad.setExpression('Length','ProtectionDimensions.PCBContactZ - SensorBossSketch.Placement.Base.z')
    for name in ('CoverHolesSketch','SensorHolesSketch','SensorWindowSketch','VentSketch'):
        m.doc.getObject(name).setExpression('Placement.Base.z','ProtectionDimensions.PCBContactZ')
    m.doc.CounterboreSketch.setExpression('Placement.Base.z','OuterProfile.Placement.Base.z')
    for child,master,mapping in [
        ('CoverHolesSketch','CornerBossSketch',[(i,i) for i in range(1,5)]),
        ('SensorHolesSketch','SensorBossSketch',[(i,i) for i in range(1,5)]),
        ('CounterboreSketch','CornerBossSketch',[(i,i) for i in range(1,5)]),
        ('CounterboreSketch','SensorBossSketch',[(i,i+4) for i in range(1,5)])]:
        center_links(m.doc,child,master,mapping)
    m.doc.ReadMe.Label='预览：传感器朝外；薄膜内缩1mm；保留20mm PCB间距；后盖向外加深4.28mm'
    m.doc.recompute()
    for f in m.features:
        assert f.Shape.isValid() and len(f.Shape.Solids)==1,(f.Name,f.State)
        f.Shape.check(True)
    assert all(s.FullyConstrained for s in m.sketches)
    assert all('Invalid' not in o.State for o in m.doc.Objects)
    return m


def main():
    print('STAGE',STAGE,flush=True)
    digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    model=build_cover()
    doc=model.doc
    shape=model.tip.Shape
    cad=STAGE/(STEM+'.FCStd')
    doc.saveAs(str(cad))
    step=STAGE/(STEM+'.step')
    Part.export([doc.Body],str(step))
    reimported=Part.read(str(step))
    assert reimported.isValid() and len(reimported.Solids)==1
    reimported.check(True)
    assert abs(reimported.Volume-shape.Volume)<1e-4
    mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.005,AngularDeflection=.05,Relative=False)
    assert mesh.isSolid() and mesh.countComponents()==1
    assert not mesh.hasNonManifolds() and not mesh.hasSelfIntersections()
    assert mesh.countNonUniformOrientedFacets()==0
    mesh.write(str(STAGE/(STEM+'.stl')))
    mesh=Mesh.Mesh(str(STAGE/(STEM+'.stl')))
    assert mesh.isSolid() and mesh.countComponents()==1
    assert not mesh.hasNonManifolds() and not mesh.hasSelfIntersections()
    assert mesh.countNonUniformOrientedFacets()==0
    finished=clean(shape)
    App.closeDocument(doc.Name)
    check=App.openDocument(str(cad))
    check.recompute()
    check.Body.Tip.Shape.check(True)
    assert all(o.FullyConstrained for o in check.Objects if o.TypeId=='Sketcher::SketchObject')
    App.closeDocument(check.Name)
    print('COVER_EXPORTS_PASS',mesh.CountFacets,flush=True)

    assembly=App.openDocument(str(SOURCE))
    names=['CO2SensorPCB','CO2SensorCan','CO2SensorConnectors']
    unchanged={o.Name:(o.Shape,list(o.Placement.toMatrix().A)) for o in assembly.Objects
               if 'Shape' in o.PropertiesList and 'Placement' in o.PropertiesList
               and o.Name not in names+['CO2SensorEnvelope','RemovableBottomCover']}
    # Reflect Z around the PCB mid-plane while retaining the 25.4mm long X axis.
    flip=App.Placement(App.Vector(0,0,7.2),App.Rotation(App.Vector(1,0,0),180))
    for name in names:
        obj=assembly.getObject(name)
        obj.Placement=flip.multiply(obj.Placement)
    can=assembly.CO2SensorCan
    can.Label='SCD41 倒装朝外（薄膜低于后盖1mm）'
    membrane_z=can.Shape.BoundBox.ZMin
    recess=membrane_z-finished.BoundBox.ZMin
    assert abs(recess-1)<1e-5,recess
    pcb=assembly.CO2SensorPCB.Shape
    assert abs(pcb.BoundBox.ZMin-3)<1e-6 and abs(pcb.BoundBox.ZMax-4.2)<1e-6
    assert abs(pcb.BoundBox.XLength-25.4)<1e-5
    envelope=assembly.CO2SensorEnvelope
    envelope.Shape=clean(Part.makeCompound([assembly.getObject(n).Shape for n in names]))
    envelope.Placement=App.Placement()
    envelope.Label='SCD41 横置倒装总成（PCB高度保持）'
    assembly.RemovableBottomCover.Shape=finished
    # Assignment carries the feature's root placement. Resetting it here would
    # lift the recessed cover by 4.28mm and create a real PCB interference.
    assert abs(assembly.RemovableBottomCover.Shape.BoundBox.ZMin-OUTER_Z)<1e-6
    assembly.RemovableBottomCover.Label='倒装保护后盖（向外加深4.28mm，薄膜内缩1mm）'
    assembly.recompute()
    collisions={}
    for name in ('RearShell','RemovableBottomCover','ESP32BoardAssembly','HeaderPinsKeepout','FrontBezel'):
        other=assembly.getObject(name).Shape
        # Report every physical component independently for inspectable checks.
        overlaps={component:assembly.getObject(component).Shape.common(other).Volume
                  for component in names}
        assert all(v<1e-6 for v in overlaps.values()),(name,overlaps)
        collisions[name]=overlaps
    minimum_can_clearance=can.Shape.distToShape(finished)[0]
    assert minimum_can_clearance>.2,minimum_can_clearance
    p=assembly.DesignParameters
    pcb_gap=p.PCBBackPlaneZ.Value-pcb.BoundBox.ZMax
    assert abs(pcb_gap-20)<1e-6
    p.CO2BottomStandoffHeight=SUPPORT_Z-FLOOR_Z
    p.PCBBackToBottomInnerDistance=p.PCBBackPlaneZ.Value-FLOOR_Z
    for name,value in [('CO2MembraneRecess',recess),('BottomCoverOutwardExtension',4.28),
                       ('BottomCoverOuterPlaneZ',OUTER_Z)]:
        if name not in p.PropertiesList:
            p.addProperty('App::PropertyLength',name,'Dimensions')
        setattr(p,name,value)
    p.Layout += ' 2026-10-28倒装预览：PCB高度保持3–4.2mm，传感器朝后盖外侧；薄膜低于新后盖外表面1mm，后盖向外加深4.28mm。'
    for name,(old,pose) in unchanged.items():
        obj=assembly.getObject(name)
        assert obj.Shape.isSame(old) and list(obj.Placement.toMatrix().A)==pose,name
    assembly_path=STAGE/'装配检查_传感器倒装_薄膜内缩1mm.FCStd'
    assembly.saveAs(str(assembly_path))
    App.closeDocument(assembly.Name)
    assembly=App.openDocument(str(assembly_path))
    assert abs(assembly.CO2SensorCan.Shape.BoundBox.ZMin-
               assembly.RemovableBottomCover.Shape.BoundBox.ZMin-1)<1e-5
    App.closeDocument(assembly.Name)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==digest
    record=dict(preview=True,package_height_mm=6.28,membrane_recess_mm=recess,
        outward_cover_extension_mm=4.28,cover_floor_thickness_mm=2,
        wall_thickness_mm=2.2,sensor_window_mm=[10.7,10.7],window_corner_radius_mm=.7,
        minimum_sensor_body_to_cover_clearance_mm=minimum_can_clearance,
        sensor_mount_pitch_xy_mm=[20,18],sensor_support_height_mm=5.28,
        pcb_z_range_mm=[3,4.2],esp32_to_co2_pcb_gap_mm=pcb_gap,
        cover_exterior_z_mm=OUTER_Z,white_surface_z_mm=membrane_z,
        auxiliary_vent_holes=12,collision_overlap_mm3=collisions,
        single_valid_cover_solid=True,extended_geometry_check='PASS',
        mesh_closed=True,mesh_components=1,mesh_self_intersections=False,
        mesh_non_manifold=False,mesh_inconsistent_faces=0,mesh_facets=mesh.CountFacets,
        source_files_unchanged=True,assembly_reopen='PASS',native_reopen='PASS')
    (STAGE/'检查记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    print('ASSEMBLY_PASS',record,flush=True)
    print('DONE',STAGE,flush=True)


if __name__=='__main__':
    main()

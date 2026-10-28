"""Rotate SCD41 mounting layout into landscape; preserve the released sources."""
import hashlib
import json
import math
from pathlib import Path
import tempfile

import FreeCAD as App
import Mesh
import MeshPart
import Part

ROOT = Path('/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)')
CAD_SOURCE = ROOT/'草图直接编辑工程_修正版'/'下盖_草图编辑.FCStd'
ASSEMBLY_SOURCE = ROOT/'ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd'
STAGE = Path(tempfile.mkdtemp(prefix='bottom-sensor-landscape-',
    dir='/Users/bytedance/Documents/New project/.cad-recovery'))
EXPECTED = sorted((x,y) for x in (-10.,10.) for y in (-9.,9.))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def centers(shape, radius, inner=False):
    return sorted(set((round(f.Surface.Center.x,6),round(f.Surface.Center.y,6))
        for f in shape.Faces if isinstance(f.Surface,Part.Cylinder)
        and abs(f.Surface.Radius-radius)<1e-6
        and (not inner or abs(f.Surface.Center.x)<15)))


def index(sketch,name):
    return next(i for i,c in enumerate(sketch.Constraints) if c.Name==name)


def valid(shape):
    assert shape.isValid() and len(shape.Solids)==1
    shape.check(True)


def validate_cover(doc):
    doc.recompute()
    assert all('Invalid' not in o.State for o in doc.Objects)
    assert all(o.FullyConstrained for o in doc.Objects if o.TypeId=='Sketcher::SketchObject')
    shape=doc.Body.Tip.Shape
    valid(shape)
    assert centers(shape,1.4)==EXPECTED
    assert centers(shape,2.5)==EXPECTED
    assert centers(shape,2.55,inner=True)==EXPECTED
    for x,y in EXPECTED:
        # Full-height support above the counterbore floor, with the original bore.
        support=Part.makeCylinder(2.5,1.6,App.Vector(x,y,1.4)).cut(
            Part.makeCylinder(1.4,1.6,App.Vector(x,y,1.4)))
        assert support.cut(shape).Volume<1e-6
    return shape


def mesh_report(mesh):
    data=dict(facets=mesh.CountFacets,closed=mesh.isSolid(),
              components=mesh.countComponents(),non_manifold=mesh.hasNonManifolds(),
              self_intersections=mesh.hasSelfIntersections(),
              inconsistent_orientation=mesh.countNonUniformOrientedFacets())
    assert data['closed'] and data['components']==1
    assert not data['non_manifold'] and not data['self_intersections']
    assert data['inconsistent_orientation']==0 and mesh.Volume>0
    return data


def main():
    print('STAGE',STAGE,flush=True)
    hashes={p:digest(p) for p in (CAD_SOURCE,ASSEMBLY_SOURCE)}
    doc=App.openDocument(str(CAD_SOURCE))
    before=doc.Body.Tip.Shape.copy()
    old_corner=centers(before,1.45)
    old_corner_recess=[p for p in centers(before,2.55) if abs(p[0])>15]
    old_vents=centers(before,.75)
    sketch=doc.SensorBossSketch
    original=[(c.Name,c.Value) for c in sketch.Constraints if c.Name.startswith('Hole')]
    for hole,(x,y) in enumerate(EXPECTED,1):
        sketch.setDatum(index(sketch,'Hole%d_X'%hole),App.Units.Quantity('%g mm'%x))
        sketch.setDatum(index(sketch,'Hole%d_Y'%hole),App.Units.Quantity('%g mm'%y))
    sketch.Label='CO2 横置安装孔位草图（主控：长边20、短边18）'
    doc.ReadMe.Label='传感器长边平行外壳长边；主控草图孔距X20/Y18，凸台、通孔、沉孔联动'
    shape=validate_cover(doc)
    assert abs(shape.Volume-before.Volume)<1e-5
    assert centers(shape,1.45)==old_corner
    assert [p for p in centers(shape,2.55) if abs(p[0])>15]==old_corner_recess
    assert centers(shape,.75)==old_vents
    assert all(abs(getattr(shape.BoundBox,k)-getattr(before.BoundBox,k))<1e-7
               for k in ('XMin','XMax','YMin','YMax','ZMin','ZMax'))
    minimum_vent_ligament=min(math.hypot(x-vx,y-vy)-2.55-.75
        for x,y in EXPECTED for vx,vy in old_vents)
    assert minimum_vent_ligament>0
    print('COVER_VALID',EXPECTED,'VENT_CLEARANCE',minimum_vent_ligament,flush=True)
    base='后盖_传感器横置_20x18mm'
    cad=STAGE/(base+'.FCStd')
    doc.saveAs(str(cad))
    step=STAGE/(base+'.step')
    Part.export([doc.Body],str(step))
    loaded_step=Part.read(str(step))
    valid(loaded_step)
    assert centers(loaded_step,1.4)==EXPECTED
    assert abs(loaded_step.Volume-shape.Volume)<1e-4
    mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.005,
                              AngularDeflection=.05,Relative=False)
    data=mesh_report(mesh)
    stl=STAGE/(base+'.stl')
    mesh.write(str(stl))
    mesh_report(Mesh.Mesh(str(stl)))
    print('EXPORTS_VALID',data,flush=True)
    # Preserve geometry without carrying element-map identifiers across documents.
    result_shape=Part.Shape()
    result_shape.importBrepFromString(shape.exportBrepToString())
    App.closeDocument(doc.Name)
    check=App.openDocument(str(cad))
    validate_cover(check)
    App.closeDocument(check.Name)

    assembly=App.openDocument(str(ASSEMBLY_SOURCE))
    component_names=['CO2SensorPCB','CO2SensorCan','CO2SensorConnectors']
    modified=set(component_names+['CO2SensorEnvelope','RemovableBottomCover'])
    unchanged={o.Name:(o.Shape,list(o.Placement.toMatrix().A))
               for o in assembly.Objects if 'Shape' in o.PropertiesList
               and 'Placement' in o.PropertiesList and o.Name not in modified}
    old_sensor_size=assembly.CO2SensorPCB.Shape.BoundBox
    before_z={n:(assembly.getObject(n).Shape.BoundBox.ZMin,
                 assembly.getObject(n).Shape.BoundBox.ZMax) for n in component_names}
    rotation=App.Placement(App.Vector(0,0,0),App.Rotation(App.Vector(0,0,1),-90))
    for name in component_names:
        obj=assembly.getObject(name)
        obj.Placement=rotation.multiply(obj.Placement)
    envelope=assembly.CO2SensorEnvelope
    envelope.Shape=Part.makeCompound([assembly.getObject(n).Shape for n in component_names])
    envelope.Placement=App.Placement()
    envelope.Label='SCD41 横置总成（长边平行外壳长边）'
    cover=assembly.RemovableBottomCover
    cover.Shape=result_shape
    cover.Placement=App.Placement()
    cover.Label='后盖：传感器横置，孔距长边20 mm/短边18 mm'
    assembly.recompute()
    pcb=assembly.CO2SensorPCB
    assert abs(pcb.Shape.BoundBox.XLength-25.4)<1e-5
    assert abs(pcb.Shape.BoundBox.YLength-22.86)<1e-5
    assert centers(pcb.Shape,1.4)==EXPECTED
    for name in component_names:
        b=assembly.getObject(name).Shape.BoundBox
        assert abs(b.ZMin-before_z[name][0])<1e-7 and abs(b.ZMax-before_z[name][1])<1e-7
    collision={}
    for name in ('RearShell','RemovableBottomCover','ESP32BoardAssembly','HeaderPinsKeepout'):
        other=assembly.getObject(name)
        volume=envelope.Shape.common(other.Shape).Volume
        assert volume<1e-6,(name,volume)
        collision[name]={'overlap_mm3':volume,
                         'minimum_distance_mm':envelope.Shape.distToShape(other.Shape)[0]}
    for name,(old,pose) in unchanged.items():
        obj=assembly.getObject(name)
        assert list(obj.Placement.toMatrix().A)==pose
        assert obj.Shape.isSame(old),name
    p=assembly.DesignParameters
    for name,value in [('CO2MountSpacingX',20),('CO2MountSpacingY',18)]:
        setattr(p,name,value)
    p.Layout += ' 2026-10-28：SCD41改为横置，25.4mm长边平行外壳45.4mm长边，孔距X20/Y18；安装高度保持。'
    assembly_path=STAGE/'装配检查_传感器横置.FCStd'
    assembly.saveAs(str(assembly_path))
    print('ASSEMBLY_VALID',collision,flush=True)
    App.closeDocument(assembly.Name)
    reopened=App.openDocument(str(assembly_path))
    assert centers(reopened.RemovableBottomCover.Shape,1.4)==EXPECTED
    assert centers(reopened.CO2SensorPCB.Shape,1.4)==EXPECTED
    App.closeDocument(reopened.Name)
    for path,value in hashes.items():
        assert digest(path)==value
    report=dict(date='2026-10-28',old_mount_pitch_xy_mm=[18,20],
        new_mount_pitch_xy_mm=[20,18],sensor_size_xy_mm=[25.4,22.86],
        shell_long_axis='X',sensor_long_axis='X',mount_centers_xy_mm=EXPECTED,
        boss_diameter_mm=5,through_hole_diameter_mm=2.8,
        counterbore_diameter_mm=5.1,counterbore_depth_mm=1.4,
        sensor_support_z_mm=3,minimum_vent_ligament_mm=minimum_vent_ligament,
        external_corner_mounts_unchanged=True,external_dimensions_unchanged=True,
        ventilation_holes_unchanged=True,installation_heights_unchanged=True,
        native_and_step_extended_geometry_check='PASS',native_reopen_check='PASS',
        stl_mesh=data,assembly_collision_check=collision,
        source_files_unchanged=True,files=[cad.name,step.name,stl.name,assembly_path.name])
    (STAGE/'检查记录.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('DONE',STAGE,flush=True)


if __name__=='__main__':
    main()

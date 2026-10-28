"""2.5 mm flat covers; all additional depth belongs to the native middle shell.

Run with FreeCAD's Python runtime. Outputs are staged, never written over inputs.
"""
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile

import FreeCAD as App
import Mesh
import MeshPart
import Part

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
COVER_T = 2.5
RECESS = 1.0
PACKAGE_H = 6.28
PCB_CONTACT_Z = RECESS + PACKAGE_H
UPPER_LIFT = PCB_CONTACT_Z - 3.0
MIDDLE_BASE = COVER_T + .05
MOUNTS = [(x, y) for x in (-10., 10.) for y in (-9., 9.)]
from shift_corner_mounts import CORNERS, apply_corner_positions, stamp_corner_parameters
from resize_sensor_window import (WINDOW_LENGTH, WINDOW_WIDTH, WINDOW_RADIUS, CENTER_X,
    CENTER_Y, stamp_window_parameters)
TOL = 1e-6
BUTTON_PROJECTION = 1.5
FOOT_HEIGHT = 2.0


def clean(shape):
    out = Part.Shape()
    out.importBrepFromString(shape.exportBrepToString())
    return out


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b, tol=TOL):
    assert abs(a-b) < tol, (a, b)


def index(sketch, name):
    return next(i for i, c in enumerate(sketch.Constraints) if c.Name == name)


def linked_centers(doc, child, master, pairs):
    for source, target in pairs:
        for axis in ('X', 'Y'):
            doc.getObject(child).setExpression('Constraints.Hole%d_%s' % (target, axis),
                '%s.Constraints.Hole%d_%s' % (master, source, axis))


def validate(doc):
    doc.recompute()
    invalid = [(o.Name, o.State) for o in doc.Objects if 'Invalid' in o.State]
    assert not invalid, invalid
    sketches = [o for o in doc.Objects if o.TypeId == 'Sketcher::SketchObject']
    assert all(o.FullyConstrained for o in sketches), [
        o.Name for o in sketches if not o.FullyConstrained]
    shape = doc.Body.Tip.Shape
    assert shape.isValid() and len(shape.Solids) == 1 and shape.Volume > 0
    shape.check(True)
    return shape


def make_back(DirectModel, detach):
    m = DirectModel('UniformFlatBack', '后盖_2.5mm_无围边_草图编辑')
    sk = m.sketch('OuterProfile', '01 后盖外轮廓（无加深围边）', 0)
    m.rounded(sk, 45.4, 33.9, 4)
    m.extrude(sk, 'BasePad', '02 后盖基础板厚 2.5 mm', COVER_T)
    sk = m.sketch('SensorBossSketch', '03 CO2 横置安装孔位主控 X20/Y18', COVER_T)
    m.circles(sk, MOUNTS, 5)
    m.extrude(sk, 'SensorBossPad', '04 传感器安装台（不是外围围边）',
              PCB_CONTACT_Z-COVER_T)
    for name, locations, diameter in [
        ('CoverHoles', CORNERS, 2.9), ('SensorHoles', MOUNTS, 2.8)]:
        sk = m.sketch(name+'Sketch', name+' 贯穿孔草图', PCB_CONTACT_Z)
        m.circles(sk, locations, diameter)
        m.extrude(sk, name, name+' 贯穿孔', 12, pocket=True, through=True)
    sk = m.sketch('CounterboreSketch', '外底面八个沉孔 Ø5.1', 0)
    m.circles(sk, CORNERS+MOUNTS, 5.1)
    m.extrude(sk, 'Counterbores', '外底面沉孔 深1.4', 1.4,
              pocket=True, reversed=True)
    sk = m.sketch('SensorWindowSketch', 'SCD41 实际穿板外形每边+0.3mm', PCB_CONTACT_Z)
    m.rounded(sk, WINDOW_LENGTH, WINDOW_WIDTH, WINDOW_RADIUS, CENTER_X, CENTER_Y)
    m.extrude(sk, 'SensorWindow', '传感器外露窗口（贯穿）', 12,
              pocket=True, through=True)
    vents = [(sx*9., y) for sx in (-1, 1) for y in (-3., 0., 3.)]
    vents += [(x, sy*9.) for sy in (-1, 1) for x in (-3., 0., 3.)]
    sk = m.sketch('VentSketch', '窗口外围十二个 Ø1.5 通气孔', PCB_CONTACT_Z)
    m.circles(sk, vents, 1.5)
    m.extrude(sk, 'Vents', '外围通气孔（贯穿）', 12, pocket=True, through=True)
    detach(m)
    doc = m.doc
    cfg = doc.addObject('App::VarSet', 'ProtectionDimensions')
    cfg.Label = '传感器倒装保护尺寸（不增加后盖围边）'
    for name, value in [('SensorPackageHeight', PACKAGE_H), ('MembraneRecess', RECESS)]:
        cfg.addProperty('App::PropertyLength', name, 'Dimensions')
        setattr(cfg, name, value)
    doc.SensorBossSketch.setExpression('Placement.Base.z',
        'OuterProfile.Placement.Base.z + BasePad.Length')
    doc.SensorBossPad.setExpression('Length',
        'ProtectionDimensions.MembraneRecess + ProtectionDimensions.SensorPackageHeight - BasePad.Length')
    for name in ('CoverHolesSketch', 'SensorHolesSketch', 'SensorWindowSketch', 'VentSketch'):
        doc.getObject(name).setExpression('Placement.Base.z',
            'SensorBossSketch.Placement.Base.z + SensorBossPad.Length')
    pairs = [(i, i) for i in range(1, 5)]
    linked_centers(doc, 'SensorHolesSketch', 'SensorBossSketch', pairs)
    linked_centers(doc, 'CounterboreSketch', 'CoverHolesSketch', pairs)
    linked_centers(doc, 'CounterboreSketch', 'SensorBossSketch', [(i, i+4) for i in range(1, 5)])
    doc.ReadMe.Label = '后盖平板厚2.5mm、无外围围边；四个局部安装台支撑倒装PCB；表面内缩1mm'
    validate(doc)
    return doc


def make_top(path):
    doc = App.openDocument(str(path))
    doc.Label = '上盖_2.5mm_草图编辑'
    doc.OuterProfile.Placement.Base.z += UPPER_LIFT
    doc.BasePad.Length = COVER_T
    doc.BasePad.Label = '02 上盖基础板厚 2.5 mm'
    # Concentric, equal-offset sections yield exact conical corner transitions.
    # Keep the display-side aperture unchanged; avoid the legacy skewed loft's
    # curve-on-surface STEP errors and self-intersecting display-rim tessellation.
    doc.WindowSection1.setExpression('Placement.Base.z', 'OuterProfile.Placement.Base.z')
    for name, expression in [
        ('Length', 'WindowSection1.Constraints.Length + 3.096 mm'),
        ('Width', 'WindowSection1.Constraints.Width + 3.096 mm'),
        ('CornerRadius', 'WindowSection1.Constraints.CornerRadius + 1.548 mm'),
        ('CenterX', 'WindowSection1.Constraints.CenterX'),
        ('CenterY', 'WindowSection1.Constraints.CenterY')]:
        doc.WindowSection2.setExpression('Constraints.'+name, expression)
    doc.ReadMe.Label = '上盖平板厚2.5mm；屏幕下口不变；同心等宽外扩斜面、R0.4过渡和Ø5.1沉孔'
    apply_corner_positions(doc, 'top')
    validate(doc)
    # The legacy split fillet's B-spline control-box extends below its trimmed
    # surface. Use the actual trimmed geometry, not the loose control-point box.
    close(doc.Body.Tip.Shape.optimalBoundingBox(False, False).ZLength, COVER_T, 1e-5)
    return doc


def make_middle(path):
    doc = App.openDocument(str(path))
    doc.Label = '中间外壳_加深_草图编辑'
    old_top = doc.OuterProfile.Placement.Base.z + doc.OuterPad.Length.Value
    doc.OuterProfile.Placement.Base.z = MIDDLE_BASE
    doc.OuterPad.Length = old_top+UPPER_LIFT-MIDDLE_BASE
    doc.CavitySketch.setExpression('Placement.Base.z',
        'OuterProfile.Placement.Base.z + OuterPad.Length')
    doc.DeckSketch.Placement.Base.z += UPPER_LIFT
    doc.CentralSketch.setExpression('Placement.Base.z',
        'DeckSketch.Placement.Base.z + DeckPad.Length')
    doc.HeaderSketch.Placement.Base.z += UPPER_LIFT
    for name in ('USBSketch', 'GuideSketchPositive', 'GuideSketchNegative',
                 'ButtonHoleSketchPositive', 'ButtonHoleSketchNegative'):
        doc.getObject(name).Placement.Base.z += UPPER_LIFT
    # Keep the rear feet and lower ventilation in place; the front feet follow
    # the translated display/ESP32 end of the enclosure.
    for hole in (2, 4):
        sk = doc.FootSketch
        name = 'Hole%d_Y' % hole
        sk.setDatum(index(sk, name), App.Units.Quantity(sk.getDatum(index(sk, name)).Value-UPPER_LIFT))
    doc.OuterPad.Label = '中间外壳加深（新增高度由中间件承担）'
    doc.FootPad.Length = FOOT_HEIGHT
    doc.ReadMe.Label = '上下盖均2.5mm且无加深围边；中层板、ESP32、Type-C和按钮同步上移4.28mm'
    apply_corner_positions(doc, 'middle')
    validate(doc)
    close(doc.Body.Tip.Shape.BoundBox.ZMin, MIDDLE_BASE)
    close(doc.Body.Tip.Shape.BoundBox.ZMax, old_top+UPPER_LIFT)
    return doc


def export_native(doc, folder, stem):
    shape = validate(doc)
    for obj in doc.Objects:
        if hasattr(obj, 'Visibility'):
            obj.Visibility = obj in (doc.Body, doc.Body.Tip)
    native = folder/(stem+'.FCStd')
    doc.saveAs(str(native))
    shape = clean(doc.Body.Tip.Shape)
    step = folder/'打印文件'/(stem+'.step')
    Part.export([doc.Body], str(step))
    roundtrip = Part.read(str(step))
    assert roundtrip.isValid() and len(roundtrip.Solids) == 1
    close(roundtrip.Volume, shape.Volume, .001)
    roundtrip.check(True)
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=.005,
        AngularDeflection=.05, Relative=False)
    stl = folder/'打印文件'/(stem+'.stl')
    mesh.write(str(stl))
    mesh = Mesh.Mesh(str(stl))
    assert mesh.isSolid() and mesh.countComponents() == 1
    assert not mesh.hasNonManifolds() and not mesh.hasSelfIntersections()
    assert mesh.countNonUniformOrientedFacets() == 0 and mesh.Volume > 0
    name = doc.Name
    App.closeDocument(name)
    check = App.openDocument(str(native))
    validate(check)
    App.closeDocument(check.Name)
    print('NATIVE_STEP_STL_PASS', stem, mesh.CountFacets, flush=True)
    return shape, dict(native=native.name, volume_mm3=shape.Volume,
        mesh_facets=mesh.CountFacets, mesh_closed=True, mesh_components=1,
        mesh_non_manifold=False, mesh_self_intersections=False,
        mesh_inconsistent_faces=0, geometry_check='PASS', step_roundtrip='PASS', native_reopen='PASS')


def assign_shape(obj, shape):
    # Shape assignment carries its root placement. Never reset Placement here.
    obj.Shape = clean(shape)
    for attr in ('XMin', 'XMax', 'YMin', 'YMax', 'ZMin', 'ZMax'):
        close(getattr(obj.Shape.BoundBox, attr), getattr(shape.BoundBox, attr))


def set_length(params, name, value):
    if name not in params.PropertiesList:
        params.addProperty('App::PropertyLength', name, 'Dimensions')
    setattr(params, name, value)


def vertical_axes(shape, radius):
    return sorted(set((round(f.Surface.Center.x, 5), round(f.Surface.Center.y, 5))
        for f in shape.Faces if isinstance(f.Surface, Part.Cylinder)
        and abs(f.Surface.Radius-radius) < 1e-6 and abs(f.Surface.Axis.z) > .999))


def stamp_screen_parameters(doc):
    p = doc.DesignParameters
    lower_z = doc.FrontBezel.Shape.optimalBoundingBox(False, False).ZMin
    for name, value in [('ScreenWindowLowerEdgeZ', lower_z),
        ('ScreenWindowChamferDepth', COVER_T), ('ScreenWindowUpperLength', 35.946),
        ('ScreenWindowUpperWidth', 20.986), ('ScreenWindowUpperRadius', 4.048),
        ('ScreenWindowReliefDepth', 0),
        ('ScreenToLidGap', max(0, lower_z-doc.ESP32BoardAssembly.Shape.BoundBox.ZMax))]:
        set_length(p, name, value)
    for name in ('ScreenWindowLongSideAngle', 'ScreenWindowLeftSideAngle', 'ScreenWindowRightSideAngle'):
        if name not in p.PropertiesList:
            p.addProperty('App::PropertyAngle', name, 'Dimensions')
        setattr(p, name, math.degrees(math.atan2(COVER_T, 1.548)))


def validate_assembly(doc):
    doc.recompute()
    pcb = doc.CO2SensorPCB.Shape
    substrates = [s for s in doc.ESP32BoardAssembly.Shape.Solids
        if s.BoundBox.XLength > 30 and s.BoundBox.YLength > 18
        and abs(s.BoundBox.ZLength-.8) < .005]
    assert len(substrates) == 1
    gap = substrates[0].BoundBox.ZMin-pcb.BoundBox.ZMax
    recess = doc.CO2SensorCan.Shape.BoundBox.ZMin-doc.RemovableBottomCover.Shape.BoundBox.ZMin
    close(gap, 20)
    close(recess, RECESS, 1e-5)
    close(pcb.BoundBox.ZMin, PCB_CONTACT_Z)
    close(pcb.BoundBox.ZMax, PCB_CONTACT_Z+1.2)
    close(doc.FrontBezel.Shape.optimalBoundingBox(False, False).ZLength, COVER_T, 1e-5)
    close(doc.RemovableBottomCover.Shape.BoundBox.ZMin, 0)
    corners = sorted((round(x,5),round(y,5)) for x,y in CORNERS)
    for name, radius in [('FrontBezel', 1.45), ('RemovableBottomCover', 1.45), ('RearShell', 1.15)]:
        assert vertical_axes(doc.getObject(name).Shape, radius) == corners, name
    assert vertical_axes(doc.CO2SensorPCB.Shape, 1.4) == sorted(MOUNTS)
    assert vertical_axes(doc.RemovableBottomCover.Shape, 1.4) == sorted(MOUNTS)
    connector_centers = sorted((s.CenterOfMass.x, s.CenterOfMass.y, s.CenterOfMass.z)
        for s in doc.CO2SensorConnectors.Shape.Solids)
    assert len(connector_centers) == 2
    assert connector_centers[0][0] < 0 < connector_centers[1][0]
    assert all(abs(center[1]-(pcb.BoundBox.YMin+pcb.BoundBox.YMax)/2) < 1e-6
        for center in connector_centers)
    p = doc.DesignParameters
    wall_y = p.OuterWidth.Value/2
    close(p.ButtonOuterProjection.Value, BUTTON_PROJECTION)
    close(doc.ButtonPlungerPositive.Shape.BoundBox.YMax-wall_y, BUTTON_PROJECTION)
    close(-doc.ButtonPlungerNegative.Shape.BoundBox.YMin-wall_y, BUTTON_PROJECTION)
    close(doc.RearShell.Shape.BoundBox.YMax-wall_y, FOOT_HEIGHT)
    close(doc.RearShell.Shape.BoundBox.YMax-doc.ButtonPlungerPositive.Shape.BoundBox.YMax, .5)
    collisions = {}
    names = ('FrontBezel', 'RearShell', 'RemovableBottomCover', 'ESP32BoardAssembly',
             'HeaderPinsKeepout', 'CO2SensorPCB', 'CO2SensorCan', 'CO2SensorConnectors')
    for a, b in itertools.combinations(names, 2):
        # Header pins are a keep-out belonging to ESP32 itself, not another part.
        if (a, b) == ('ESP32BoardAssembly', 'HeaderPinsKeepout'):
            continue
        overlap = doc.getObject(a).Shape.common(doc.getObject(b).Shape).Volume
        collisions[a+' / '+b] = overlap
        assert overlap < 1e-5, (a, b, overlap)
    minimum_can_clearance = doc.CO2SensorCan.Shape.distToShape(doc.RemovableBottomCover.Shape)[0]
    assert abs(minimum_can_clearance-.3) < .002
    p = doc.DesignParameters
    return dict(esp32_to_co2_pcb_gap_mm=gap, membrane_recess_mm=recess,
        sensor_pcb_z_mm=[pcb.BoundBox.ZMin, pcb.BoundBox.ZMax],
        sensor_to_cover_min_clearance_mm=minimum_can_clearance,
        sensor_window_size_xy_mm=[WINDOW_LENGTH, WINDOW_WIDTH],
        sensor_window_corner_radius_mm=WINDOW_RADIUS, sensor_window_side_gap_mm=.3,
        cover_base_thickness_mm=COVER_T, front_thickness_mm=COVER_T,
        back_skirt_height_mm=0, upper_assembly_lift_mm=UPPER_LIFT,
        middle_base_z_mm=doc.RearShell.Shape.BoundBox.ZMin,
        middle_top_z_mm=doc.RearShell.Shape.BoundBox.ZMax,
        middle_height_mm=doc.RearShell.Shape.BoundBox.ZLength,
        overall_thickness_mm=doc.FrontBezel.Shape.BoundBox.ZMax,
        co2_mount_pitch_xy_mm=[20, 18], connector_model_count=len(doc.CO2SensorConnectors.Shape.Solids),
        connector_model_arrangement='Left/right along long X axis; simplified placeholders',
        connector_centers_mm=connector_centers,
        button_outer_projection_mm=BUTTON_PROJECTION, horizontal_foot_height_mm=FOOT_HEIGHT,
        horizontal_button_ground_clearance_mm=.5,
        corner_mount_coaxiality='PASS', co2_mount_coaxiality='PASS',
        corner_mount_centers_xy_mm=CORNERS,
        corner_mount_diagonal_shift_mm=.3,
        screen_lower_aperture_mm=[32.85, 17.89], screen_aperture_center_x_mm=-1.5675,
        screen_upper_aperture_mm=[35.946, 20.986], screen_upper_aperture_radius_mm=4.048,
        screen_transition='Concentric equal-offset loft; lower aperture unchanged; R0.4 edge transition',
        plugged_connector_and_wire_space_validated=False, collisions_mm3=collisions)


def make_assembly(source, shapes, folder):
    doc = App.openDocument(str(source))
    doc.Label = '装配检查_盖板2.5mm_中间壳加深'
    for name in ('ESP32BoardAssembly', 'HeaderPinsKeepout',
                 'ButtonPlungerPositive', 'ButtonPlungerNegative'):
        doc.getObject(name).Placement.Base.z += UPPER_LIFT
    flip = App.Placement(App.Vector(0, 0, 7.2+UPPER_LIFT), App.Rotation(App.Vector(1, 0, 0), 180))
    for name in ('CO2SensorPCB', 'CO2SensorCan', 'CO2SensorConnectors'):
        obj = doc.getObject(name)
        obj.Placement = flip.multiply(obj.Placement)
    # The module is already landscape. Only its two socket placeholders belong
    # at the left/right ends; rotating the whole PCB would break the hole layout.
    from fix_co2_connector_layout import correct_connectors
    correct_connectors(doc)
    assign_shape(doc.CO2SensorEnvelope, Part.makeCompound([
        doc.getObject(n).Shape for n in ('CO2SensorPCB', 'CO2SensorCan', 'CO2SensorConnectors')]))
    for name, shape in shapes.items():
        assign_shape(doc.getObject(name), shape)
    doc.RemovableBottomCover.Label = '后盖 平板2.5mm（无加深围边）'
    doc.FrontBezel.Label = '前盖 平板2.5mm'
    doc.RearShell.Label = '中间外壳（承担新增高度）'
    doc.CO2SensorPCB.Label = 'CO2 横置PCB（倒装安装面Z7.28）'
    doc.CO2SensorCan.Label = 'SCD41 朝外（表面内缩1mm）'
    doc.CO2SensorEnvelope.Label = 'CO2 横置倒装总成参考'
    p = doc.DesignParameters
    for name, value in [('HorizontalFootHeight', FOOT_HEIGHT),
        ('HorizontalSupportPlaneY', p.OuterWidth.Value/2+FOOT_HEIGHT),
        ('OverallWidthIncludingFeet', p.OuterWidth.Value+FOOT_HEIGHT)]:
        set_length(p, name, value)
    from horizontal_supports import extend_hemispherical_buttons
    extend_hemispherical_buttons(doc, projection=BUTTON_PROJECTION)
    for name in ('BoardLayerStart', 'PCBMountContactHeight', 'HeaderSlotCutBottomZ',
                 'HeaderSlotCutTopZ', 'ButtonCenterZ', 'PCBColumnReliefBottomZ',
                 'HorizontalFootFrontCenterZ', 'LowerLayerHeightIncrease',
                 'InterLayerDeckBottomZ', 'InterLayerDeckTopZ'):
        if name in p.PropertiesList:
            setattr(p, name, getattr(p, name).Value+UPPER_LIFT)
    for name, value in [('FrontBezelThickness', COVER_T), ('BottomCoverThickness', COVER_T),
        ('CO2BottomStandoffHeight', PCB_CONTACT_Z-COVER_T),
        ('CO2PCBTopZ', PCB_CONTACT_Z+1.2), ('PCBBackPlaneZ', 24.2+UPPER_LIFT),
        ('PCBBackToCO2PCBTopDistance', 20), ('PCBBackToBottomInnerDistance', 24.2+UPPER_LIFT-COVER_T),
        ('CO2MembraneRecess', RECESS), ('BottomCoverOutwardExtension', 0),
        ('BottomCoverOuterPlaneZ', 0), ('LatestLowerLayerHeightIncrease', UPPER_LIFT),
        ('MiddleShellBaseZ', MIDDLE_BASE), ('MiddleShellDepthIncrease', UPPER_LIFT-.5),
        ('RearShellDepth', shapes['RearShell'].BoundBox.ZMax)]:
        set_length(p, name, value)
    p.Layout = ('2026-10-28统一盖板设计：前后基础板厚均2.5mm，后盖无加深围边。'
        '传感器横置倒装，薄膜表面内缩1mm；CO2 PCB安装面Z7.28mm，'
        'ESP32 PCB下表面到CO2 PCB上表面保持20mm。额外高度由中间外壳承担；'
        'Type-C、按钮、中层板与ESP32同步上移4.28mm。'
        '按钮突出1.5mm、侧脚高2mm，离桌间隙0.5mm。实际插头和弯线空间尚待实物确认。')
    stamp_screen_parameters(doc)
    stamp_corner_parameters(doc)
    stamp_window_parameters(doc)
    report = validate_assembly(doc)
    from apply_button_projection15 import export_button_print
    report['button_print'] = export_button_print(doc, folder/'打印文件')
    path = folder/'装配检查_盖板2.5mm_中间壳加深.FCStd'
    doc.saveAs(str(path))
    App.closeDocument(doc.Name)
    check = App.openDocument(str(path))
    validate_assembly(check)
    App.closeDocument(check.Name)
    report['assembly_reopen'] = 'PASS'
    return report


def main():
    parser = argparse.ArgumentParser()
    default_root = SCRIPTS.parent if (SCRIPTS.parent/'ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd').exists() else (
        Path.home()/'Downloads/ESP32-S3-LCD-1.47B_20260204 (1)')
    parser.add_argument('--root', type=Path, default=default_root)
    args = parser.parse_args()
    root = args.root.resolve()
    os.environ['ESP32_MODEL_ROOT'] = str(root)
    import rebuild_editable_enclosure as base
    from rebuild_direct_sketch_enclosure import DirectModel, detach
    stage = Path(tempfile.mkdtemp(prefix='uniform-covers-', dir=base.RECOVERY))
    (stage/'打印文件').mkdir()
    print('STAGE', stage, flush=True)
    sources = [root/'草图直接编辑工程_修正版'/name for name in
        ('上盖_草图编辑.FCStd', '中间外壳_草图编辑.FCStd')]
    assembly_source = root/'后盖_传感器横置_20261028/装配检查_传感器横置.FCStd'
    hashes = {p: digest(p) for p in sources+[assembly_source]}
    outputs = {}
    reports = {}
    specs = [('RemovableBottomCover', make_back(DirectModel, detach), '后盖_2.5mm_无围边_草图编辑'),
             ('FrontBezel', make_top(sources[0]), '上盖_2.5mm_草图编辑'),
             ('RearShell', make_middle(sources[1]), '中间外壳_加深_草图编辑')]
    for name, doc, stem in specs:
        outputs[name], reports[name] = export_native(doc, stage, stem)
    reports['assembly'] = make_assembly(assembly_source, outputs, stage)
    reports['ButtonPlunger'] = reports['assembly'].pop('button_print')
    assert all(digest(p) == value for p, value in hashes.items())
    reports['source_files_unchanged'] = True
    (stage/'检查记录.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    print('DONE', stage, flush=True)


if __name__ == '__main__':
    main()

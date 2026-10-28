"""Apply a scoped, backed-up PCB-edge relief to the current saved models."""
import ast
import os
import FreeCAD as App
import Part
import Mesh

ROOT = '/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)'
SOURCE = '/Users/bytedance/Documents/New project/create_compact_stacked_enclosure.py'
FILES = ('ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd',
         'ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd')
TOL = 1e-6
CENTERS = [(-18.66, -12.62), (-18.66, 12.62)]

# Reuse the generator's helper without running its document-generation code.
with open(SOURCE, encoding='utf-8') as source:
    tree = ast.parse(source.read())
helper = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == 'relieve_pcb_columns')
exec(compile(ast.Module(body=[helper], type_ignores=[]), SOURCE, 'exec'))


def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(), copy=True)


def bore_records(shape):
    return sorted((round(f.Surface.Radius, 6), round(f.Surface.Center.x, 6),
                   round(f.Surface.Center.y, 6), round(f.BoundBox.ZMin, 6),
                   round(f.BoundBox.ZMax, 6), round(f.Area, 6))
                  for f in shape.Faces if isinstance(f.Surface, Part.Cylinder)
                  and abs(f.Surface.Axis.z) > .999999
                  and abs(f.Surface.Radius - 1.15) < TOL)


docs = [App.openDocument(os.path.join(ROOT, filename)) for filename in FILES]
main = docs[0]
board = main.ESP32BoardAssembly.Shape
original = local_shape(main.RearShell)
after, cutter, pcb, metrics = relieve_pcb_columns(original, board, CENTERS, 3.55, 1.15)
print('RELIEF_METRICS', metrics, flush=True)
assert metrics['removed_volume'] > 1
assert after.cut(original).Volume < TOL, 'unexpected addition'
assert original.cut(after).cut(cutter).Volume < TOL, 'out-of-scope removal'
assert bore_records(original) == bore_records(after), 'through bores changed'
assert len(bore_records(after)) == 4
assert after.common(board).Volume < TOL, 'ESP32 collision remains'
print('ESP32_BODY_COLLISION', original.common(board).Volume,
      '->', after.common(board).Volume, flush=True)

# Continuous sweep of the bare PCB outline confirms that the new relief is
# open upward. This tests PCB edge access, not every component's full motion.
top = max((f for f in pcb.Faces if f.BoundBox.ZLength < 1e-5),
          key=lambda f: f.CenterOfMass.z)
profile = Part.Face(top.OuterWire)
profile.translate(App.Vector(0, 0, pcb.BoundBox.ZMin - profile.BoundBox.ZMin))
insertion_sweep = profile.extrude(App.Vector(0, 0, 25.1 - pcb.BoundBox.ZMin))
insertion_overlap = after.common(insertion_sweep).Volume
assert insertion_overlap < TOL, ('PCB edge insertion', insertion_overlap)
print('PCB_EDGE_CONTINUOUS_UPWARD_SWEEP_COLLISION', insertion_overlap, flush=True)
for x, y in CENTERS:
    column = Part.makeCylinder(3.55, 22.95, App.Vector(x, y, 2.05))
    gap = after.common(column).distToShape(pcb)[0]
    bore = Part.makeCylinder(1.15, 22.95, App.Vector(x, y, 2.05))
    nominal_thread = Part.makeCylinder(1.25, 22.95, App.Vector(x, y, 2.05))
    print('LEFT_COLUMN', x, y, 'PCB_GAP', gap,
          'BORE_WALL', bore.distToShape(cutter)[0],
          'NOMINAL_M2_5_ENVELOPE_WALL', nominal_thread.distToShape(cutter)[0], flush=True)
    assert gap >= .3 - TOL
    assert nominal_thread.distToShape(cutter)[0] >= 1.5 - TOL

for doc in docs:
    p = doc.DesignParameters
    assert abs(p.PCBBossRadius.Value - 1.6) < TOL
    assert abs(p.OuterCornerRadius.Value - 4) < TOL
    assert abs(p.CoverHeadPocketDiameter.Value - 5.1) < TOL
    unchanged = {o.Name: (o.Shape, o.Placement.toMatrix().A)
                 for o in doc.Objects if 'Shape' in o.PropertiesList and o.Name != 'RearShell'}
    before = local_shape(doc.RearShell)
    assert original.cut(before).Volume < TOL and before.cut(original).Volume < TOL
    pose = App.Placement(doc.RearShell.Placement)
    doc.RearShell.Shape = after.copy()
    doc.RearShell.Placement = pose
    for key, value in (('PCBColumnReliefClearance', metrics['clearance']),
                       ('PCBColumnReliefMinWall', metrics['min_wall']),
                       ('PCBColumnReliefBottomZ', metrics['bottom_z'])):
        if key not in p.PropertiesList:
            p.addProperty('App::PropertyLength', key, 'Dimensions')
        setattr(p, key, value)
    p.Layout += ('左侧两根角柱按真实PCB外轮廓留0.3mm局部避让，向上贯通；'
                 '孔位不动，避让处Ø2.3孔最薄壁厚约1.640mm，'
                 '取代该局部原2.4mm内壁值；按M2.5公称外径包络仍约1.540mm。')
    doc.recompute()
    for name, (shape, saved_pose) in unchanged.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(shape) and obj.Placement.toMatrix().A == saved_pose, name
    print('OTHER_SHAPES_AND_PLACEMENTS_UNCHANGED', doc.Label, len(unchanged), flush=True)

# Audit the actual assembled coordinates, never the separated exploded poses.
pairs = [
    ('RearShell', 'ESP32BoardAssembly'),
    ('FrontBezel', 'ESP32BoardAssembly'),
    ('RemovableBottomCover', 'ESP32BoardAssembly'),
    ('RearShell', 'CO2SensorEnvelope'),
    ('RemovableBottomCover', 'CO2SensorEnvelope'),
    ('FrontBezel', 'CO2SensorEnvelope'),
    ('ESP32BoardAssembly', 'CO2SensorEnvelope'),
    ('RearShell', 'HeaderPinsKeepout'),
    ('RearShell', 'FrontBezel'),
    ('RearShell', 'RemovableBottomCover'),
    ('RearShell', 'ButtonPlungerPositive'),
    ('RearShell', 'ButtonPlungerNegative'),
    ('ESP32BoardAssembly', 'ButtonPlungerPositive'),
    ('ESP32BoardAssembly', 'ButtonPlungerNegative'),
]
for a, b in pairs:
    overlap = main.getObject(a).Shape.common(main.getObject(b).Shape).Volume
    print('ASSEMBLED_OVERLAP', a, b, overlap, flush=True)
    assert overlap < TOL, (a, b, overlap)

# Commit only after all geometric checks have passed for both documents.
for doc in docs:
    doc.save()
    print('SAVED', doc.FileName, flush=True)
stl = os.path.join(ROOT, 'ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl')
Part.export([main.RearShell], stl)
mesh = Mesh.Mesh(stl)
assert mesh.isSolid()
print('REAR_STL_CLOSED', mesh.CountFacets, flush=True)
for doc in docs:
    path = doc.FileName
    App.closeDocument(doc.Name)
    check = App.openDocument(path)
    saved = local_shape(check.RearShell)
    assert saved.isValid() and len(saved.Solids) == 1
    assert saved.cut(after).Volume < TOL and after.cut(saved).Volume < TOL
    assert bore_records(saved) == bore_records(original)
    assert abs(check.DesignParameters.PCBColumnReliefClearance.Value - .3) < TOL
    print('REOPEN_VERIFIED', path, flush=True)
    App.closeDocument(check.Name)

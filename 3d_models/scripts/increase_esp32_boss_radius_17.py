"""Increase only the four ESP32 pedestal radii from 1.6 to 1.7 mm."""

import math
import os

import FreeCAD as App
import Part
import Mesh

ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
FILES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)
AXES = ((-16.814, -6.640), (-16.814, 6.640),
        (15.186, -8.160), (15.186, 8.160))
RADIUS = 1.7
TOL = 1e-6


def local_shape(obj):
    return obj.Shape.transformed(obj.Placement.inverse().toMatrix(), copy=True)


pending = []
for filename in FILES:
    doc = App.openDocument(os.path.join(ROOT, filename))
    p = doc.DesignParameters
    obj = doc.RearShell
    pose = App.Placement(obj.Placement)
    before = local_shape(obj)
    before_volume = before.Volume
    assert abs(p.PCBBossRadius.Value - 1.6) < TOL
    assert abs(p.PCBBossDiameter.Value - 3.2) < TOL
    hole_radius = p.PCBMountThroughHoleDiameter.Value / 2
    assert abs(hole_radius - 1.1) < TOL
    deck_bottom = 13.5
    deck_top = deck_bottom + p.InterLayerDeckThickness.Value
    contact_z = p.PCBMountContactHeight.Value
    height = contact_z - deck_top
    others = {
        o.Name: (o.Shape, o.Placement.toMatrix().A)
        for o in doc.Objects if "Shape" in o.PropertiesList and o.Name != obj.Name
    }

    rings = []
    for x, y in AXES:
        base = App.Vector(x, y, deck_top)
        rings.append(Part.makeCylinder(RADIUS, height, base).cut(
            Part.makeCylinder(hole_radius, height, base)))
    result = before.multiFuse(rings).removeSplitter()

    slot_bottom = p.HeaderSlotCutBottomZ.Value
    slot_top = p.HeaderSlotCutTopZ.Value
    slot_length = p.HeaderSlotLength.Value
    slot_width = p.HeaderSlotWidth.Value
    slots = [Part.makeBox(
        slot_length, slot_width, slot_top - slot_bottom,
        App.Vector(-3.889 - slot_length / 2, y - slot_width / 2, slot_bottom))
        for y in (-p.HeaderRowSpacing.Value / 2, p.HeaderRowSpacing.Value / 2)]
    # Preserve the existing square-ended header clearances exactly.
    for slot in slots:
        result = result.cut(slot)
    result = result.removeSplitter()
    assert result.isValid() and len(result.Solids) == 1
    added = result.cut(before)
    removed = before.cut(result)
    assert removed.Volume < TOL, ("unexpected removal", removed.Volume)
    expected = 4 * math.pi * (RADIUS**2 - 1.6**2) * height
    assert abs(added.Volume - expected) < TOL, (added.Volume, expected)
    assert abs(result.Volume - before_volume - expected) < TOL
    assert added.cut(Part.makeCompound(rings)).Volume < TOL
    assert all(result.common(slot).Volume < TOL for slot in slots)

    for x, y in AXES:
        surfaces = [f for f in result.Faces
                    if isinstance(f.Surface, Part.Cylinder)
                    and abs(f.Surface.Center.x - x) < TOL
                    and abs(f.Surface.Center.y - y) < TOL
                    and abs(f.Surface.Radius - RADIUS) < TOL
                    and abs(f.BoundBox.ZMin - deck_top) < TOL
                    and abs(f.BoundBox.ZMax - contact_z) < TOL]
        assert surfaces, ("missing R1.7 side face", x, y)
        assert not any(isinstance(f.Surface, Part.Cylinder)
                       and abs(f.Surface.Center.x - x) < TOL
                       and abs(f.Surface.Center.y - y) < TOL
                       and abs(f.Surface.Radius - 1.6) < TOL
                       and f.BoundBox.ZMax > deck_top + TOL
                       for f in result.Faces)
        hole = Part.makeCylinder(hole_radius - 0.001,
                                 contact_z - deck_bottom + 0.6,
                                 App.Vector(x, y, deck_bottom - 0.3))
        assert result.common(hole).Volume < TOL, "through hole blocked"

    obj.Shape = result
    obj.Placement = pose
    p.PCBBossRadius = RADIUS
    p.PCBBossDiameter = 2 * RADIUS
    p.Layout = p.Layout.replace(
        "四个ESP32固定凸台外半径1.6mm（直径3.2mm）",
        "四个ESP32固定凸台外半径1.7mm（直径3.4mm）")
    p.Layout += "本次仅将四个ESP32固定圆台外半径增加0.1mm至1.7mm，孔径、孔位、高度及其他结构不变。"
    doc.recompute()
    for name, (shape, placement) in others.items():
        other = doc.getObject(name)
        assert other.Shape.isSame(shape), ("other shape changed", name)
        assert other.Placement.toMatrix().A == placement, ("other pose changed", name)
    assert obj.Placement.toMatrix().A == pose.toMatrix().A
    print("FOUR_BOSSES_VERIFIED", filename, "R", RADIUS, "hole_R", hole_radius,
          "Z", deck_top, contact_z, "ADDED_MM3", added.Volume,
          "UNCHANGED_OTHER_SHAPES", len(others), flush=True)
    pending.append(doc)

main, exploded = pending
a, b = local_shape(main.RearShell), local_shape(exploded.RearShell)
assert a.cut(b).Volume < TOL and b.cut(a).Volume < TOL
for name in ("ESP32BoardAssembly", "HeaderPinsKeepout", "CO2SensorEnvelope",
             "FrontBezel", "RemovableBottomCover", "ButtonPlungerPositive",
             "ButtonPlungerNegative"):
    volume = main.RearShell.Shape.common(main.getObject(name).Shape).Volume
    print("ASSEMBLY_INTERFERENCE_MM3", name, volume, flush=True)
    assert abs(volume) < TOL, name

for doc in pending:
    doc.save()
stl = os.path.join(ROOT, "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl")
Part.export([main.RearShell], stl)
mesh = Mesh.Mesh(stl)
assert mesh.isSolid()
print("STL_CLOSED", mesh.CountFacets, flush=True)

for doc in pending:
    path = doc.FileName
    App.closeDocument(doc.Name)
    check = App.openDocument(path)
    s = check.RearShell.Shape
    assert s.isValid() and len(s.Solids) == 1
    assert abs(check.DesignParameters.PCBBossRadius.Value - RADIUS) < TOL
    assert abs(s.Volume - a.Volume) < TOL
    print("SAVED_REOPENED", path, "VOLUME", s.Volume, flush=True)
    App.closeDocument(check.Name)

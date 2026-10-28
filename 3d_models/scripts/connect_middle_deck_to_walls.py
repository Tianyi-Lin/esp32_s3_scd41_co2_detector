"""Fill only the 0.3 mm deck perimeter clearance in both current CAD files."""
import os
import FreeCAD as App
import Part

OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
NAMES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)
DECK_Z = 13.5
OLD_GAP = 0.30
WALL_OVERLAP = 0.20
DECK_OVERLAP = 0.10
CORNER_R = 5.0
PCB_MOUNTS = [(-16.814, -6.640), (-16.814, 6.640),
              (15.186, -8.160), (15.186, 8.160)]

def rounded_prism(w, d, h, r, z):
    shape = Part.makeBox(w-2*r, d, h, App.Vector(-w/2+r, -d/2, z))
    shape = shape.fuse(Part.makeBox(w, d-2*r, h, App.Vector(-w/2, -d/2+r, z)))
    for x in (-w/2+r, w/2-r):
        for y in (-d/2+r, d/2-r):
            shape = shape.fuse(Part.makeCylinder(r, h, App.Vector(x, y, z)))
    return shape.removeSplitter()

pending = []
for filename in NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR, filename))
    p = doc.DesignParameters
    shell = doc.RearShell
    assert shell.Placement.toMatrix().A == App.Placement().toMatrix().A
    before = shell.Shape.copy()
    others = {o.Name: (o.Shape, o.Placement.toMatrix().A)
              for o in doc.Objects if "Shape" in o.PropertiesList and o != shell}
    cavity_w = p.OuterLength.Value - 2*p.WallThickness.Value
    cavity_d = p.OuterWidth.Value - 2*p.WallThickness.Value
    cavity_r = CORNER_R - p.WallThickness.Value
    thickness = p.InterLayerDeckThickness.Value
    assert abs(thickness-2.0) < 1e-7
    original_deck = rounded_prism(cavity_w-2*OLD_GAP, cavity_d-2*OLD_GAP,
                                  thickness, cavity_r-OLD_GAP, DECK_Z)
    cavity = rounded_prism(cavity_w, cavity_d, thickness, cavity_r, DECK_Z)
    allowed_addition = cavity.cut(original_deck)
    outer_band = rounded_prism(cavity_w+2*WALL_OVERLAP, cavity_d+2*WALL_OVERLAP,
                               thickness, cavity_r+WALL_OVERLAP, DECK_Z)
    inner_band = rounded_prism(cavity_w-2*(OLD_GAP+DECK_OVERLAP),
                               cavity_d-2*(OLD_GAP+DECK_OVERLAP),
                               thickness+0.2, cavity_r-OLD_GAP-DECK_OVERLAP,
                               DECK_Z-0.1)
    band = outer_band.cut(inner_band)
    hole_tools = [Part.makeCylinder(p.SideBodyTapHoleDiameter.Value/2,
                                    thickness+0.2, App.Vector(x,y,DECK_Z-0.1))
                  for x in (-18.1,18.1) for y in (-12.2,12.2)]
    hole_tools += [Part.makeCylinder(p.PCBMountThroughHoleDiameter.Value/2,
                                     thickness+0.2, App.Vector(x,y,DECK_Z-0.1))
                   for x,y in PCB_MOUNTS]
    holes = Part.makeCompound(hole_tools)
    band = band.cut(holes)
    after = before.fuse(band).removeSplitter()
    added = after.cut(before)
    assert after.isValid() and len(after.Solids) == 1
    assert before.cut(after).Volume < 1e-7
    assert added.cut(allowed_addition).Volume < 1e-7
    assert added.Volume > 1.0
    assert allowed_addition.cut(holes).cut(after).Volume < 1e-7
    assert after.common(holes).Volume < 1e-7
    for field in ("XMin","XMax","YMin","YMax","ZMin","ZMax"):
        assert abs(getattr(after.BoundBox,field)-getattr(before.BoundBox,field)) < 1e-7

    # Material crosses each complete straight inner-wall edge through the full
    # 2 mm deck thickness, not merely through the four corner screw towers.
    joints = [
        Part.makeBox(0.7, cavity_d-2*cavity_r, thickness,
                     App.Vector(sign*cavity_w/2-0.35, -cavity_d/2+cavity_r, DECK_Z))
        for sign in (-1,1)
    ] + [
        Part.makeBox(cavity_w-2*cavity_r, 0.7, thickness,
                     App.Vector(-cavity_w/2+cavity_r, sign*cavity_d/2-0.35, DECK_Z))
        for sign in (-1,1)
    ]
    missing = [j.cut(after).Volume for j in joints]
    assert all(v < 1e-7 for v in missing), missing
    region_inside_old_deck = original_deck
    assert after.common(region_inside_old_deck).cut(before).Volume < 1e-7
    # Newly filled material must not touch any electronics or moving button.
    if filename == NAMES[0]:
        for name in ("ESP32BoardAssembly","HeaderPinsKeepout","CO2SensorEnvelope",
                     "ButtonPlungerPositive","ButtonPlungerNegative"):
            assert added.common(doc.getObject(name).Shape).Volume < 1e-7, name
    shell.Shape = after
    for name, value in (("InterLayerDeckPerimeterGap",0.0),
                        ("InterLayerDeckWallOverlap",WALL_OVERLAP)):
        if name not in p.PropertiesList:
            p.addProperty("App::PropertyLength", name, "Dimensions")
        setattr(p,name,value)
    note = "中层板四周无间隙，与四面侧壁连续融合为一体。"
    if note not in p.Layout:
        p.Layout += note
    doc.recompute()
    for name, (old_shape, old_pose) in others.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(old_shape), name
        assert obj.Placement.toMatrix().A == old_pose, name
    print("VERIFIED", filename)
    print("ADDED_ONLY_IN_PERIMETER_GAP_MM3", added.Volume)
    print("MISSING_MATERIAL_AT_FOUR_WALLS_MM3", missing)
    print("SOLIDS",len(after.Solids),"OTHER_SHAPES_PRESERVED",len(others))
    pending.append(doc)

assert pending[0].RearShell.Shape.cut(pending[1].RearShell.Shape).Volume < 1e-7
assert pending[1].RearShell.Shape.cut(pending[0].RearShell.Shape).Volume < 1e-7
for doc in pending:
    doc.save()
Part.export([pending[0].RearShell], os.path.join(
    OUT_DIR,"ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl"))
for doc in pending:
    print("SAVED",doc.FileName)
    App.closeDocument(doc.Name)

"""Merge both plunger discs into one full-width collar, keeping end positions."""

import os

import FreeCAD as App
import Part


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
MODEL_NAMES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)
BUTTONS = (("ButtonPlungerPositive", 1.0), ("ButtonPlungerNegative", -1.0))
pending = []

for model_name in MODEL_NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR, model_name))
    p = doc.DesignParameters
    before_other = {
        obj.Name: (obj.Shape, obj.Placement.toMatrix().A)
        for obj in doc.Objects
        if "Shape" in obj.PropertiesList and obj.Name not in dict(BUTTONS)
    }
    center_x, center_z = p.ButtonCenterX.Value, p.ButtonCenterZ.Value
    collar_d = p.ButtonStopFlangeDiameter.Value
    outside = p.OuterWidth.Value / 2.0
    stop_outer = outside - p.WallThickness.Value - p.ButtonGuideBossLength.Value - 0.20
    contact_inner = 11.36 + p.ButtonSwitchGap.Value
    collar_t = stop_outer - contact_inner
    assert abs(collar_d - 5.8) < 1e-6
    assert abs(collar_t - 1.39) < 1e-6

    for name, side in BUTTONS:
        obj = doc.getObject(name)
        before = obj.Shape.copy()
        pose = App.Placement(obj.Placement)
        assert pose.toMatrix().A == App.Placement().toMatrix().A
        collar = Part.makeCylinder(
            collar_d / 2.0, collar_t,
            App.Vector(center_x, side * contact_inner, center_z),
            App.Vector(0, side, 0),
        )
        after = before.fuse(collar).removeSplitter()
        assert after.isValid() and len(after.Solids) == 1
        assert before.cut(after).Volume < 1e-7
        assert after.cut(before).cut(collar).Volume < 1e-7
        for field in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
            assert abs(getattr(before.BoundBox, field) - getattr(after.BoundBox, field)) < 1e-6
        cylinder_faces = [f for f in after.Faces if isinstance(f.Surface, Part.Cylinder)]
        ring_faces = [f for f in cylinder_faces if abs(f.Surface.Radius-collar_d/2) < 1e-6]
        assert len(ring_faces) == 1 and len(cylinder_faces) == 2
        assert abs(ring_faces[0].BoundBox.YLength - collar_t) < 1e-6
        assert after.common(doc.RearShell.Shape).Volume < 1e-7

        if model_name == MODEL_NAMES[0]:
            board = doc.ESP32BoardAssembly.Shape
            assert after.common(board).Volume < 1e-7
            # The two end positions overlap axially, so their union is the
            # complete linear swept volume for this cylindrical plunger.
            pushed = after.copy()
            pushed.translate(App.Vector(0, -side * p.ButtonPlungerTravel.Value, 0))
            swept = after.fuse(pushed).removeSplitter()
            assert swept.common(doc.RearShell.Shape).Volume < 1e-7
            assert swept.common(doc.HeaderPinsKeepout.Shape).Volume < 1e-7
            switch_indices = [
                i for i, solid in enumerate(board.Solids)
                if solid.BoundBox.XMin < center_x + collar_d / 2.0
                and solid.BoundBox.XMax > center_x - collar_d / 2.0
                and (solid.BoundBox.YMax > 10.8 and solid.BoundBox.YMin < 12.5
                     if side > 0 else
                     solid.BoundBox.YMin < -10.8 and solid.BoundBox.YMax > -12.5)
            ]
            assert len(switch_indices) == 1, switch_indices
            other_components = Part.makeCompound([
                solid for i, solid in enumerate(board.Solids) if i not in switch_indices
            ])
            assert swept.common(other_components).Volume < 1e-7
            print("SWEPT_SHELL_AND_NON_SWITCH_COLLISIONS_MM3", name, 0.0)
            print("REST_SWITCH_GAP_MM", name,
                  after.distToShape(board.Solids[switch_indices[0]])[0])

        obj.Shape = after
        obj.Placement = pose
        obj.Label = ("内装式单圆台推杆（BOOT/RST，打印件 1）" if side > 0 else
                     "内装式单圆台推杆（BOOT/RST，翻转件 2）")
        print("MERGED", model_name, name, "ADDED_MM3", after.Volume-before.Volume)

    for key, value in (
        ("ButtonStopFlangeThickness", collar_t),
        ("ButtonContactPadDiameter", collar_d),
        ("ButtonContactPadThickness", collar_t),
        ("ButtonCollarDiameter", collar_d),
        ("ButtonCollarThickness", collar_t),
    ):
        if key not in p.PropertiesList:
            p.addProperty("App::PropertyLength", key, "Dimensions")
        setattr(p, key, value)
    if "ButtonInnerRingCount" not in p.PropertiesList:
        p.addProperty("App::PropertyInteger", "ButtonInnerRingCount", "Dimensions")
    p.ButtonInnerRingCount = 1
    p.Layout = p.Layout.replace(
        "外部为圆形按帽，内部用独立压入式限位圈防止脱落，预留 0.8 mm 行程。",
        "外部为 3 mm 圆柱按压端，内部为直径 5.8 mm、厚 1.39 mm 的一体圆台；"
        "从壳内装入，圆台兼作防脱限位和按键接触面，预留 0.8 mm 行程。",
    )
    doc.recompute()
    for name, (old_shape, old_pose) in before_other.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(old_shape), name
        assert obj.Placement.toMatrix().A == old_pose, name
    print("PRESERVED_OTHER_SHAPES", len(before_other))
    print("COLLAR_MM", collar_d, collar_t)
    pending.append(doc)

for doc in pending:
    doc.save()
Part.export([pending[0].ButtonPlungerPositive], os.path.join(
    OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl"
))
for doc in pending:
    print("SAVED", doc.FileName)
    App.closeDocument(doc.Name)

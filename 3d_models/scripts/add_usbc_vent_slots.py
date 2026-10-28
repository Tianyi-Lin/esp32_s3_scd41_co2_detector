"""Add the matching five-slot grille below USB-C to both current CAD files."""

import os

import FreeCAD as App
import Part


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
MODEL_NAMES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)
SLOT_COUNT = 5
SLOT_START_Z = 5.0
USB_BOTTOM_Z = 15.7
pending = []

for model_name in MODEL_NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR, model_name))
    shell = doc.RearShell
    params = doc.DesignParameters
    width = params.ConvectionSlotWidth.Value
    height = params.ConvectionSlotHeight.Value
    pitch = params.ConvectionSlotPitch.Value
    wall = params.WallThickness.Value
    x_max = params.OuterLength.Value / 2.0
    assert shell.Placement.toMatrix().A == App.Placement().toMatrix().A
    before = shell.Shape.copy()
    other_shapes = {
        obj.Name: (obj.Shape, obj.Placement.toMatrix().A)
        for obj in doc.Objects
        if "Shape" in obj.PropertiesList and obj.Name != shell.Name
    }
    cutters = [
        Part.makeBox(
            wall + 1.0, width, height,
            App.Vector(x_max - wall - 0.5, -width / 2.0,
                       SLOT_START_Z + index * pitch),
        )
        for index in range(SLOT_COUNT)
    ]
    cutter_union = Part.makeCompound(cutters)
    columns = Part.makeCompound([
        Part.makeCylinder(
            params.SideBodyColumnDiameter.Value / 2.0,
            params.RearShellDepth.Value,
            App.Vector(x, y, 0),
        )
        for x in (-18.1, 18.1) for y in (-12.2, 12.2)
    ])
    assert cutter_union.common(columns).Volume < 1e-7
    after = before.copy()
    removed_per_slot = []
    for cut in cutters:
        removed = before.common(cut).Volume
        assert abs(removed - wall * width * height) < 1e-6, (
            "槽位置不是完整侧壁，请检查", removed
        )
        removed_per_slot.append(removed)
        after = after.cut(cut)
    after = after.removeSplitter()
    assert after.isValid() and len(after.Solids) == 1
    assert after.cut(before).Volume < 1e-7
    assert before.cut(after).cut(cutter_union).Volume < 1e-7
    residual = [after.common(cut).Volume for cut in cutters]
    assert all(volume < 1e-7 for volume in residual)
    top_z = SLOT_START_Z + (SLOT_COUNT - 1) * pitch + height
    assert top_z < 13.5  # All new vents are below the intermediate deck.
    if model_name == MODEL_NAMES[0]:
        for name in ("CO2SensorEnvelope", "ESP32BoardAssembly", "HeaderPinsKeepout"):
            obj = doc.getObject(name)
            assert obj is not None
            assert cutter_union.common(obj.Shape).Volume < 1e-7

    shell.Shape = after
    for kind, name, value in (
        ("App::PropertyLength", "USBCVentSlotStartZ", SLOT_START_Z),
        ("App::PropertyLength", "USBCVentToConnectorGap", USB_BOTTOM_Z - top_z),
        ("App::PropertyInteger", "USBCVentSlotCount", SLOT_COUNT),
    ):
        if name not in params.PropertiesList:
            params.addProperty(kind, name, "Dimensions")
        setattr(params, name, value)
    params.Layout = params.Layout.replace(
        "-X 短边设置横向栅格，+X 短边仅预留 USB-C，底面和原外部杜邦线出口封闭。",
        "两端短边均设置五条横向透气槽，+X 端位于 USB-C 下方，间隔 3 mm；"
        "底面和原外部杜邦线出口封闭。",
    )
    doc.recompute()
    for name, (old_shape, old_placement) in other_shapes.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(old_shape)
        assert obj.Placement.toMatrix().A == old_placement
    assert abs(params.PCBBossDiameter.Value - 4.0) < 1e-7
    pending.append(doc)
    print("VERIFIED", model_name)
    print("SLOT_COUNT_AND_SIZE_MM", SLOT_COUNT, width, height)
    print("VENT_Z_RANGE_MM", SLOT_START_Z, top_z)
    print("USB_GAP_MM", USB_BOTTOM_Z - top_z)
    print("REMOVED_PER_SLOT_MM3", removed_per_slot)
    print("SLOT_RESIDUAL_MM3", residual)
    print("OTHER_SHAPES_PRESERVED", len(other_shapes))

# Save only after both copies pass the geometry checks.
for doc in pending:
    doc.save()
Part.export([pending[0].RearShell], os.path.join(
    OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl"
))
for doc in pending:
    print("SAVED", doc.FileName)
    App.closeDocument(doc.Name)

"""Replace only the central SCD41 placeholder; preserve the carrier and poses."""

import os

import FreeCAD as App
import Part


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
STEP_PATH = os.path.join(OUT_DIR, "Sensirion_CO2_Sensors_SEK-SCD41_STEP_file.STEP")
MODEL_NAMES = (
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
)

# In this file the evaluation PCB extends from Z=-0.83000342 to Z=0.
# Above it are two disconnected solids: the connector and the real package.
source = Part.read(STEP_PATH)
above_board = source.common(Part.makeBox(40, 40, 10, App.Vector(-5, -5, 0)))
candidates = [
    solid for solid in above_board.Solids
    if abs(solid.BoundBox.XLength - 10.1) < 0.01
    and abs(solid.BoundBox.YLength - 10.1) < 0.01
    and abs(solid.BoundBox.ZLength - 6.28) < 0.01
]
assert len(candidates) == 1, "SCD41 本体未被唯一识别"
package = candidates[0]
assert package.isValid() and len(package.Solids) == 1
bbox = package.BoundBox
pending = []

for model_name in MODEL_NAMES:
    doc = App.openDocument(os.path.join(OUT_DIR, model_name))
    can = doc.CO2SensorCan
    pcb = doc.CO2SensorPCB
    envelope = doc.CO2SensorEnvelope
    can_placement = App.Placement(can.Placement)
    envelope_placement = App.Placement(envelope.Placement)
    unchanged_shapes = {
        obj.Name: (obj.Shape, obj.Placement.toMatrix().A)
        for obj in doc.Objects
        if "Shape" in obj.PropertiesList
        and obj.Name not in (can.Name, envelope.Name)
    }
    # Retain the existing 90-degree rotation and exploded translation. Bake
    # source centering into the new geometry, keeping editable poses intact.
    pcb_in_can_frame = pcb.Shape.transformed(
        can_placement.inverse().toMatrix(), copy=True
    )
    mount_z = pcb_in_can_frame.BoundBox.ZMax
    replacement = package.transformed(App.Placement(
        App.Vector(
            -(bbox.XMin + bbox.XMax) / 2.0,
            -(bbox.YMin + bbox.YMax) / 2.0,
            mount_z - bbox.ZMin,
        ), App.Rotation(),
    ).toMatrix(), copy=True)
    assert replacement.isValid()
    assert abs(replacement.Volume - package.Volume) < 1e-6
    assert len(replacement.Faces) == len(package.Faces)
    can.Shape = replacement
    can.Placement = can_placement
    can.Label = "SCD41 传感器本体（真实 STEP，朝上）"
    if "SourceSTEP" not in can.PropertiesList:
        can.addProperty("App::PropertyFile", "SourceSTEP", "Source")
    can.SourceSTEP = STEP_PATH

    assert abs(can.Shape.BoundBox.ZMin - pcb.Shape.BoundBox.ZMax) < 1e-6
    assert can.Shape.common(pcb.Shape).Volume < 1e-7
    assert can.Shape.common(doc.CO2SensorConnectors.Shape).Volume < 1e-7
    parts_in_envelope_frame = [
        obj.Shape.transformed(envelope_placement.inverse().toMatrix(), copy=True)
        for obj in (pcb, can, doc.CO2SensorConnectors)
    ]
    envelope.Shape = Part.makeCompound(parts_in_envelope_frame)
    envelope.Placement = envelope_placement
    envelope.Label = "SCD41 总成碰撞参考（含真实 STEP 本体）"
    doc.DesignParameters.CO2Height = pcb.Shape.BoundBox.ZLength + bbox.ZLength
    doc.recompute()

    for name, (old_shape, old_placement) in unchanged_shapes.items():
        obj = doc.getObject(name)
        assert obj.Shape.isSame(old_shape), name
        assert obj.Placement.toMatrix().A == old_placement, name
    assert can.Placement.toMatrix().A == can_placement.toMatrix().A
    assert envelope.Placement.toMatrix().A == envelope_placement.toMatrix().A
    envelope_volume_error = envelope.Shape.Volume - sum(
        obj.Shape.Volume for obj in (pcb, can, doc.CO2SensorConnectors)
    )
    print("ENVELOPE_VOLUME_ERROR_MM3", envelope_volume_error)
    # OCC integrates the imported curved faces slightly differently after
    # grouping. Require matching solids and a <0.01 mm3 aggregate discrepancy.
    assert envelope.Shape.isValid()
    assert len(envelope.Shape.Solids) == sum(
        len(obj.Shape.Solids) for obj in (pcb, can, doc.CO2SensorConnectors)
    )
    assert abs(envelope_volume_error) < 0.01, envelope_volume_error

    if model_name == MODEL_NAMES[0]:
        collision_results = {}
        for name in ("RearShell", "RemovableBottomCover", "ESP32BoardAssembly",
                     "HeaderPinsKeepout", "FrontBezel"):
            obj = doc.getObject(name)
            overlap = envelope.Shape.common(obj.Shape).Volume
            collision_results[name] = round(overlap, 8)
            assert overlap < 1e-6, (name, overlap)
        print("ASSEMBLED_COLLISIONS_MM3", collision_results)

    print("VERIFIED", model_name)
    print("PACKAGE_SIZE_MM", bbox.XLength, bbox.YLength, bbox.ZLength)
    print("PACKAGE_VOLUME_AND_FACES", package.Volume, len(package.Faces))
    print("PACKAGE_WORLD_BOUNDS", can.Shape.BoundBox)
    print("PRESERVED_POSE", can.Placement)
    print("UNCHANGED_OTHER_SHAPES", len(unchanged_shapes))
    pending.append(doc)

for doc in pending:
    doc.save()
    print("SAVED", doc.FileName)
for doc in pending:
    App.closeDocument(doc.Name)

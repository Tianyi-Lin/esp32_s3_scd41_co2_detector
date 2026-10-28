"""Read-only preliminary battery packaging study; do not save the model."""
import FreeCAD as App
import Part

ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
doc = App.openDocument(ROOT + "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
names = ("RearShell", "RemovableBottomCover", "FrontBezel", "ESP32BoardAssembly",
         "HeaderPinsKeepout", "CO2SensorPCB", "CO2SensorCan", "CO2SensorConnectors",
         "ButtonPlungerPositive", "ButtonPlungerNegative")
for name in names:
    bb = doc.getObject(name).Shape.BoundBox
    print("PART_BOUNDS", name, (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax), flush=True)
p = doc.DesignParameters
print("DECK_BOTTOM_TOP", p.InterLayerDeckBottomZ.Value, p.InterLayerDeckTopZ.Value, flush=True)
print("NOMINAL_INNER_XY", p.OuterLength.Value - 2*p.WallThickness.Value,
      p.OuterWidth.Value - 2*p.WallThickness.Value, flush=True)
# Abstract volume probes, not a selected or recommended battery product.
for label, dims, base in (
    ("NON_USB_END_4x18x10", (4, 18, 10), (-19.5, -9, 3.5)),
    ("ABOVE_SENSOR_24x13x4", (24, 13, 4), (-12, -6.5, 11.3)),
    ("ABOVE_SENSOR_30x20x4", (30, 20, 4), (-15, -10, 11.3)),
):
    probe = Part.makeBox(*dims, App.Vector(*base))
    print("PROBE", label, flush=True)
    for name in names:
        obj = doc.getObject(name)
        overlap = probe.common(obj.Shape).Volume
        if overlap > 1e-6:
            print("INTERFERENCE", name, overlap, flush=True)
    print("SENSOR_CAN_CLEARANCE", probe.distToShape(doc.CO2SensorCan.Shape)[0], flush=True)
App.closeDocument(doc.Name)

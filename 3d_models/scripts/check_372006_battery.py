"""Read-only collision checks for the user's 37 x 20 x 6 mm battery."""
import FreeCAD as App
import Part

ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
doc = App.openDocument(ROOT + "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
parts = ("RearShell", "HeaderPinsKeepout", "CO2SensorEnvelope", "ESP32BoardAssembly")
for z in (4.5, 10.8, 12.0, 15.8):
    probe = Part.makeBox(37, 20, 6, App.Vector(-18.5, -10, z))
    print("BATTERY37x20x6_Z", z, z + 6, flush=True)
    for name in parts:
        obj = doc.getObject(name)
        vol = probe.common(obj.Shape).Volume
        print("COLLISION_MM3", name, vol, flush=True)
    print("---", flush=True)
# Full-width battery would also approach the four through-hole columns even
# in an otherwise empty new internal layer; report geometric edge clearance.
for x, y in ((-18.86, -12.82), (-18.86, 12.82), (18.86, -12.82), (18.86, 12.82)):
    dx = max(abs(x) - 18.5, 0)
    dy = max(abs(y) - 10, 0)
    distance = (dx*dx + dy*dy)**0.5
    print("COLUMN_DISTANCE_TO_BATTERY", x, y, distance,
          "OUTER_COLUMN_R", 3.55, "BORE_R", 1.15, flush=True)
App.closeDocument(doc.Name)

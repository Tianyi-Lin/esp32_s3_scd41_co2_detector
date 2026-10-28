"""Read the two substrate datum planes and back up the current deliverables."""
import os
import shutil
import sys
import tempfile

import FreeCAD as App
import Part

WORK = "/Users/bytedance/Documents/New project"
ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
sys.path.insert(0, WORK)
from raise_co2_layer import pcb_substrate, floor_z

FILES = ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
         "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd",
         "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd")
for filename in (FILES[0], FILES[2]):
    doc = App.openDocument(os.path.join(ROOT, filename))
    pcb = pcb_substrate(doc)
    bottom = [f for f in pcb.Faces if isinstance(f.Surface, Part.Plane)
              and f.BoundBox.ZLength < 1e-6 and f.Area > 100
              and f.normalAt(0, 0).z < -0.99]
    top = [f for f in doc.CO2SensorPCB.Shape.Faces
           if isinstance(f.Surface, Part.Plane)
           and f.BoundBox.ZLength < 1e-6 and f.Area > 100
           and f.normalAt(0, 0).z > 0.99]
    assert len(bottom) == len(top) == 1
    esp_z, co2_z = bottom[0].CenterOfMass.z, top[0].CenterOfMass.z
    gap = esp_z - co2_z
    print("DATUM_PLANES", filename, "ESP32_BACK_Z", esp_z,
          "CO2_PCB_TOP_Z", co2_z, "GAP", gap, "ADD", 20-gap,
          "FLOOR_Z", floor_z(doc), flush=True)
    assert abs(gap - 17.8) < 1e-6
    assert doc.RearShell.Shape.isValid()
    App.closeDocument(doc.Name)

backup = tempfile.mkdtemp(prefix="before-pcb-to-pcb20-",
                          dir=os.path.join(WORK, ".cad-recovery"))
for filename in FILES + ("ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl",):
    shutil.copy2(os.path.join(ROOT, filename), backup)
for filename in ("create_compact_stacked_enclosure.py", "raise_co2_layer.py",
                 "horizontal_supports.py"):
    shutil.copy2(os.path.join(WORK, filename), backup)
print("BACKUP", backup, flush=True)
